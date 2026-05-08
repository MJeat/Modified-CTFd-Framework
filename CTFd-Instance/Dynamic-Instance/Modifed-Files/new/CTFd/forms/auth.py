import re
from flask_babel import lazy_gettext as _l
from wtforms import PasswordField, StringField, ValidationError
from wtforms.fields.html5 import EmailField
from wtforms.validators import InputRequired, Regexp, Length

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


def RegistrationForm(*args, **kwargs):
    # Description for the UI based on your specific requirements
    password_description = _l("Password must be 5-10 characters and contain at least 1 symbol")

    class _RegistrationForm(BaseForm):
        name = StringField(
            _l("User Name"),
            description="Letters, numbers, and @ only",
            validators=[
                InputRequired(),
				# STRICT REGEX: ONLY Letters and @. No numbers, no spaces, no other signs.
                Regexp(r'^[a-zA-Z@]+$', message=_l("ONLY letters and @ allowed. No numbers."))
            ],
            render_kw={"autofocus": True},
        )
        email = EmailField(
            _l("Email"),
            description="Must be @aupp.edu.kh address",
            validators=[InputRequired()],
        )
        password = PasswordField(
            _l("Password"),
            description=password_description,
            validators=[
                InputRequired(),
                # Length filter: 5 to 10
                Length(min=5, max=10, message=_l("Password must be between 5 and 10 characters"))
            ],
        )
        submit = SubmitField(_l("Submit"))

        # Check if Username is taken
        def validate_name(self, field):
            # Double check: ensure no digits are in the string at all
            if any(char.isdigit() for char in field.data):
                raise ValidationError(_l("Numbers are strictly prohibited in usernames."))
            if Users.query.filter_by(name=field.data).first():
                raise ValidationError(_l("This username is already taken"))

        # Domain Filter & Check if Email is taken
        def validate_email(self, field):
            # FORCE logic: convert to string, strip, and lowercase
            val = str(field.data).strip().lower()
            if not val.endswith("@aupp.edu.kh"):
                # StopValidation prevents the form from even trying to hit the DB
                raise StopValidation(_l("ONLY @aupp.edu.kh emails are accepted."))
            
            if Users.query.filter_by(email=val).first():
                raise ValidationError(_l("This email is already registered"))

        # Detect at least 1 symbol in password
        def validate_password(self, field):
            # Password must contain at least one symbol
            if not re.search(r"[!@#$%^&*,.]", field.data):
                raise ValidationError(_l("Password must contain at least one symbol"))
        @property
        def extra(self):
            return (
                build_custom_user_fields(
                    self, include_entries=False, blacklisted_items=()
                )
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
