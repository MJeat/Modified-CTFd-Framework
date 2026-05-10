# CTFd/auth.py

```
import requests
import re
from flask import Blueprint, abort
from flask import current_app as app
from flask import redirect, render_template, request, session, url_for
from flask_babel import lazy_gettext as _l

from CTFd.cache import cache, clear_team_session, clear_user_session
from CTFd.exceptions.email import (
    UserConfirmTokenInvalidException,
    UserResetPasswordTokenInvalidException,
)
from CTFd.models import Brackets, Teams, UserFieldEntries, UserFields, Users, db
from CTFd.utils import config, email, get_app_config, get_config
from CTFd.utils import user as current_user
from CTFd.utils import validators
from CTFd.utils.config import can_send_mail, is_teams_mode
from CTFd.utils.config.integrations import mlc_registration
from CTFd.utils.config.visibility import registration_visible
from CTFd.utils.crypto import verify_password
from CTFd.utils.decorators import ratelimit
from CTFd.utils.decorators.visibility import check_registration_visibility
from CTFd.utils.helpers import error_for, get_errors, markup
from CTFd.utils.logging import log
from CTFd.utils.modes import TEAMS_MODE
from CTFd.utils.security.auth import generate_preset_admin, login_user, logout_user
from CTFd.utils.security.email import (
    remove_email_confirm_token,
    remove_reset_password_token,
    verify_email_confirm_token,
    verify_reset_password_token,
)
from CTFd.utils.validators import ValidationError

auth = Blueprint("auth", __name__)


@auth.route("/confirm", methods=["POST", "GET"])
@auth.route("/confirm/<data>", methods=["POST", "GET"])
@ratelimit(method="POST", limit=10, interval=60)
def confirm(data=None):
    if not can_send_mail():
        if get_config("verify_emails") is False:
            return redirect(url_for("challenges.listing"))
        else:
            return render_template(
                "confirm.html",
                errors=[
                    "Email verification is enabled but email sending isn't available. Please contact an admin to confirm your account"
                ],
            )

    if data and request.method == "GET":
        try:
            user_email = verify_email_confirm_token(data)
        except (UserConfirmTokenInvalidException):
            return render_template(
                "confirm.html",
                errors=["Your confirmation link is invalid, please generate a new one"],
            )

        user = Users.query.filter_by(email=user_email).first_or_404()
        if user.verified:
            return redirect(url_for("views.settings"))

        if (
            get_app_config("EMAIL_CONFIRMATION_REQUIRE_INTERACTION")
            and request.args.get("interaction") is None
        ):
            button = """<button style="margin-top: 3rem; padding: 1rem;" onclick="
                let u = new window.URL(window.location.href);
                u.searchParams.set('interaction', '1');
                window.location.href = u;">Click Here to Confirm Email</button>"""
            return render_template("page.html", content=button)

        user.verified = True
        log(
            "registrations",
            format="[{date}] {ip} - successful confirmation for {name}",
            name=user.name,
        )
        db.session.commit()
        remove_email_confirm_token(data)
        clear_user_session(user_id=user.id)
        if get_config("verify_emails"):
            email.successful_registration_notification(user.email)
        db.session.close()
        if current_user.authed():
            return redirect(url_for("challenges.listing"))
        return redirect(url_for("auth.login"))

    if current_user.authed() is False:
        return redirect(url_for("auth.login"))

    user = Users.query.filter_by(id=session["id"]).first_or_404()
    if user.verified:
        return redirect(url_for("views.settings"))

    if data is None:
        if request.method == "POST":
            email.verify_email_address(user.email)
            log(
                "registrations",
                format="[{date}] {ip} - {name} initiated a confirmation email resend",
                name=user.name,
            )
            return render_template(
                "confirm.html", infos=[f"Confirmation email sent to {user.email}!"]
            )
        elif request.method == "GET":
            return render_template("confirm.html")


@auth.route("/reset_password", methods=["POST", "GET"])
@auth.route("/reset_password/<data>", methods=["POST", "GET"])
@ratelimit(method="POST", limit=10, interval=60)
def reset_password(data=None):
    if config.can_send_mail() is False and data is None:
        return render_template(
            "reset_password.html",
            errors=[
                markup(
                    "This CTF is not configured to send email.<br> Please contact an organizer to have your password reset."
                )
            ],
        )

    if data is not None:
        try:
            email_address = verify_reset_password_token(data)
        except (UserResetPasswordTokenInvalidException):
            return render_template(
                "reset_password.html",
                errors=["Your reset link is invalid, please generate a new one"],
            )

        if request.method == "GET":
            return render_template("reset_password.html", mode="set")
        if request.method == "POST":
            password = request.form.get("password", "").strip()
            user = Users.query.filter_by(email=email_address).first_or_404()
            if user.oauth_id:
                return render_template(
                    "reset_password.html",
                    infos=[
                        "Your account was registered via an authentication provider and does not have an associated password. Please login via your authentication provider."
                    ],
                )

            pass_short = len(password) == 0
            if pass_short:
                return render_template(
                    "reset_password.html", errors=[_l("Please pick a longer password")]
                )

            password_min_length = int(get_config("password_min_length", default=0))
            pass_min = len(password) < password_min_length
            if pass_min:
                return render_template(
                    "reset_password.html",
                    errors=[
                        _l(
                            f"Password must be at least {password_min_length} characters"
                        )
                    ],
                )

            user.password = password
            user.change_password = False
            db.session.commit()
            remove_reset_password_token(data)
            clear_user_session(user_id=user.id)
            log(
                "logins",
                format="[{date}] {ip} - successful password reset for {name}",
                name=user.name,
            )
            db.session.close()
            email.password_change_alert(user.email)
            return redirect(url_for("auth.login"))

    if request.method == "POST":
        email_address = request.form["email"].strip()
        user = Users.query.filter_by(email=email_address).first()

        get_errors()

        if not user:
            return render_template(
                "reset_password.html",
                infos=[
                    _l(
                        "If that account exists you will receive an email, please check your inbox"
                    )
                ],
            )

        if user.oauth_id:
            return render_template(
                "reset_password.html",
                infos=[
                    _l(
                        "The email address associated with this account was registered via an authentication provider and does not have an associated password. Please login via your authentication provider."
                    )
                ],
            )

        limit = cache.inc(f"reset_password_attempt_user_{user.id}")
        cache.expire(f"reset_password_attempt_user_{user.id}", 180)
        if limit > 5:
            return render_template(
                "reset_password.html",
                errors=[
                    _l("Too many password reset attempts. Please try again later.")
                ],
            )
        email.forgot_password(email_address)

        return render_template(
            "reset_password.html",
            infos=[
                _l(
                    "If that account exists you will receive an email, please check your inbox"
                )
            ],
        )
    return render_template("reset_password.html")


@auth.route("/register", methods=["POST", "GET"])
@check_registration_visibility
@ratelimit(method="POST", limit=2, interval=60)
def register():
    errors = get_errors()
    if current_user.authed():
        return redirect(url_for("challenges.listing"))

    num_users_limit = int(get_config("num_users", default=0))
    num_users = Users.query.filter_by(banned=False, hidden=False).count()
    if num_users_limit and num_users >= num_users_limit:
        abort(
            403,
            description=f"Reached the maximum number of users ({num_users_limit}).",
        )

    if request.method == "POST":
        # --- CSRF/NONCE SECURITY CHECK ---
        nonce = request.form.get("nonce")
        if nonce != session.get("nonce"):
            errors.append(_l("Invalid Security Token. Please refresh and try again."))
            return render_template(
                "register.html", 
                errors=errors, 
                registration_fields=UserFields.query.all()
            )

        name = request.form.get("name", "").strip()
        email_address = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        website = request.form.get("website")
        affiliation = request.form.get("affiliation")
        country = request.form.get("country")
        registration_code = str(request.form.get("registration_code", ""))
        bracket_id = request.form.get("bracket_id", None)

        # Validation Logic
        name_len = len(name) == 0
        names = Users.query.add_columns(Users.name, Users.id).filter_by(name=name).first()
        emails = Users.query.add_columns(Users.email, Users.id).filter_by(email=email_address).first()
        pass_short = len(password) == 0
        pass_long = len(password) > 128
        valid_email = validators.validate_email(email_address)
        
        # --- CUSTOM SECURITY CHECKS ---
        if not email_address.endswith("@aupp.edu.kh"):
            errors.append(_l("Only @aupp.edu.kh email addresses are allowed."))
        if any(char.isdigit() for char in name):
            errors.append(_l("Usernames cannot contain numbers."))
        if not re.search(r"[!@#$%^&*]", password):
            errors.append(_l("Password must contain at least one symbol (!@#$%^&*)."))
        if len(password) < 5 or len(password) > 10:
            errors.append(_l("Password must be between 5 and 10 characters."))

        password_min_length = int(get_config("password_min_length", default=0))
        pass_min = len(password) < password_min_length

        if get_config("registration_code"):
            if registration_code.lower() != str(get_config("registration_code", default="")).lower():
                errors.append(_l("The registration code you entered was incorrect"))

        # Process custom user fields
        fields = {field.id: field for field in UserFields.query.all()}
        entries = {}
        for field_id, field in fields.items():
            value = request.form.get(f"fields[{field_id}]", "").strip()
            if field.required is True and not value:
                errors.append(_l("Please provide all required fields"))
                break
            entries[field_id] = bool(value) if field.field_type == "boolean" else value

        # standard CTFd validations
        if not valid_email: errors.append(_l("Please enter a valid email address"))
        if names: errors.append(_l("That user name is already taken"))
        if emails: errors.append(_l("That email has already been used"))
        if pass_short or (password_min_length and pass_min): errors.append(_l("Pick a longer password"))
        if pass_long: errors.append(_l("Pick a shorter password"))
        if name_len: errors.append(_l("Pick a longer user name"))

        if len(errors) > 0:
            return render_template(
                "register.html",
                errors=errors,
                name=name,
                email=email_address,
                registration_fields=UserFields.query.all()
            )
        else:
            user = Users(name=name, email=email_address, password=password, bracket_id=bracket_id)
            if website: user.website = website
            if affiliation: user.affiliation = affiliation
            if country: user.country = country
            db.session.add(user)
            db.session.commit()

            for field_id, value in entries.items():
                db.session.add(UserFieldEntries(field_id=field_id, value=value, user_id=user.id))
            db.session.commit()

            login_user(user)
            db.session.close()
            return redirect(url_for("challenges.listing"))
    else:
        # GET Request
        return render_template(
            "register.html", 
            errors=errors, 
            registration_fields=UserFields.query.all()
        )


@auth.route("/login", methods=["POST", "GET"])
@ratelimit(method="POST", limit=5, interval=60)
def login():
    errors = get_errors()
    if request.method == "POST":
        nonce = request.form.get("nonce")
        if nonce != session.get("nonce"):
            errors.append(_l("Invalid Security Token. Please refresh and try again."))
            return render_template("login.html", errors=errors)

        name = request.form.get("name")
        password = request.form.get("password", "")

        if name == get_app_config("PRESET_ADMIN_NAME") and password == get_app_config("PRESET_ADMIN_PASSWORD"):
            admin = generate_preset_admin()
            if admin:
                login_user(admin)
                return redirect(url_for("challenges.listing"))

        user = Users.query.filter_by(email=name).first() if validators.validate_email(name) else Users.query.filter_by(name=name).first()

        if user:
            fail_key = f"login_fails_{user.id}"
            fails = cache.get(fail_key) or 0
            if fails >= 5:
                errors.append(_l("Account Locked: Too many failed attempts. Try again in 10 minutes."))
                return render_template("login.html", errors=errors)

            if verify_password(password, user.password):
                session.regenerate()
                cache.delete(fail_key)
                login_user(user)
                return redirect(url_for("challenges.listing"))
            else:
                cache.set(fail_key, fails + 1, timeout=600)
                errors.append("Your username or password is incorrect")
        else:
            errors.append("Your username or password is incorrect")
        
        return render_template("login.html", errors=errors)
    else:
        return render_template("login.html", errors=errors)

@auth.route("/oauth")
def oauth_login():
    endpoint = (
        get_app_config("OAUTH_AUTHORIZATION_ENDPOINT")
        or get_config("oauth_authorization_endpoint")
        or "https://auth.majorleaguecyber.org/oauth/authorize"
    )

    if get_config("user_mode") == "teams":
        scope = "profile team"
    else:
        scope = "profile"

    client_id = get_app_config("OAUTH_CLIENT_ID") or get_config("oauth_client_id")

    if client_id is None:
        error_for(
            endpoint="auth.login",
            message="OAuth Settings not configured. "
            "Ask your CTF administrator to configure MajorLeagueCyber integration.",
        )
        return redirect(url_for("auth.login"))

    redirect_url = "{endpoint}?response_type=code&client_id={client_id}&scope={scope}&state={state}".format(
        endpoint=endpoint, client_id=client_id, scope=scope, state=session["nonce"]
    )
    return redirect(redirect_url)


@auth.route("/redirect", methods=["GET"])
@ratelimit(method="GET", limit=10, interval=60)
def oauth_redirect():
    oauth_code = request.args.get("code")
    state = request.args.get("state")
    if session["nonce"] != state:
        log("logins", "[{date}] {ip} - OAuth State validation mismatch")
        error_for(endpoint="auth.login", message="OAuth State validation mismatch.")
        return redirect(url_for("auth.login"))

    if oauth_code:
        url = (
            get_app_config("OAUTH_TOKEN_ENDPOINT")
            or get_config("oauth_token_endpoint")
            or "https://auth.majorleaguecyber.org/oauth/token"
        )

        client_id = get_app_config("OAUTH_CLIENT_ID") or get_config("oauth_client_id")
        client_secret = get_app_config("OAUTH_CLIENT_SECRET") or get_config(
            "oauth_client_secret"
        )
        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            "code": oauth_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
        }
        token_request = requests.post(url, data=data, headers=headers, timeout=5)

        if token_request.status_code == requests.codes.ok:
            token = token_request.json()["access_token"]
            user_url = (
                get_app_config("OAUTH_API_ENDPOINT")
                or get_config("oauth_api_endpoint")
                or "https://api.majorleaguecyber.org/user"
            )

            headers = {
                "Authorization": "Bearer " + str(token),
                "Content-type": "application/json",
            }
            api_data = requests.get(url=user_url, headers=headers, timeout=5).json()

            user_id = api_data["id"]
            user_name = api_data["name"]
            user_email = api_data["email"]

            user = Users.query.filter_by(email=user_email).first()
            if user is None:
                num_users_limit = int(get_config("num_users", default=0))
                num_users = Users.query.filter_by(banned=False, hidden=False).count()
                if num_users_limit and num_users >= num_users_limit:
                    abort(
                        403,
                        description=f"Reached the maximum number of users ({num_users_limit}).",
                    )

                if registration_visible() or mlc_registration():
                    user = Users(
                        name=user_name,
                        email=user_email,
                        oauth_id=user_id,
                        verified=True,
                    )
                    db.session.add(user)
                    db.session.commit()
                else:
                    log("logins", "[{date}] {ip} - Public registration via MLC blocked")
                    error_for(
                        endpoint="auth.login",
                        message="Public registration is disabled. Please try again later.",
                    )
                    return redirect(url_for("auth.login"))

            if get_config("user_mode") == TEAMS_MODE and user.team_id is None:
                team_id = api_data["team"]["id"]
                team_name = api_data["team"]["name"]

                team = Teams.query.filter_by(oauth_id=team_id).first()
                if team is None:
                    num_teams_limit = int(get_config("num_teams", default=0))
                    num_teams = Teams.query.filter_by(
                        banned=False, hidden=False
                    ).count()
                    if num_teams_limit and num_teams >= num_teams_limit:
                        abort(
                            403,
                            description=f"Reached the maximum number of teams ({num_teams_limit}). Please join an existing team.",
                        )

                    team = Teams(name=team_name, oauth_id=team_id, captain_id=user.id)
                    db.session.add(team)
                    db.session.commit()
                    clear_team_session(team_id=team.id)

                team_size_limit = get_config("team_size", default=0)
                if team_size_limit and len(team.members) >= team_size_limit:
                    plural = "" if team_size_limit == 1 else "s"
                    size_error = "Teams are limited to {limit} member{plural}.".format(
                        limit=team_size_limit, plural=plural
                    )
                    error_for(endpoint="auth.login", message=size_error)
                    return redirect(url_for("auth.login"))

                team.members.append(user)
                db.session.commit()

            if user.oauth_id is None:
                user.oauth_id = user_id
                user.verified = True
                db.session.commit()
                clear_user_session(user_id=user.id)

            login_user(user)
            return redirect(url_for("challenges.listing"))
        else:
            log("logins", "[{date}] {ip} - OAuth token retrieval failure")
            error_for(endpoint="auth.login", message="OAuth token retrieval failure.")
            return redirect(url_for("auth.login"))
    else:
        log("logins", "[{date}] {ip} - Received redirect without OAuth code")
        error_for(
            endpoint="auth.login", message="Received redirect without OAuth code."
        )
        return redirect(url_for("auth.login"))


@auth.route("/logout")
def logout():
    if current_user.authed():
        logout_user()
    return redirect(url_for("views.static_html"))


```




