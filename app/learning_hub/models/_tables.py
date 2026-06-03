"""Learning Hub SQLAlchemy models (prefixed tables learn_*)."""

from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class LearnSchool(db.Model):
    __tablename__ = "learn_schools"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(128), unique=True, nullable=False, index=True)
    region = db.Column(db.String(120), nullable=True)
    meta_data = db.Column(db.JSON, nullable=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    join_code = db.Column(db.String(32), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnSchoolMember(db.Model):
    __tablename__ = "learn_school_members"

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey("learn_schools.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(32), nullable=False, default="student")  # student | educator | school_admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("school_id", "learner_id", name="uq_learn_school_member"),)


class LearnLearner(db.Model):
    __tablename__ = "learn_learners"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    full_name = db.Column(db.String(160), nullable=False, default="")
    bio = db.Column(db.Text, nullable=True)
    avatar_url = db.Column(db.String(512), nullable=True)

    # Education band + personalization
    category = db.Column(db.String(24), nullable=False, default="secondary")  # primary | secondary | tertiary
    age_band = db.Column(db.String(16), nullable=False, default="13-15")  # 6-8, 9-12, ...
    skill_level = db.Column(db.String(24), nullable=False, default="beginner")

    learner_role = db.Column(db.String(32), nullable=False, default="student")  # student | mentor

    email_verified_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    total_xp = db.Column(db.Integer, nullable=False, default=0)
    streak_days = db.Column(db.Integer, nullable=False, default=0)
    last_activity_at = db.Column(db.DateTime, nullable=True)

    # Guardian pairing (short-lived code shown to learner)
    pairing_code = db.Column(db.String(16), nullable=True, index=True)
    pairing_expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class LearnGuardianAccount(db.Model):
    __tablename__ = "learn_guardian_accounts"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(160), nullable=False, default="")
    guardian_role = db.Column(db.String(32), nullable=False, default="parent")  # parent | teacher
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


learn_guardian_learners = db.Table(
    "learn_guardian_learners",
    db.Column("guardian_id", db.Integer, db.ForeignKey("learn_guardian_accounts.id", ondelete="CASCADE"), primary_key=True),
    db.Column("learner_id", db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), primary_key=True),
    db.Column("relationship", db.String(64), nullable=True),
)

LearnGuardianAccount.learners = db.relationship(
    "LearnLearner",
    secondary=learn_guardian_learners,
    back_populates="guardians",
)
LearnLearner.guardians = db.relationship(
    "LearnGuardianAccount",
    secondary=learn_guardian_learners,
    back_populates="learners",
)


class LearnLearningTrack(db.Model):
    __tablename__ = "learn_learning_tracks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    difficulty = db.Column(db.String(32), nullable=False, default="beginner")
    category = db.Column(db.String(64), nullable=False, index=True)
    estimated_duration_minutes = db.Column(db.Integer, nullable=True)

    badge_reward_id = db.Column(db.Integer, db.ForeignKey("learn_badges.id", ondelete="SET NULL"), nullable=True)
    certificate_reward_id = db.Column(db.Integer, nullable=True)  # future FK to certificate template

    suitable_age_bands = db.Column(db.JSON, nullable=True)  # list of bands
    suitable_skill_levels = db.Column(db.JSON, nullable=True)

    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnTrackChallenge(db.Model):
    __tablename__ = "learn_track_challenges"

    id = db.Column(db.Integer, primary_key=True)
    track_id = db.Column(db.Integer, db.ForeignKey("learn_learning_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    unlock_after_challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (db.UniqueConstraint("track_id", "challenge_id", name="uq_learn_track_challenge"),)


class LearnLearnerTrackProgress(db.Model):
    __tablename__ = "learn_learner_track_progress"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    track_id = db.Column(db.Integer, db.ForeignKey("learn_learning_tracks.id", ondelete="CASCADE"), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="active")  # active | completed | paused
    percent_complete = db.Column(db.Float, nullable=False, default=0.0)
    last_challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="SET NULL"), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint("learner_id", "track_id", name="uq_learn_learner_track"),)

    track = db.relationship("LearnLearningTrack", backref=db.backref("learner_progress_rows", lazy="dynamic"))


class LearnMiniGame(db.Model):
    __tablename__ = "learn_minigames"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    client_bundle = db.Column(db.String(128), nullable=False, default="default")  # static asset key
    config_json = db.Column(db.JSON, nullable=True)
    max_score = db.Column(db.Integer, nullable=False, default=100)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnChallenge(db.Model):
    __tablename__ = "learn_challenges"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    challenge_category = db.Column(db.String(64), nullable=False, index=True)  # Python, AI, ...
    challenge_type = db.Column(db.String(48), nullable=False, index=True)  # quiz | coding | minigame | ...
    difficulty = db.Column(db.String(32), nullable=False, default="beginner")

    base_points = db.Column(db.Integer, nullable=False, default=10)
    time_limit_seconds = db.Column(db.Integer, nullable=True)

    suitable_categories = db.Column(db.JSON, nullable=True)
    suitable_age_bands = db.Column(db.JSON, nullable=True)
    suitable_skill_levels = db.Column(db.JSON, nullable=True)

    instructions = db.Column(db.Text, nullable=True)
    hints_json = db.Column(db.JSON, nullable=True)
    content_json = db.Column(db.JSON, nullable=True)  # coding tests, misc metadata

    prerequisite_challenge_ids = db.Column(db.JSON, nullable=True)
    required_level = db.Column(db.Integer, nullable=True)
    required_badge_ids = db.Column(db.JSON, nullable=True)

    mini_game_id = db.Column(db.Integer, db.ForeignKey("learn_minigames.id", ondelete="SET NULL"), nullable=True)

    expected_output = db.Column(db.Text, nullable=True)

    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LearnQuestion(db.Model):
    __tablename__ = "learn_questions"

    id = db.Column(db.Integer, primary_key=True)
    stem = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(32), nullable=False, default="mcq")
    difficulty = db.Column(db.String(32), nullable=False, default="beginner")
    age_band = db.Column(db.String(16), nullable=True)
    skill_level = db.Column(db.String(24), nullable=True)
    explanation = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnQuestionOption(db.Model):
    __tablename__ = "learn_question_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("learn_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    text = db.Column(db.String(512), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)


