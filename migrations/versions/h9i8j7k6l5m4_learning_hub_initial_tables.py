"""learning hub initial tables

Revision ID: h9i8j7k6l5m4
Revises: a8b2c3d4e5f6
Create Date: 2026-05-20

Creates all `learn_*` tables from SQLAlchemy models (checkfirst for idempotency).
"""

from alembic import op
from sqlalchemy.schema import Table


revision = "h9i8j7k6l5m4"
down_revision = "a8b2c3d4e5f6"
branch_labels = None
depends_on = None


def _create(bind, obj):
    if isinstance(obj, Table):
        obj.create(bind, checkfirst=True)
    else:
        obj.__table__.create(bind, checkfirst=True)


def _drop(bind, obj):
    if isinstance(obj, Table):
        obj.drop(bind, checkfirst=True)
    else:
        obj.__table__.drop(bind, checkfirst=True)


def upgrade():
    bind = op.get_bind()

    # Import registers metadata with Flask db
    from app.learning_hub.models import _tables as t

    _create_order = [
        t.LearnSchool,
        t.LearnLearner,
        t.LearnGuardianAccount,
        t.learn_guardian_learners,
        t.LearnBadge,
        t.LearnAchievement,
        t.LearnMiniGame,
        t.LearnChallenge,
        t.LearnLearningTrack,
        t.LearnQuestion,
        t.LearnQuestionOption,
        t.LearnChallengeQuestion,
        t.LearnTrackChallenge,
        t.LearnLearnerTrackProgress,
        t.LearnChallengeAttempt,
        t.LearnMiniGameSession,
        t.LearnMiniGameScore,
        t.LearnTeam,
        t.LearnTeamMember,
        t.LearnTeamInvitation,
        t.LearnHackathonEvent,
        t.LearnEventSubmission,
        t.LearnLearnerBadge,
        t.LearnAchievementRule,
        t.LearnLearnerAchievement,
        t.LearnChallengeComment,
        t.LearnChallengeRating,
        t.LearnAdminAuditLog,
        t.LearnNotification,
        t.LearnLeaderboardSnapshot,
        t.LearnSchoolMember,
    ]

    for obj in _create_order:
        _create(bind, obj)


def downgrade():
    bind = op.get_bind()
    from app.learning_hub.models import _tables as t

    _drop_order = [
        t.LearnSchoolMember,
        t.LearnLeaderboardSnapshot,
        t.LearnNotification,
        t.LearnAdminAuditLog,
        t.LearnChallengeRating,
        t.LearnChallengeComment,
        t.LearnLearnerAchievement,
        t.LearnAchievementRule,
        t.LearnLearnerBadge,
        t.LearnEventSubmission,
        t.LearnHackathonEvent,
        t.LearnTeamInvitation,
        t.LearnTeamMember,
        t.LearnTeam,
        t.LearnMiniGameScore,
        t.LearnMiniGameSession,
        t.LearnChallengeAttempt,
        t.LearnLearnerTrackProgress,
        t.LearnTrackChallenge,
        t.LearnChallengeQuestion,
        t.LearnQuestionOption,
        t.LearnQuestion,
        t.LearnLearningTrack,
        t.LearnChallenge,
        t.LearnMiniGame,
        t.LearnAchievement,
        t.LearnBadge,
        t.learn_guardian_learners,
        t.LearnGuardianAccount,
        t.LearnLearner,
        t.LearnSchool,
    ]

    for obj in _drop_order:
        _drop(bind, obj)
