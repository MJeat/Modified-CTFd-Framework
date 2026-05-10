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
