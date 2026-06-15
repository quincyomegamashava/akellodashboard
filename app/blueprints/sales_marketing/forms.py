"""WTForms for Sales & Marketing."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DateField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional

from app.blueprints.sales_marketing.services import HEARD_ABOUT_OPTIONS, ROLE_CATEGORIES, ZIMBABWE_PROVINCES


class PublicStakeholderForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(max=255)])
    occupation = StringField("Occupation", validators=[DataRequired(), Length(max=255)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    mobile = StringField("Mobile", validators=[DataRequired(), Length(max=64)])
    province = SelectField(
        "Province",
        choices=[("", "Select province…")] + [(p, p) for p in ZIMBABWE_PROVINCES],
        validators=[Optional()],
    )
    school_name = StringField("School", validators=[Optional(), Length(max=255)])
    organization = StringField("Organization", validators=[Optional(), Length(max=255)])
    role_category = SelectField(
        "Role",
        choices=[("", "Select…")] + [(r, r) for r in ROLE_CATEGORIES],
        validators=[Optional()],
    )
    event_date = DateField("Event date", validators=[Optional()])
    event_id = SelectField("Event", coerce=int, validators=[Optional()])
    interest_option_id = SelectField("Interest", coerce=int, validators=[DataRequired()])
    preferred_contact = SelectField(
        "Preferred contact",
        choices=[("email", "Email"), ("phone", "Phone"), ("whatsapp", "WhatsApp")],
        validators=[Optional()],
    )
    heard_about = SelectField(
        "How did you hear about us?",
        choices=[("", "Select…")] + [(h, h) for h in HEARD_ABOUT_OPTIONS],
        validators=[Optional()],
    )
    comments = TextAreaField("Comments", validators=[Optional(), Length(max=2000)])
    consent_marketing = BooleanField(
        "I agree to receive information from Akello",
        validators=[DataRequired()],
    )
    website = StringField("Website")  # honeypot
    submit = SubmitField("Submit")


class MarketingEventForm(FlaskForm):
    name = StringField("Event name", validators=[DataRequired(), Length(max=255)])
    start_date = DateField("Start date", validators=[DataRequired()])
    end_date = DateField("End date", validators=[DataRequired()])
    location = StringField("Location", validators=[Optional(), Length(max=255)])
    status = SelectField(
        "Status",
        choices=[("active", "Active"), ("cancelled", "Cancelled")],
        validators=[DataRequired()],
    )
    notes = TextAreaField("Notes", validators=[Optional()])
    submit = SubmitField("Save")