# CTFd/forms/auth.py:
```
print("AUTH.PY LOADED")

import re
from flask_babel import lazy_gettext as _l
from wtforms import PasswordField, StringField, ValidationError
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired, Regexp, Length, StopValidation

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.forms.users import (
    attach_custom_user_fields,
    attach_registration_code_field,
    attach_user_bracket_field,
    build_custom_user_fields,
    build_registration_code_field,
    build_user_bracket_field,
)
from CTFd.models import Users
from CTFd.utils import get_config

# --- CUSTOM VALIDATOR FUNCTION ---
def aupp_domain_check(form, field):
    print("CUSTOM VALIDATOR EXECUTED")
    email = str(field.data).strip().lower()

    if not email.endswith("@aupp.edu.kh"):
        raise StopValidation(_l("ONLY @aupp.edu.kh emails are allowed!"))

def RegistrationForm(*args, **kwargs):
    print("RegistrationForm factory called")
    class _RegistrationForm(BaseForm):
        name = StringField(
            _l("User Name"),
            validators=[
                InputRequired(),
                Regexp(r'^[a-zA-Z@]+$', message=_l("ONLY letters and @ allowed."))
            ],
            render_kw={"autofocus": True},
        )
        email = EmailField(
            _l("Email"), 
            validators=[
                InputRequired(), 
                aupp_domain_check  # <--- FORCE CHECK HERE
            ]
        )
        password = PasswordField(
            _l("Password"),
            validators=[
                InputRequired(),
                Length(min=5, max=10, message=_l("Must be 5-10 characters."))
            ],
        )
        submit = SubmitField(_l("Submit"))

        def validate_name(self, field):
            if any(char.isdigit() for char in str(field.data)):
                raise ValidationError(_l("Numbers are strictly forbidden."))
            if Users.query.filter_by(name=field.data).first():
                raise ValidationError(_l("Username taken."))

        def validate_email(self, field):
            print("validate_email method executed")
            # Database check only
            email_val = str(field.data).strip().lower()
            if Users.query.filter_by(email=email_val).first():
                raise ValidationError(_l("Email already exists."))

        def validate_password(self, field):
            if not re.search(r"[!@#$%^&*]", str(field.data)):
                raise ValidationError(_l("Must contain at least one symbol."))

        @property
        def extra(self):
            return (
                build_custom_user_fields(self, include_entries=False, blacklisted_items=())
                + build_registration_code_field(self)
                + build_user_bracket_field(self)
            )

    attach_custom_user_fields(_RegistrationForm)
    attach_registration_code_field(_RegistrationForm)
    attach_user_bracket_field(_RegistrationForm)
    return _RegistrationForm(*args, **kwargs)


class LoginForm(BaseForm):
    name = StringField(
        _l("User Name or Email"),
        validators=[InputRequired()],
        render_kw={"autofocus": True},
    )
    password = PasswordField(_l("Password"), validators=[InputRequired()])
    submit = SubmitField(_l("Submit"))


class ConfirmForm(BaseForm):
    submit = SubmitField(_l("Send Confirmation Email"))


class ResetPasswordRequestForm(BaseForm):
    email = EmailField(
        _l("Email"), validators=[InputRequired()], render_kw={"autofocus": True}
    )
    submit = SubmitField(_l("Submit"))


class ResetPasswordForm(BaseForm):
    password = PasswordField(
        _l("Password"), validators=[InputRequired()], render_kw={"autofocus": True}
    )
    submit = SubmitField(_l("Submit"))

```



