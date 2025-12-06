from flask_wtf import FlaskForm
from wtforms import DateField, DateTimeField, DateTimeLocalField, IntegerField, SelectMultipleField, StringField, PasswordField, BooleanField, SubmitField, SelectField, TextAreaField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Optional, NumberRange
import sqlalchemy as sa
from app import db
from app.models import User, ChampionSchool
from flask_wtf.file import FileField, FileAllowed
from wtforms import ValidationError



from wtforms.widgets import ListWidget, CheckboxInput

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class ChampionSchoolForm(FlaskForm):
    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    province = StringField('Province', validators=[DataRequired()])
    # schools = SelectMultipleField('Schools', validators=[Optional()], coerce=int, render_kw={"id": "school-select"})
    submit = SubmitField('Add to Champion')

class ChampionCSVUploadForm(FlaskForm):
    file = FileField('Upload CSV', validators=[DataRequired(), FileAllowed(['csv'], 'CSV files only!')])
    submit = SubmitField('Upload')


class CSVUploadForm(FlaskForm):
    csv_file = FileField('Upload CSV', validators=[
        DataRequired(),
        FileAllowed(['csv'], 'CSV files only!')
    ])
    submit = SubmitField('Upload CSV')



class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    
    # --- New Fields Added Below ---

    firstname = StringField('First Name', validators=[DataRequired()])
    lastname = StringField('Last Name', validators=[DataRequired()])
    
    # A dropdown/select field is good for predefined roles
    userRole = SelectField('Role', choices=[
        ('Brand Ambassador', 'Brand Ambassador'), 
        ('Manager', 'Manager'), 
        ('Software Engineer', 'Software Engineer'), 
        ('DevOps Engineer', 'DevOps Engineer'),
        ('Content Acquisition', 'Content Acquisition'),
        ('Brand Manager', 'Brand Manager'),
        ('Admin', 'Admin')
    ], validators=[DataRequired()])
    
    department = SelectField('Department', choices=[
        ('Sales & Marketing', 'Sales & Marketing'),
        ('Product development', 'Product development'),
        ('Brand Management', 'Brand Management'),
        ('Content development', 'Content development')
    ], validators=[DataRequired()])
    
    province = SelectField('Province', choices=[
        ('Harare', 'Harare'),
        ('Bulawayo', 'Bulawayo'),
        ('Manicaland', 'Manicaland'),
        ('Mashonaland Central', 'Mashonaland Central'),
        ('Mashonaland East', 'Mashonaland East'),
        ('Mashonaland West', 'Mashonaland West'),
        ('Masvingo', 'Masvingo'),
        ('Matabeleland North', 'Matabeleland North'),
        ('Matabeleland South', 'Matabeleland South'),
        ('Midlands', 'Midlands')
    ], validators=[DataRequired()])

    submit = SubmitField('Register')

    # --- Validation methods to prevent duplicate username/email ---

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')
        




class EventForm(FlaskForm):
    title = StringField('Event Title', validators=[DataRequired()])
    
    start_date = DateTimeLocalField(
        'Start Date & Time',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}
    )
    
    end_date = DateTimeLocalField(
        'End Date & Time',
        format='%Y-%m-%dT%H:%M',
        validators=[DataRequired()],
        render_kw={"type": "datetime-local"}
    )

    status = SelectField('Status', choices=[
        ('Confirmed', 'Confirmed'),
        ('Not Confirmed', 'Not Confirmed'),
        ('In Progress', 'In Progress'),
        ('Event Ended', 'Event Ended')
    ])
    request_collateral = BooleanField('Request Collateral?')
    submit = SubmitField('Submit')





class BookAllocationForm(FlaskForm):
    school_name = StringField('School Name', validators=[DataRequired()])
    school_province = SelectField(('School Province'), choices=[('Harare','Harare'), ('Bulawayo','Bulawayo'), ('Manicaland','Manicaland'), ('Mashonaland Central','Mashonaland Central'), ('Mashonaland East','Mashonaland East'), ('Mashonaland West','Mashonaland West'), ('Masvingo','Masvingo'), ('Matabeleland North','Matabeleland North'), ('Matabeleland South','Matabeleland South'), ('Midlands','Midlands')], validators=[DataRequired()])
    books_allocated = SelectMultipleField(
        'Books Allocated',
        choices=[
            ('N/A', 'N/A'),('Grade4', 'Grade 4'), ('Grade5', 'Grade 5'), ('Grade6', 'Grade 6'), ('Grade7', 'Grade 7'),
            ('Form1', 'Form 1'), ('Form2', 'Form 2'), ('Form3', 'Form 3'), ('Form4', 'Form 4'),
            ('Form5', 'Form 5'), ('Form6', 'Form 6')
        ],
        validators=[DataRequired()]
    )
    # allocated_by = StringField('Allocated By', validators=[DataRequired()])
    submit = SubmitField('Submit')


class BookAllocationRequestForm(FlaskForm):
    school_name = StringField('School Name', validators=[DataRequired()])
    school_province = SelectField(
        'School Province',
        choices=[
            ('Harare', 'Harare'), ('Bulawayo', 'Bulawayo'), ('Manicaland', 'Manicaland'),
            ('Mashonaland Central', 'Mashonaland Central'), ('Mashonaland East', 'Mashonaland East'),
            ('Mashonaland West', 'Mashonaland West'), ('Masvingo', 'Masvingo'),
            ('Matabeleland North', 'Matabeleland North'), ('Matabeleland South', 'Matabeleland South'),
            ('Midlands', 'Midlands')
        ],
        validators=[DataRequired()]
    )
    school_grade = SelectField(
        'School Grade',
        choices=[
            ('Grade4', 'Grade 4'), ('Grade5', 'Grade 5'), ('Grade6', 'Grade 6'), ('Grade7', 'Grade 7'),
            ('Form1', 'Form 1'), ('Form2', 'Form 2'), ('Form3', 'Form 3'), ('Form4', 'Form 4'),
            ('Form5', 'Form 5'), ('Form6', 'Form 6')
        ],
        validators=[DataRequired()]
    )
    quantity = IntegerField('Quantity', validators=[DataRequired()], default=1)
    notes = TextAreaField('Notes (Optional)', validators=[])
    requested_date = DateField('Requested Date (Optional)', validators=[])
    submit = SubmitField('Submit Request')


