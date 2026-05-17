# filepath: models.py
"""
SkillSwap — Database Models
All models: User, Skill, Exchange, Message, Review, Session, Badge
"""

from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


# ─── Association table for badges ────────────────────────────────────────────
user_badges = db.Table(
    "user_badges",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("badge_id", db.Integer, db.ForeignKey("badge.id"), primary_key=True),
    db.Column("awarded_at", db.DateTime, default=lambda: datetime.now(timezone.utc)),
)


class User(UserMixin, db.Model):
    """User account with extended profile fields."""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, default="")
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.Text, default="")
    city = db.Column(db.String(100), default="")
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), default="")
    avatar_url = db.Column(db.String(256), default="")
    available_from = db.Column(db.String(10), default="09:00")
    available_to = db.Column(db.String(10), default="21:00")
    rating_points = db.Column(db.Float, default=0.0)
    teaching_rating = db.Column(db.Float, default=0.0)
    communication_rating = db.Column(db.Float, default=0.0)
    review_count = db.Column(db.Integer, default=0)
    onboarding_done = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)      # blue checkmark
    referral_code = db.Column(db.String(12), unique=True, nullable=True)
    referred_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Email verification
    email_verified = db.Column(db.Boolean, default=False)
    username = db.Column(db.String(40), unique=True, nullable=True, index=True)
    # Profile view counter
    profile_views = db.Column(db.Integer, default=0)

    # Skill sort order (JSON list of skill IDs)
    skills_order = db.Column(db.Text, default="")

    # API token for external access
    api_token = db.Column(db.String(64), unique=True, nullable=True, index=True)

    # totp_email fields for email-based 2FA code
    totp_email_code = db.Column(db.String(6), nullable=True)
    totp_email_expires = db.Column(db.DateTime, nullable=True)
    email_verify_token = db.Column(db.String(64), nullable=True)

    # Password reset
    reset_token = db.Column(db.String(64), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    # Two-Factor Authentication
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    skills = db.relationship(
        "Skill", back_populates="user", cascade="all, delete-orphan", lazy="dynamic"
    )
    proposed_exchanges = db.relationship(
        "Exchange",
        foreign_keys="Exchange.proposer_id",
        back_populates="proposer",
        lazy="dynamic",
    )
    received_exchanges = db.relationship(
        "Exchange",
        foreign_keys="Exchange.receiver_id",
        back_populates="receiver",
        lazy="dynamic",
    )
    reviews_given = db.relationship(
        "Review", foreign_keys="Review.reviewer_id", back_populates="reviewer", lazy="dynamic"
    )
    reviews_received = db.relationship(
        "Review", foreign_keys="Review.reviewee_id", back_populates="reviewee", lazy="dynamic"
    )
    badges = db.relationship("Badge", secondary=user_badges, back_populates="users", lazy="dynamic")

    def set_password(self, password: str) -> None:
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify password."""
        return check_password_hash(self.password_hash, password)

    def recalculate_rating(self) -> None:
        """Recalculate composite rating_points from exchanges + reviews."""
        completed = Exchange.query.filter(
            (
                (Exchange.proposer_id == self.id) | (Exchange.receiver_id == self.id)
            ),
            Exchange.status == "completed",
        ).count()

        reviews = Review.query.filter_by(reviewee_id=self.id).all()
        avg_review = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0
        teaching_reviews = [r for r in reviews if r.review_type == "teaching"]
        comm_reviews = [r for r in reviews if r.review_type == "communication"]

        self.teaching_rating = (
            sum(r.rating for r in teaching_reviews) / len(teaching_reviews)
            if teaching_reviews
            else 0.0
        )
        self.communication_rating = (
            sum(r.rating for r in comm_reviews) / len(comm_reviews)
            if comm_reviews
            else 0.0
        )
        self.rating_points = completed * 10 + avg_review * 5
        self.review_count = len(reviews)

    def get_skills_offer(self):
        """Return skills the user offers."""
        return self.skills.filter_by(skill_type="offer").all()

    def get_skills_want(self):
        """Return skills the user wants."""
        return self.skills.filter_by(skill_type="want").all()

    def avatar_or_default(self) -> str:
        """Return avatar URL or placeholder."""
        if self.avatar_url:
            return self.avatar_url
        return f"https://ui-avatars.com/api/?name={self.full_name or 'User'}&background=6366f1&color=fff&size=128"

    @property
    def is_banned(self) -> bool:
        ban = getattr(self, "ban_record", None)
        if ban is None:
            return False
        return ban.is_active()

    def pending_reports_count(self) -> int:
        from models import Report
        return Report.query.filter_by(reported_id=self.id, status="pending").count()

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Skill(db.Model):
    """A skill that a user offers or wants to learn."""

    __tablename__ = "skill"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(80), default="")
    subcategory = db.Column(db.String(80), default="")
    level = db.Column(db.String(20), default="beginner")
    skill_type = db.Column(db.String(10), nullable=False)  # 'offer' or 'want'
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", back_populates="skills")
    offered_in = db.relationship(
        "Exchange",
        foreign_keys="Exchange.offered_skill_id",
        back_populates="offered_skill",
        lazy="dynamic",
    )
    requested_in = db.relationship(
        "Exchange",
        foreign_keys="Exchange.requested_skill_id",
        back_populates="requested_skill",
        lazy="dynamic",
    )

    CATEGORIES = [
        "IT та програмування",
        "Дизайн і візуал",
        "Мови та комунікація",
        "Освіта та науки",
        "Бізнес і кар'єра",
        "Маркетинг і контент",
        "Фото, відео та монтаж",
        "Музика і звук",
        "Спорт і здоров'я",
        "Кулінарія і побут",
        "Мистецтво і handmade",
        "Інше",
    ]
    LEVELS = ["beginner", "elementary", "intermediate", "advanced", "expert", "master"]

    def __repr__(self) -> str:
        return f"<Skill {self.title} [{self.skill_type}]>"


class Exchange(db.Model):
    """A skill-exchange proposal between two users."""

    __tablename__ = "exchange"

    id = db.Column(db.Integer, primary_key=True)
    proposer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    offered_skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=True)
    requested_skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=True)
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")  # pending/accepted/rejected/completed
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    proposer = db.relationship(
        "User", foreign_keys=[proposer_id], back_populates="proposed_exchanges"
    )
    receiver = db.relationship(
        "User", foreign_keys=[receiver_id], back_populates="received_exchanges"
    )
    offered_skill = db.relationship(
        "Skill", foreign_keys=[offered_skill_id], back_populates="offered_in"
    )
    requested_skill = db.relationship(
        "Skill", foreign_keys=[requested_skill_id], back_populates="requested_in"
    )
    messages = db.relationship(
        "Message", back_populates="exchange", cascade="all, delete-orphan", lazy="dynamic"
    )
    sessions = db.relationship(
        "Session", back_populates="exchange", cascade="all, delete-orphan", lazy="dynamic"
    )
    reviews = db.relationship(
        "Review", back_populates="exchange", cascade="all, delete-orphan", lazy="dynamic"
    )

    STATUS_LABELS = {
        "pending": ("Очікує", "warning"),
        "accepted": ("Прийнято", "success"),
        "rejected": ("Відхилено", "danger"),
        "completed": ("Завершено", "secondary"),
    }

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, ("Невідомо", "light"))

    def __repr__(self) -> str:
        return f"<Exchange #{self.id} {self.status}>"


class Message(db.Model):
    """Chat message linked to an exchange."""

    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    attachment_url = db.Column(db.String(512), default="")
    attachment_filename = db.Column(db.String(255), default="")
    attachment_mime = db.Column(db.String(120), default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    exchange = db.relationship("Exchange", back_populates="messages")
    sender = db.relationship("User")

    def __repr__(self) -> str:
        return f"<Message #{self.id} exchange={self.exchange_id}>"


class Review(db.Model):
    """Rating + comment left after a completed exchange."""

    __tablename__ = "review"

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1–5
    comment = db.Column(db.Text, default="")
    review_type = db.Column(db.String(20), default="teaching")  # teaching / communication
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    exchange = db.relationship("Exchange", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_given")
    reviewee = db.relationship("User", foreign_keys=[reviewee_id], back_populates="reviews_received")

    def __repr__(self) -> str:
        return f"<Review {self.rating}★ for user#{self.reviewee_id}>"


class Session(db.Model):
    """Scheduled learning session linked to an exchange."""

    __tablename__ = "session"

    id = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    exchange = db.relationship("Exchange", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session #{self.id} at {self.scheduled_at}>"


class Badge(db.Model):
    """Gamification badge."""

    __tablename__ = "badge"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(256), default="")
    icon = db.Column(db.String(10), default="🏅")

    users = db.relationship("User", secondary=user_badges, back_populates="badges", lazy="dynamic")

    DEFINITIONS = [
        {"slug": "first_skill", "name": "Перша навичка", "description": "Додав першу навичку", "icon": "🌱"},
        {"slug": "first_exchange", "name": "Перший обмін", "description": "Завершив перший обмін", "icon": "🤝"},
        {"slug": "experienced", "name": "Досвідчений", "description": "5 завершених обмінів", "icon": "⭐"},
        {"slug": "master", "name": "Майстер", "description": "10 завершених обмінів", "icon": "🏆"},
        {"slug": "top_mentor", "name": "Топ-ментор", "description": "Більше 100 рейтинг-балів", "icon": "🎓"},
    ]

    def __repr__(self) -> str:
        return f"<Badge {self.slug}>"


class Notification(db.Model):
    """In-app notification for a user."""

    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.String(256), default="")
    link = db.Column(db.String(256), default="")
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    # Notification type icons
    ICONS = {
        "exchange_new":      "🤝",
        "exchange_accepted": "✅",
        "exchange_rejected": "❌",
        "exchange_completed":"🏁",
        "review_new":        "⭐",
        "badge_new":         "🏅",
        "message_new":       "💬",
        "agreement_created": "📋",
        "agreement_signed":  "✅",
    }

    def __repr__(self) -> str:
        return f"<Notification #{self.id} user={self.user_id}>"


# ─── Global Reviews (стіна відгуків) ─────────────────────────────────────────

class GlobalReview(db.Model):
    """Platform-wide review wall. Categories: app / user / exchange."""

    __tablename__ = "global_review"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    category = db.Column(db.String(20), nullable=False, default="app")
    # category: 'app' | 'user' | 'exchange'
    rating = db.Column(db.Integer, nullable=False)          # 1–5
    title = db.Column(db.String(120), default="")
    body = db.Column(db.Text, nullable=False)
    is_visible = db.Column(db.Boolean, default=True)        # адмін може приховати
    mentioned_username = db.Column(db.String(42), nullable=True)  # @tag for user reviews
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    author = db.relationship("User", foreign_keys=[author_id],
                             backref=db.backref("global_reviews", lazy="dynamic"))

    CATEGORIES = {
        "app":      ("💬", "Про застосунок"),
        "user":     ("👤", "Про користувача"),
        "exchange": ("🔄", "Про якість обміну"),
    }

    def category_label(self):
        icon, label = self.CATEGORIES.get(self.category, ("📝", self.category))
        return icon, label

    def __repr__(self):
        return f"<GlobalReview #{self.id} [{self.category}]>"


# ─── Reports (жалоби) ─────────────────────────────────────────────────────────

class Report(db.Model):
    """User complaint / report against another user."""

    __tablename__ = "report"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reported_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.String(60), nullable=False)
    # reason: 'spam' | 'abuse' | 'fake' | 'fraud' | 'other'
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")
    # status: 'pending' | 'reviewed' | 'dismissed'
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    reporter = db.relationship("User", foreign_keys=[reporter_id],
                               backref=db.backref("reports_sent", lazy="dynamic"))
    reported = db.relationship("User", foreign_keys=[reported_id],
                               backref=db.backref("reports_received", lazy="dynamic"))

    REASONS = {
        "spam":    "Спам",
        "abuse":   "Образи / Харасмент",
        "fake":    "Фейковий профіль",
        "fraud":   "Шахрайство",
        "other":   "Інше",
    }

    STATUS_LABELS = {
        "pending":   ("На розгляді", "warning"),
        "reviewed":  ("Розглянуто",  "success"),
        "dismissed": ("Відхилено",   "secondary"),
    }

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, ("—", "light"))

    def __repr__(self):
        return f"<Report #{self.id} {self.reporter_id}→{self.reported_id}>"


# ─── BannedUser ────────────────────────────────────────────────────────────────

class BannedUser(db.Model):
    """Record of a banned user account."""

    __tablename__ = "banned_user"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"),
                        unique=True, nullable=False)
    banned_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reason = db.Column(db.Text, default="")
    banned_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at = db.Column(db.DateTime, nullable=True)  # None = permanent

    user = db.relationship("User", foreign_keys=[user_id],
                           backref=db.backref("ban_record", uselist=False))
    banned_by = db.relationship("User", foreign_keys=[banned_by_id])

    def is_active(self) -> bool:
        """Return True if ban is currently active."""
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) < self.expires_at.replace(
            tzinfo=timezone.utc
        )

    def __repr__(self):
        return f"<BannedUser user_id={self.user_id}>"


# ─── Activity Feed ────────────────────────────────────────────────────────────

class ActivityEvent(db.Model):
    """Platform-wide activity feed entry."""

    __tablename__ = "activity_event"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    event_type = db.Column(db.String(40), nullable=False)
    # event_type: skill_added | exchange_started | exchange_completed |
    #             review_given | badge_awarded | user_joined
    object_id = db.Column(db.Integer, nullable=True)    # skill/exchange/badge id
    object_title = db.Column(db.String(120), default="")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    actor = db.relationship("User", foreign_keys=[actor_id],
                            backref=db.backref("activity_events", lazy="dynamic"))

    ICONS = {
        "skill_added":          "⚡",
        "exchange_started":     "🤝",
        "exchange_completed":   "🏁",
        "review_given":         "⭐",
        "badge_awarded":        "🏅",
        "user_joined":          "👋",
    }

    LABELS = {
        "skill_added":          "додав навичку",
        "exchange_started":     "розпочав обмін",
        "exchange_completed":   "завершив обмін",
        "review_given":         "залишив відгук",
        "badge_awarded":        "отримав значок",
        "user_joined":          "приєднався до платформи",
    }

    def icon(self) -> str:
        return self.ICONS.get(self.event_type, "📌")

    def label(self) -> str:
        return self.LABELS.get(self.event_type, self.event_type)

    def __repr__(self):
        return f"<ActivityEvent #{self.id} {self.event_type}>"


# ─── Skill Endorsement ────────────────────────────────────────────────────────

class Endorsement(db.Model):
    """User endorses another user's skill (LinkedIn-style)."""

    __tablename__ = "endorsement"

    id = db.Column(db.Integer, primary_key=True)
    endorser_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    skill_id    = db.Column(db.Integer, db.ForeignKey("skill.id"), nullable=False)
    created_at  = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.UniqueConstraint("endorser_id", "skill_id", name="uq_endorsement"),
    )

    endorser = db.relationship("User", foreign_keys=[endorser_id],
                               backref=db.backref("endorsements_given", lazy="dynamic"))
    skill    = db.relationship("Skill",
                               backref=db.backref("endorsements", lazy="dynamic"))

    def __repr__(self):
        return f"<Endorsement endorser={self.endorser_id} skill={self.skill_id}>"