# register.html:
```
{% extends "base.html" %}
{% block content %}
<style>
  :root {
    --cyan: #00f5ff;
    --magenta: #ff006e;
    --dark-bg: #050208;
  }
  body { background-color: var(--dark-bg); }
  .auth-card {
    max-width: 550px;
    margin: 4rem auto;
    background: rgba(10, 5, 15, 0.9);
    border: 1px solid rgba(0, 245, 255, 0.3);
    padding: 2.5rem;
    border-radius: 8px;
    position: relative;
    box-shadow: 0 0 30px rgba(0, 245, 255, 0.1);
  }
  .auth-card::before {
    content: ""; position: absolute; top: -1px; left: -1px; width: 25px; height: 25px;
    border-top: 2px solid var(--cyan); border-left: 2px solid var(--cyan);
  }
  .auth-card::after {
    content: ""; position: absolute; bottom: -1px; right: -1px; width: 25px; height: 25px;
    border-bottom: 2px solid var(--cyan); border-right: 2px solid var(--cyan);
  }
  .terminal-header { color: var(--cyan); font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
  .form-label { color: var(--cyan); font-family: var(--font-mono); font-size: 0.85rem; text-transform: uppercase; }
  .form-control {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(0, 245, 255, 0.2) !important;
    color: #fff !important;
  }
  .form-control:focus {
    border-color: var(--cyan) !important;
    box-shadow: 0 0 12px rgba(0, 245, 255, 0.2);
  }
  .btn-cyan {
    background: var(--cyan) !important;
    color: #000 !important;
    font-weight: 700;
    border: none;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    transition: all 0.2s ease;
  }
  .btn-cyan:hover {
    background: #00e0ff !important;
    box-shadow: 0 0 20px rgba(0, 245, 255, 0.4);
    transform: translateY(-1px);
  }
  .form-text { color: rgba(0, 245, 255, 0.5) !important; font-size: 0.75rem; }
</style>

<div class="container">
  <div class="auth-card">
    <div class="text-center mb-4">
      <h2 class="terminal-header">{% trans %}REGISTER{% endtrans %}</h2>
      <small class="text-muted d-block mt-2">-- RECRUITMENT PROTOCOL --</small>
    </div>

    {% include "components/errors.html" %}

    {# Pulled from old register.html: MLC OAuth button shown when integration is active #}
    {% if integrations.mlc() %}
      <a class="btn btn-secondary btn-lg btn-block w-100 mb-3" href="{{ url_for('auth.oauth_login') }}">
        Login with Major League Cyber
      </a>
      <hr style="border-color: rgba(0, 245, 255, 0.2);">
    {% endif %}

    {% with form = Forms.auth.RegistrationForm() %}
      {# Pulled from old register.html: needed to render registration_code and any
         other admin-configured extra fields (the macro handles them all together) #}
      {% from "macros/forms.html" import render_extra_fields %}

      <form method="post" accept-charset="utf-8">
        {# Pulled from old register.html: use form.nonce() instead of manual Session.nonce
           so Flask-WTF generates and validates the token correctly #}
        {{ form.nonce() }}

        <div class="mb-3">
          <b><label class="form-label" for="name">User Name</label> <span class="text-danger">*</span></b>
          <input class="form-control" id="name" name="name" type="text" value="{{ name or '' }}" autocomplete="username" required>
          <small class="form-text">DELETE ME cannot contain numbers.</small>
        </div>

        <div class="mb-3">
          <b><label class="form-label" for="email">Email Address</label> <span class="text-danger">*</span></b>
          <input class="form-control" id="email" name="email" type="email" value="{{ email or '' }}" autocomplete="email" required>
          <small class="form-text">Must be an @aupp.edu.kh address.</small>
        </div>

        <div class="mb-3">
          <b><label class="form-label" for="password">Password</label> <span class="text-danger">*</span></b>
          <input class="form-control" id="password" name="password" type="password" autocomplete="new-password" required>
          <small class="form-text">5-10 chars. Must include a symbol (!@#$%^&*).</small>
        </div>

        {# Pulled from old register.html: renders the registration_code input box and
           any other extra fields the admin configured under CTFd settings.
           Without this line, the registration code field never appears in the UI
           even when an admin has set a required registration code. #}
        {{ render_extra_fields(form.extra) }}

        {% if registration_fields %}
          {% for field in registration_fields %}
            <div class="mb-3">
              <b><label class="form-label" for="fields[{{ field.id }}]">{{ field.name }}</label></b>
              {% if field.description %}
                <small class="d-block text-muted mb-1">{{ field.description }}</small>
              {% endif %}
              <input class="form-control" id="fields[{{ field.id }}]" name="fields[{{ field.id }}]" type="text">
            </div>
          {% endfor %}
        {% endif %}

        <div class="mt-4">
          <button type="submit" class="btn btn-cyan w-100 py-2">Initialize Profile</button>
        </div>

        {# Pulled from old register.html: show ToS/privacy policy links when the
           admin has configured them under CTFd settings #}
        {% if Configs.tos_or_privacy %}
          <div class="row pt-3">
            <div class="col-md-12 text-center">
              <small class="form-text text-center">
                {% trans trimmed privacy_link=Configs.privacy_link, tos_link=Configs.tos_link %}
                By registering, you agree to the
                <a href="{{ privacy_link }}" target="_blank" style="color: var(--cyan);">privacy policy</a>
                and <a href="{{ tos_link }}" target="_blank" style="color: var(--cyan);">terms of service</a>
                {% endtrans %}
              </small>
            </div>
          </div>
        {% endif %}

      </form>
    {% endwith %}

  </div>
</div>
{% endblock %}

```




















