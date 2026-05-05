from datetime import datetime

from app import db


class Curriculum(db.Model):
    __tablename__ = "new_creations_curriculums"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    creator = db.relationship("User", foreign_keys=[created_by])

    grades = db.relationship(
        "Grade",
        backref="curriculum",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Grade(db.Model):
    __tablename__ = "new_creations_grades"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    curriculum_id = db.Column(
        db.Integer,
        db.ForeignKey("new_creations_curriculums.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    subjects = db.relationship(
        "Subject",
        backref="grade",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Subject(db.Model):
    __tablename__ = "new_creations_subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    grade_id = db.Column(
        db.Integer,
        db.ForeignKey("new_creations_grades.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topics = db.relationship(
        "TopicLesson",
        backref="subject",
        lazy=True,
        cascade="all, delete-orphan",
    )


class TopicLesson(db.Model):
    __tablename__ = "new_creations_topic_lessons"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("new_creations_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    content = db.Column(db.Text, nullable=True)
    questions = db.Column(db.Text, nullable=True)
    objectives = db.Column(db.Text, nullable=True)
    detailed_objectives = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    creator = db.relationship("User", foreign_keys=[created_by])
