from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login
from hashlib import md5
import json


# Association Table for Workspace Membership
workspace_membership = db.Table('workspace_membership',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('workspace_id', db.Integer, db.ForeignKey('workspace.id'))
)


# Association table for project members
project_membersA = db.Table(
    "project_membersa",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("project_id", db.Integer, db.ForeignKey("projectsa.id"), primary_key=True)
)

# Association table for task assignees (ProjectA/TaskA system)
task_assigneesA = db.Table(
    "task_assigneesa",
    db.Column("task_id", db.Integer, db.ForeignKey("tasksa.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True)
)


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))

    # --- New Fields Added Below ---

    firstname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True)
    lastname: so.Mapped[str] = so.mapped_column(sa.String(64), index=True)
    
    # Role of the user, e.g., 'Admin', 'Teacher', 'Student'
    userRole: so.Mapped[str] = so.mapped_column(sa.String(64), index=True)
    
    # Department the user belongs to, can be optional
    department: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120), index=True)
    
    # Province the user is in, can be optional
    province: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120), index=True)
    
    # Using JSON type for privileges allows storing a list or dictionary
    # e.g., {'can_edit': True, 'can_delete': False}
    privileges: so.Mapped[Optional[dict]] = so.mapped_column(sa.JSON, default={})

    memberships = db.relationship('Workspace', secondary=workspace_membership, back_populates='members')

    # backref to see which projects a user belongs to
    projects = db.relationship("ProjectA", secondary=project_membersA, back_populates="members")
    


    def __repr__(self):
        # You could enhance this to show more info if you like
        # For example: return f'<User {self.username} ({self.firstname} {self.lastname})>'
        return '<User {}>'.format(self.username)
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'
    
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    

    def remove_privilege(self, privilege: str):
        """Remove a privilege from this user."""
        from sqlalchemy.orm.attributes import flag_modified
        if self.privileges and privilege in self.privileges:
            self.privileges[privilege] = False
            # Mark the JSON field as modified so SQLAlchemy tracks the change
            flag_modified(self, 'privileges')
            db.session.commit()

    def get_privileges(self):
        """Ensure all expected privileges exist in dict, default False."""
        all_privs = ["Super-admin", "Manager", "Brand Ambassador", "Read Only", "Higherlife", "Content Development", "Akello Events"]
        if not self.privileges:
            self.privileges = {}
        for p in all_privs:
            if p not in self.privileges:
                self.privileges[p] = False
        return self.privileges

    def has_privilege(self, privilege):
        return self.get_privileges().get(privilege, False)

    def set_privilege(self, privilege, value: bool):
        from sqlalchemy.orm.attributes import flag_modified
        privs = self.get_privileges()
        privs[privilege] = value
        self.privileges = privs
        # Mark the JSON field as modified so SQLAlchemy tracks the change
        flag_modified(self, 'privileges')
        db.session.commit()
    
    
@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))




class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Not Confirmed")
    request_collateral = db.Column(db.Boolean, default=False)
    added_by = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class AkelloSimEvent(db.Model):
    __tablename__ = 'akello_sim_events'

    id = db.Column(db.Integer, primary_key=True)
    calendar_title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Confirmed')  # Confirmed, Cancelled
    created_by = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    request_collateral = db.Column(db.Boolean, default=False)
    collateral_items = db.Column(db.JSON, default=list)  # ["Branding", "T-Shirts", ...]



class BookAllocations(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    school_name = db.Column(db.String(100), nullable=False)
    school_province = db.Column(db.String(100), nullable=False)
    books_allocated = db.Column(db.String(500), nullable=True, default="N/A")
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    allocated_by = db.Column(db.String(100), nullable=True)


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    this_week = db.Column(db.Text, nullable=False)
    next_week = db.Column(db.Text, nullable=False)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)


class WeeklyReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    week_start = db.Column(db.String(20), nullable=False)
    work_done = db.Column(db.Text, nullable=False)
    work_next = db.Column(db.Text, nullable=False)
    challenges = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Workspace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    projects = db.relationship('Project', backref='workspace', lazy=True, cascade="all, delete-orphan")
    members = db.relationship('User', secondary=workspace_membership, back_populates='memberships')
    files = db.relationship('WorkspaceFile', backref='workspace', lazy=True, cascade='all, delete-orphan')
    lessons = db.relationship('Lesson', backref='workspace', lazy=True, cascade='all, delete-orphan')
    activity_questions = db.relationship('ActivityQuestion', backref='workspace', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Workspace {self.name}>'

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('project.id'))  # Subproject support
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='Not Started')
    tasks = db.relationship('Task', backref='project', lazy=True, cascade='all, delete-orphan')


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', ondelete='CASCADE'))
    parent_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    start_date = db.Column(db.DateTime)
    due_date = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='To Do')
    progress = db.Column(db.Integer, default=0) # Percentage from 0 to 100