# ─── Support Ticket ────────────────────────────────────────────────────────────

class SupportTicket(db.Model):
    """User support request to admin."""

    __tablename__ = "support_ticket"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject    = db.Column(db.String(200), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    status     = db.Column(db.String(20), default="open")
    # status: open | in_progress | resolved | closed
    admin_reply = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", foreign_keys=[user_id],
                           backref=db.backref("support_tickets", lazy="dynamic"))

    STATUS_LABELS = {
        "open":        ("Відкрито",      "warning"),
        "in_progress": ("В обробці",     "info"),
        "resolved":    ("Вирішено",      "success"),
        "closed":      ("Закрито",       "secondary"),
    }

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, ("—", "light"))

    def __repr__(self):
        return f"<SupportTicket #{self.id}>"


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM MODELS
# ══════════════════════════════════════════════════════════════════════════════

# ─── RBAC ────────────────────────────────────────────────────────────────────

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permission.id"), primary_key=True),
)

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
)


class Permission(db.Model):
    """Granular system permission."""
    __tablename__ = "permission"

    id   = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(256), default="")

    DEFINITIONS = [
        ("can_view_reports",    "Переглядати жалоби"),
        ("can_resolve_reports", "Вирішувати жалоби"),
        ("can_ban_users",       "Банити користувачів"),
        ("can_verify_users",    "Верифікувати профілі"),
        ("can_manage_skills",   "Керувати навичками"),
        ("can_manage_exchanges","Керувати обмінами"),
        ("can_manage_admins",   "Призначати адмінів"),
        ("can_view_audit_log",  "Переглядати аудит-лог"),
        ("can_reply_tickets",   "Відповідати на тікети"),
        ("can_view_analytics",  "Переглядати аналітику"),
    ]

    def __repr__(self): return f"<Permission {self.slug}>"