class ReportForm(FlaskForm):
    # department = SelectField("Department", choices=[
    #     ('Sales & Marketing', 'Sales & Marketing'),
    #     ('Product development', 'Product development'),
    #     ('Content development', 'Content development')
    # ], validators=[DataRequired()])
    this_week = TextAreaField("What you worked on this week", validators=[DataRequired()])
    next_week = TextAreaField("What you'll work on next week", validators=[DataRequired()])
    submit = SubmitField("Submit Report")


class WorkspaceForm(FlaskForm):
    name = StringField('Workspace Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Create Workspace')

class ProjectForm(FlaskForm):
    title = StringField('Project Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    status = SelectField('Status', choices=[('Not Started', 'Not Started'), ('In Progress', 'In Progress'), ('Completed', 'Completed')])
    start_date = DateField('Start Date', validators=[Optional()]) # Make optional if not always required
    end_date = DateField('End Date', validators=[Optional()])     # Make optional if not always required
    submit = SubmitField('Create Project')

    # Optional: Add a custom validator for start_date vs end_date
    def validate_end_date(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError('End date cannot be before start date.')


class TaskForm(FlaskForm):
    title = StringField('Task Title', validators=[DataRequired()])
    description = TextAreaField('Description')
    start_date = DateField('Start Date', validators=[Optional()]) # Make optional if not always required
    due_date = DateField('Due Date', validators=[Optional()])     # Make optional if not always required
    status = SelectField('Status', choices=[('To Do', 'To Do'), ('In Progress', 'In Progress'), ('Done', 'Done')])
    progress = IntegerField('Progress (%)', validators=[
        DataRequired(),
        NumberRange(min=1, max=100, message='Progress must be between 0 and 100.')
    ], default=1) # Set default for form, though model handles database default
    # ----------------------------------
    submit = SubmitField('Create Task')

    # Add a custom validator for start_date vs due_date
    def validate_due_date(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError('End date cannot be before start date.')
        

class HelpDeskForm(FlaskForm):
    query_title = StringField('Query Title', validators=[DataRequired()])
    query_description = TextAreaField('Query Description', validators=[DataRequired()])
    query_type = SelectField('How would you like to log this?', choices=[('anonymous','Anonymous'), ('self','As myself')], validators=[DataRequired()])
    image = FileField('Attach image (optional)', validators=[FileAllowed(['png','jpg','jpeg','gif'], 'Images only!')])
    submit = SubmitField('Submit Query')


class AkelloSimEventForm(FlaskForm):
    calendar_title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    date = DateTimeLocalField('Date & Time', format='%Y-%m-%dT%H:%M', validators=[DataRequired()], render_kw={"type": "datetime-local"})
    status = SelectField('Status', choices=[('Confirmed', 'Confirmed'), ('Cancelled', 'Cancelled')], validators=[DataRequired()])
    request_collateral = BooleanField('Request Collateral?')
    collateral_items = MultiCheckboxField('Collateral Items', choices=[
        ('Branding', 'Branding'),
        ('T-Shirts', 'T-Shirts'),
        ('Diaries', 'Diaries'),
        ('Pens', 'Pens'),
        ('Key Holders', 'Key Holders')
    ], validators=[Optional()])
    submit = SubmitField('Save Event')



    


class PerfomanceTargetsForm(FlaskForm):
    smartlearning_registrations_monthly_target = IntegerField("SL Registrations (Monthly)", validators=[DataRequired(), NumberRange(min=0)])
    smartlearning_registrations_daily_target = IntegerField("SL Registrations (Daily)", validators=[DataRequired(), NumberRange(min=0)])
    smartlearning_unique_subscribers_monthly_target = IntegerField("SL Subscribers (Monthly)", validators=[DataRequired(), NumberRange(min=0)])
    smartlearning_unique_subscribers_daily_target = IntegerField("SL Subscribers (Daily)", validators=[DataRequired(), NumberRange(min=0)])
    ask_akello_users_monthly_target = IntegerField("Ask Akello Users (Monthly)", validators=[DataRequired(), NumberRange(min=0)])
    ask_akello_users_daily_target = IntegerField("Ask Akello Users (Daily)", validators=[DataRequired(), NumberRange(min=0)])
    library_registrations_monthly_target = IntegerField("Library Registrations (Monthly)", validators=[DataRequired(), NumberRange(min=0)])
    library_registrations_daily_target = IntegerField("Library Registrations (Daily)", validators=[DataRequired(), NumberRange(min=0)])
    library_unique_users_monthly_target = IntegerField("Library Unique Users (Monthly)", validators=[DataRequired(), NumberRange(min=0)])
    library_unique_users_daily_target = IntegerField("Library Unique Users (Daily)", validators=[DataRequired(), NumberRange(min=0)])
    overall_active30_target = IntegerField("Overall Active 30 Day Users", validators=[NumberRange(min=0)])
    submit = SubmitField("Save")