class WorkspaceFile(db.Model):
    __tablename__ = 'workspace_files'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id', ondelete='CASCADE'), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(512), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id', ondelete='CASCADE'), nullable=False)
    topic = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(120), nullable=True)
    age = db.Column(db.Integer, nullable=False)
    objectives = db.Column(db.JSON, default=list)
    aspects = db.Column(db.JSON, default=list)
    activities = db.Column(db.JSON, default=list)
    images = db.Column(db.JSON, default=list)
    prompt = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActivityQuestion(db.Model):
    __tablename__ = 'activity_questions'
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id', ondelete='CASCADE'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id', ondelete='SET NULL'), nullable=True)
    topic = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(120), nullable=True)
    age_range = db.Column(db.JSON, nullable=True)  # {min_age: int, max_age: int}
    grade_range = db.Column(db.JSON, nullable=True)  # {min_grade: int, max_grade: int}
    ability_levels = db.Column(db.JSON, default=list)  # ["beginner", "intermediate", "advanced"]
    question_type = db.Column(db.String(50), nullable=False, default='mixed')  # multiple_choice, short_answer, essay, mixed
    num_questions = db.Column(db.Integer, nullable=False, default=5)
    prompt = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GameUser(db.Model):
    __tablename__ = 'game_users'
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(64), nullable=False)
    surname = db.Column(db.String(64), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    scores = db.relationship('GameScore', backref='game_user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<GameUser {self.username}>'


class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    html_content = db.Column(db.Text, nullable=False)  # The HTML game code
    max_score = db.Column(db.Integer, nullable=True)  # Maximum possible score (for percentage calculation)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scores = db.relationship('GameScore', backref='game', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Game {self.title}>'


class GameScore(db.Model):
    __tablename__ = 'game_scores'
    id = db.Column(db.Integer, primary_key=True)
    game_user_id = db.Column(db.Integer, db.ForeignKey('game_users.id', ondelete='CASCADE'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=True)  # Store max score at time of attempt
    percentage = db.Column(db.Float, nullable=True)  # Calculated percentage
    attempt_number = db.Column(db.Integer, default=1, nullable=False)  # Which attempt this is for this user+game
    played_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<GameScore User:{self.game_user_id} Game:{self.game_id} Score:{self.score}>'

class Scorecard(db.Model):
    _tablename_ = 'scorecard'

    id = db.Column(db.Integer, primary_key=True)
    key_focus_area = db.Column(db.String(100), nullable=False)
    strategic_objective = db.Column(db.String(200), nullable=False)
    performance_measure = db.Column(db.String(200), nullable=False)
    unit_of_measure = db.Column(db.String(100), nullable=False)
    target = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    employee_name = db.Column(db.String(100), nullable=False)

    def _repr_(self):
        return f'<Scorecard {self.id}>'
    




# ----------------------
# ChampionSchool Model
# ----------------------
class ChampionSchool(db.Model):
    __tablename__ = 'championschools'

    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(100), nullable=False)
    lastname = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(100), nullable=False)
    schools = db.Column(db.Text, nullable=True, default='[]')  # JSON field

    def set_schools(self, school_list):
        self.schools = json.dumps(school_list)

    def get_schools(self):
        if not self.schools:
            return []
        return json.loads(self.schools)

    def add_school(self, asl_id, library_id, school_name):
        schools = self.get_schools()
        schools.append({
            "asl_school_id": asl_id,
            "library_school_id": library_id,
            "school_name": school_name
        })
        self.set_schools(schools)

    def to_dict(self):
        return {
            "id": self.id,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "province": self.province,
            "schools": self.get_schools()
        }





class PerfomanceTargets(db.Model):
    __tablename__ = 'perfomancetargets'

    id = db.Column(db.Integer, primary_key=True)
    smartlearning_registrations_monthly_target = db.Column(db.Integer, default=0)
    smartlearning_registrations_daily_target = db.Column(db.Integer, default=0)
    smartlearning_unique_subscribers_monthly_target = db.Column(db.Integer, default=0)
    smartlearning_unique_subscribers_daily_target = db.Column(db.Integer, default=0)
    ask_akello_users_monthly_target = db.Column(db.Integer, default=0)
    ask_akello_users_daily_target = db.Column(db.Integer, default=0)
    library_registrations_monthly_target = db.Column(db.Integer, default=0)
    library_registrations_daily_target = db.Column(db.Integer, default=0)
    library_unique_users_monthly_target = db.Column(db.Integer, default=0)
    library_unique_users_daily_target = db.Column(db.Integer, default=0)
    overall_active30_target = db.Column(db.Integer,nullable=True, default=0)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    updated_by = db.Column(db.String(100), nullable=False)

    def _repr_(self):
        return f'<PerfomanceTargets {self.id}>'



# new project management


# Association table for project members
# project_members = db.Table(
#     "project_members",
#     db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
#     db.Column("project_id", db.Integer, db.ForeignKey("projectsa.id"), primary_key=True)
# )



class ProjectA(db.Model):
    __tablename__ = "projectsa"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    project_type = db.Column(db.String(20), default="private")  # private / public
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    columns = db.relationship(
        "ColumnA",
        backref="project",
        cascade="all,delete-orphan",
        order_by="ColumnA.position"
    )
    members = db.relationship("User", secondary=project_membersA, back_populates="projects")


class ColumnA(db.Model):
    __tablename__ = "columnsa"
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projectsa.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)  # ordering

    tasks = db.relationship(
        "TaskA",
        backref="column",
        cascade="all,delete-orphan",
        order_by="TaskA.position"
    )