class Role(db.Model):
    """User role with associated permissions."""
    __tablename__ = "role"

    id   = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(80), nullable=False)
    priority = db.Column(db.Integer, default=0)  # higher = more power

    permissions = db.relationship("Permission", secondary=role_permissions, lazy="dynamic")
    users = db.relationship("User", secondary=user_roles,
                            backref=db.backref("roles", lazy="dynamic"))

    DEFINITIONS = [
        {"slug": "user",        "name": "Користувач",  "priority": 0,
         "permissions": []},
        {"slug": "moderator",   "name": "Модератор",   "priority": 10,
         "permissions": ["can_view_reports","can_resolve_reports","can_reply_tickets","can_verify_users"]},
        {"slug": "admin",       "name": "Адміністратор","priority": 20,
         "permissions": ["can_view_reports","can_resolve_reports","can_ban_users",
                         "can_verify_users","can_manage_skills","can_manage_exchanges",
                         "can_reply_tickets","can_view_analytics","can_view_audit_log"]},
        {"slug": "superadmin",  "name": "Суперадмін",  "priority": 30,
         "permissions": ["can_view_reports","can_resolve_reports","can_ban_users",
                         "can_verify_users","can_manage_skills","can_manage_exchanges",
                         "can_manage_admins","can_view_audit_log","can_reply_tickets",
                         "can_view_analytics"]},
    ]

    def __repr__(self): return f"<Role {self.slug}>"