class LearnChallengeQuestion(db.Model):
    __tablename__ = "learn_challenge_questions"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("learn_questions.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    points_override = db.Column(db.Integer, nullable=True)
    randomize_group = db.Column(db.String(64), nullable=True)

    __table_args__ = (db.UniqueConstraint("challenge_id", "question_id", name="uq_learn_challenge_question"),)


class LearnChallengeAttempt(db.Model):
    __tablename__ = "learn_challenge_attempts"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="CASCADE"), nullable=False, index=True)

    attempt_no = db.Column(db.Integer, nullable=False, default=1)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=True)
    time_spent_ms = db.Column(db.Integer, nullable=True)

    score = db.Column(db.Float, nullable=True)
    max_score = db.Column(db.Float, nullable=True)
    passed = db.Column(db.Boolean, nullable=False, default=False)

    payload_json = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="submitted")  # in_progress | submitted | graded | void

    ip_hash = db.Column(db.String(64), nullable=True)
    first_attempt_bonus_applied = db.Column(db.Boolean, nullable=False, default=False)
    xp_awarded = db.Column(db.Integer, nullable=False, default=0)

    meta_json = db.Column(db.JSON, nullable=True)


class LearnMiniGameSession(db.Model):
    __tablename__ = "learn_minigame_sessions"

    id = db.Column(db.Integer, primary_key=True)
    mini_game_id = db.Column(db.Integer, db.ForeignKey("learn_minigames.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    nonce = db.Column(db.String(64), nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)


class LearnMiniGameScore(db.Model):
    __tablename__ = "learn_minigame_scores"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("learn_minigame_sessions.id", ondelete="CASCADE"), nullable=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    mini_game_id = db.Column(db.Integer, db.ForeignKey("learn_minigames.id", ondelete="CASCADE"), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    raw_payload_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnTeam(db.Model):
    __tablename__ = "learn_teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    total_score = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnTeamMember(db.Model):
    __tablename__ = "learn_team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("learn_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(32), nullable=False, default="member")  # captain | member

    __table_args__ = (db.UniqueConstraint("team_id", "learner_id", name="uq_learn_team_member"),)


class LearnTeamInvitation(db.Model):
    __tablename__ = "learn_team_invitations"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("learn_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnHackathonEvent(db.Model):
    __tablename__ = "learn_events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    rules = db.Column(db.Text, nullable=True)
    deadline_at = db.Column(db.DateTime, nullable=True)
    judging_criteria_json = db.Column(db.JSON, nullable=True)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnEventSubmission(db.Model):
    __tablename__ = "learn_event_submissions"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("learn_events.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey("learn_teams.id", ondelete="SET NULL"), nullable=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="SET NULL"), nullable=True)

    title = db.Column(db.String(255), nullable=False)
    artifact_storage_key = db.Column(db.String(512), nullable=True)
    artifact_meta_json = db.Column(db.JSON, nullable=True)

    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnBadge(db.Model):
    __tablename__ = "learn_badges"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon_url = db.Column(db.String(512), nullable=True)


class LearnLearnerBadge(db.Model):
    __tablename__ = "learn_learner_badges"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_id = db.Column(db.Integer, db.ForeignKey("learn_badges.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("learner_id", "badge_id", name="uq_learn_learner_badge"),)


class LearnAchievement(db.Model):
    __tablename__ = "learn_achievements"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=True)


class LearnAchievementRule(db.Model):
    __tablename__ = "learn_achievement_rules"

    id = db.Column(db.Integer, primary_key=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey("learn_achievements.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_type = db.Column(db.String(64), nullable=False, index=True)
    params_json = db.Column(db.JSON, nullable=True)


class LearnLearnerAchievement(db.Model):
    __tablename__ = "learn_learner_achievements"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = db.Column(db.Integer, db.ForeignKey("learn_achievements.id", ondelete="CASCADE"), nullable=False, index=True)
    earned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    snapshot_json = db.Column(db.JSON, nullable=True)

    __table_args__ = (db.UniqueConstraint("learner_id", "achievement_id", name="uq_learn_learner_achievement"),)


class LearnChallengeComment(db.Model):
    __tablename__ = "learn_challenge_comments"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="SET NULL"), nullable=True)
    body = db.Column(db.Text, nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnChallengeRating(db.Model):
    __tablename__ = "learn_challenge_ratings"

    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey("learn_challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    stars = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("challenge_id", "learner_id", name="uq_learn_challenge_rating"),)


class LearnAdminAuditLog(db.Model):
    __tablename__ = "learn_admin_audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_staff_user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(128), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    before_json = db.Column(db.JSON, nullable=True)
    after_json = db.Column(db.JSON, nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnNotification(db.Model):
    __tablename__ = "learn_notifications"

    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("learn_learners.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(64), nullable=False)
    body = db.Column(db.String(512), nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LearnLeaderboardSnapshot(db.Model):
    __tablename__ = "learn_leaderboard_snapshots"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(64), nullable=False, index=True)  # global_xp_week | school_1_xp_month | ...
    window_started_at = db.Column(db.DateTime, nullable=False)
    window_ended_at = db.Column(db.DateTime, nullable=False)
    ranks_json = db.Column(db.JSON, nullable=False)
    computed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