class TaskA(db.Model):
    __tablename__ = "tasksa"
    id = db.Column(db.Integer, primary_key=True)
    column_id = db.Column(db.Integer, db.ForeignKey("columnsa.id"), nullable=False)
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    progress = db.Column(db.Integer, default=0)  # 0–100 (%), optional
    start_date = db.Column(db.DateTime, nullable=True)  # NEW
    end_date = db.Column(db.DateTime, nullable=True)    # NEW
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Many-to-many relationship to users as assignees
    assignees = db.relationship("User", secondary=task_assigneesA, backref="assigned_tasksA")


# ----------------------
# Help Desk Model
# ----------------------
class HelpDeskQuery(db.Model):
    __tablename__ = 'helpdesk_queries'

    id = db.Column(db.Integer, primary_key=True)
    query_title = db.Column(db.String(200), nullable=False)
    query_description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    query_type = db.Column(db.String(20), nullable=False)  # 'anonymous' or 'self'
    created_by = db.Column(db.String(100), nullable=False)
    image_path = db.Column(db.String(255), nullable=True)  # relative path to static file
    status = db.Column(db.String(30), nullable=False, default='Not started')  # Not started, Looking into it, Resolved


# ----------------------
# Branding inventory and requests
# ----------------------
class BrandingItem(db.Model):
    __tablename__ = 'branding_items'
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(40), index=True, nullable=False)  # Code4Kids, Library, Akello AI, Main Brand
    item_type = db.Column(db.String(80), nullable=False)             # e.g., Pop Ups, Teardrops, Gazebo
    quantity_available = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint('platform', 'item_type', name='uq_branding_platform_type'),)

    def to_dict(self):
        return {
            'id': self.id,
            'platform': self.platform,
            'item_type': self.item_type,
            'quantity_available': self.quantity_available,
        }

class BrandingRequest(db.Model):
    __tablename__ = 'branding_requests'
    id = db.Column(db.Integer, primary_key=True)
    requester_username = db.Column(db.String(100), nullable=False)
    event_name = db.Column(db.String(200), nullable=True)
    platform = db.Column(db.String(40), index=True, nullable=False)
    item_type = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    checkout_date = db.Column(db.Date, nullable=True)
    return_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending, Approved, Declined, Return Pending, Returned
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'requester_username': self.requester_username,
            'event_name': self.event_name,
            'platform': self.platform,
            'item_type': self.item_type,
            'quantity': self.quantity,
            'checkout_date': self.checkout_date.isoformat() if self.checkout_date else None,
            'return_date': self.return_date.isoformat() if self.return_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