# ─── Audit Trail ─────────────────────────────────────────────────────────────

class AuditLog(db.Model):
    """Immutable audit trail for all significant system actions."""
    __tablename__ = "audit_log"

    id          = db.Column(db.Integer, primary_key=True)
    actor_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action      = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(40), default="")   # "user","exchange","skill",...
    target_id   = db.Column(db.Integer, nullable=True)
    old_value   = db.Column(db.Text, default="")
    new_value   = db.Column(db.Text, default="")
    ip_address  = db.Column(db.String(45), default="")
    user_agent  = db.Column(db.String(256), default="")
    created_at  = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc))

    actor = db.relationship("User", foreign_keys=[actor_id],
                            backref=db.backref("audit_actions", lazy="dynamic"))

    def __repr__(self): return f"<AuditLog #{self.id} {self.action}>"


# ─── Dispute Resolution ───────────────────────────────────────────────────────

class Dispute(db.Model):
    """Formal dispute tied to an exchange."""
    __tablename__ = "dispute"

    id          = db.Column(db.Integer, primary_key=True)
    exchange_id = db.Column(db.Integer, db.ForeignKey("exchange.id"), nullable=False)
    opener_id   = db.Column(db.Integer, db.ForeignKey("user.id"),  nullable=False)
    reason      = db.Column(db.String(60), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status      = db.Column(db.String(20), default="open")
    # open | under_review | resolved_complete | resolved_cancel | resolved_warn
    resolution_note = db.Column(db.Text, default="")
    resolved_by_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at  = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc))
    updated_at  = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    exchange    = db.relationship("Exchange",
                                  backref=db.backref("disputes", lazy="dynamic"))
    opener      = db.relationship("User", foreign_keys=[opener_id])
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id])

    STATUS_LABELS = {
        "open":               ("Відкрито",              "warning"),
        "under_review":       ("На розгляді",            "info"),
        "resolved_complete":  ("Вирішено: завершити",   "success"),
        "resolved_cancel":    ("Вирішено: скасувати",   "secondary"),
        "resolved_warn":      ("Вирішено: попередження","danger"),
    }
    REASONS = {
        "no_show":     "Учасник не з'явився",
        "poor_quality":"Низька якість навчання",
        "fraud":       "Шахрайство",
        "harassment":  "Образи / домагання",
        "other":       "Інше",
    }

    def status_label(self):
        return self.STATUS_LABELS.get(self.status, ("—","light"))

    def __repr__(self): return f"<Dispute #{self.id} {self.status}>"