class BrandingAction(db.Model):
    __tablename__ = 'branding_actions'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('branding_requests.id'), index=True, nullable=False)
    action = db.Column(db.String(30), nullable=False)  # approve, decline, mark_returned, ack_return, decline_return
    actor_username = db.Column(db.String(100), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'action': self.action,
            'actor_username': self.actor_username,
            'comment': self.comment,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class CollateralItems(db.Model):
    __tablename__ = 'collateral_items'
    id = db.Column(db.Integer, primary_key=True)
    collateral_name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='available')  # available or unavailable
    added_by = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'collateral_name': self.collateral_name,
            'status': self.status,
            'added_by': self.added_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class CollateralRequest(db.Model):
    __tablename__ = 'collateral_requests'
    id = db.Column(db.Integer, primary_key=True)
    collateral_item_id = db.Column(db.Integer, db.ForeignKey('collateral_items.id'), nullable=False)
    requester_username = db.Column(db.String(100), nullable=False)
    event_details = db.Column(db.Text, nullable=False)
    needed_by_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending')  # Pending, Approved, Declined
    approved_by = db.Column(db.String(100), nullable=True)
    decline_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to collateral item
    collateral_item = db.relationship('CollateralItems', backref='requests')

    def to_dict(self):
        return {
            'id': self.id,
            'collateral_item_id': self.collateral_item_id,
            'collateral_name': self.collateral_item.collateral_name if self.collateral_item else None,
            'requester_username': self.requester_username,
            'event_details': self.event_details,
            'needed_by_date': self.needed_by_date.isoformat() if self.needed_by_date else None,
            'status': self.status,
            'approved_by': self.approved_by,
            'decline_reason': self.decline_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ----------------------
# User Activity Tracking Models
# ----------------------
class UserActivity(db.Model):
    __tablename__ = 'user_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # Nullable for anonymous users
    username = db.Column(db.String(64), nullable=True)  # Store username for quick access
    session_id = db.Column(db.String(128), nullable=False, index=True)  # Flask session ID
    
    # Activity Details
    activity_type = db.Column(db.String(50), nullable=False)  # 'page_visit', 'api_call', 'form_submit', 'login', 'logout'
    endpoint = db.Column(db.String(100), nullable=False)  # Flask endpoint name
    url_path = db.Column(db.String(500), nullable=False)  # Full URL path
    http_method = db.Column(db.String(10), nullable=False)  # GET, POST, etc.
    
    # Request Details
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.Text, nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    
    # Timing
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    response_time_ms = db.Column(db.Integer, nullable=True)  # Response time in milliseconds
    
    # Additional Data (JSON field for flexible data storage)
    meta_data = db.Column(db.JSON, nullable=True)  # Form data, query params, etc.
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'session_id': self.session_id,
            'activity_type': self.activity_type,
            'endpoint': self.endpoint,
            'url_path': self.url_path,
            'http_method': self.http_method,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'referrer': self.referrer,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'response_time_ms': self.response_time_ms,
            'metadata': self.meta_data
        }

class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(128), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(64), nullable=True)
    
    # Session Details
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    
    # Timing
    first_seen = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_activity_url = db.Column(db.String(500), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'username': self.username,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_activity_url': self.last_activity_url,
            'is_active': self.is_active,
            'duration_minutes': int((self.last_seen - self.first_seen).total_seconds() / 60) if self.first_seen and self.last_seen else 0
        }

    def update_activity(self, url_path):
        """Update the last seen time and URL for this session"""
        self.last_seen = datetime.utcnow()
        self.last_activity_url = url_path
        self.is_active = True
        db.session.commit()

class PageAnalytics(db.Model):
    __tablename__ = 'page_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    url_path = db.Column(db.String(500), nullable=False, index=True)
    endpoint = db.Column(db.String(100), nullable=True)
    
    # Counters
    total_visits = db.Column(db.Integer, default=0)
    unique_visitors = db.Column(db.Integer, default=0)
    
    # Timing
    avg_response_time_ms = db.Column(db.Float, nullable=True)
    last_visited = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'url_path': self.url_path,
            'endpoint': self.endpoint,
            'total_visits': self.total_visits,
            'unique_visitors': self.unique_visitors,
            'avg_response_time_ms': self.avg_response_time_ms,
            'last_visited': self.last_visited.isoformat() if self.last_visited else None
        }

#new project management ends here