# ─── Exchange Agreement ───────────────────────────────────────────────────────

class ExchangeAgreement(db.Model):
    """Digital contract signed by both exchange participants."""
    __tablename__ = "exchange_agreement"

    id            = db.Column(db.Integer, primary_key=True)
    exchange_id   = db.Column(db.Integer, db.ForeignKey("exchange.id"),
                              unique=True, nullable=False)
    # Terms
    sessions_count    = db.Column(db.Integer, default=1)
    format            = db.Column(db.String(20), default="online")
    # online | offline | hybrid
    language          = db.Column(db.String(40), default="Українська")
    deadline_days     = db.Column(db.Integer, default=30)
    description       = db.Column(db.Text, default="")
    # Signatures
    proposer_agreed_at = db.Column(db.DateTime, nullable=True)
    proposer_ip        = db.Column(db.String(45), default="")
    receiver_agreed_at = db.Column(db.DateTime, nullable=True)
    receiver_ip        = db.Column(db.String(45), default="")
    created_at         = db.Column(db.DateTime,
                                   default=lambda: datetime.now(timezone.utc))

    exchange = db.relationship("Exchange",
                               backref=db.backref("agreement", uselist=False))

    @property
    def is_signed_by_both(self) -> bool:
        return bool(self.proposer_agreed_at and self.receiver_agreed_at)

    def __repr__(self): return f"<ExchangeAgreement exchange={self.exchange_id}>"


# ─── Trust Score ─────────────────────────────────────────────────────────────

class SkillTrustScore(db.Model):
    """Computed trust score for a specific skill of a user."""
    __tablename__ = "skill_trust_score"

    id       = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skill.id"),
                         unique=True, nullable=False)
    score    = db.Column(db.Float, default=0.0)
    endorsements_count  = db.Column(db.Integer, default=0)
    verified_exchanges  = db.Column(db.Integer, default=0)
    positive_reviews    = db.Column(db.Integer, default=0)
    updated_at = db.Column(db.DateTime,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    skill = db.relationship("Skill",
                            backref=db.backref("trust_score", uselist=False))

    def recalculate(self) -> None:
        """Recompute trust score from components."""
        self.score = min(100.0, (
            self.endorsements_count * 10 +
            self.verified_exchanges * 8 +
            self.positive_reviews * 5
        ))

    def __repr__(self): return f"<SkillTrustScore skill={self.skill_id} score={self.score}>"


# ─── Webhook ─────────────────────────────────────────────────────────────────

class Webhook(db.Model):
    """User-defined webhook for platform events."""
    __tablename__ = "webhook"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    url        = db.Column(db.String(512), nullable=False)
    secret     = db.Column(db.String(64), nullable=False)
    events     = db.Column(db.Text, default="")   # JSON list of event slugs
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime,
                           default=lambda: datetime.now(timezone.utc))
    last_triggered_at = db.Column(db.DateTime, nullable=True)
    last_status_code  = db.Column(db.Integer, nullable=True)

    user = db.relationship("User",
                           backref=db.backref("webhooks", lazy="dynamic"))

    EVENTS = [
        "exchange.created",  "exchange.accepted",  "exchange.completed",
        "exchange.rejected", "review.created",     "session.reminder",
        "dispute.opened",    "user.banned",         "badge.awarded",
    ]

    def get_events(self):
        import json
        try:
            return json.loads(self.events) if self.events else []
        except Exception:
            return []

    def set_events(self, event_list):
        import json
        self.events = json.dumps(event_list)

    def __repr__(self): return f"<Webhook #{self.id} {self.url[:30]}>"


# ─── Platform Metrics ────────────────────────────────────────────────────────

class PlatformMetric(db.Model):
    """Time-series snapshot of platform KPI metrics."""
    __tablename__ = "platform_metric"

    id         = db.Column(db.Integer, primary_key=True)
    metric     = db.Column(db.String(60), nullable=False)
    value      = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime,
                            default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self): return f"<PlatformMetric {self.metric}={self.value}>"
