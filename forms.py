# filepath: forms.py
"""
SkillSwap — WTForms definitions for all blueprints.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, PasswordField, TextAreaField, SelectField,
    IntegerField, SubmitField, HiddenField, SelectMultipleField, TimeField
)
from wtforms.validators import (
    DataRequired, Email, EqualTo, Length, Optional,
    NumberRange, ValidationError
)
from models import User


# ─── Auth ─────────────────────────────────────────────────────────────────────

class RegisterForm(FlaskForm):
    """User registration form."""
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    username = StringField(
        "Тег користувача (@username)",
        validators=[DataRequired(), Length(min=3, max=40)],
        description="Унікальний тег для згадки у відгуках. Тільки латиниця, цифри, _"
    )
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6, max=128)])
    password2 = PasswordField(
        "Підтвердження паролю",
        validators=[DataRequired(), EqualTo("password", message="Паролі не збігаються")],
    )
    submit = SubmitField("Зареєструватися")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Ця електронна пошта вже зареєстрована.")

    def validate_username(self, field):
        import re
        val = field.data.lstrip("@").lower().strip()
        if not re.match(r'^[a-z0-9_]{3,40}$', val):
            raise ValidationError(
                "Тег може містити лише латинські літери, цифри та _ (3-40 символів)."
            )
        if User.query.filter_by(username=val).first():
            raise ValidationError("Цей тег вже зайнято.")


class LoginForm(FlaskForm):
    """User login form."""
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Увійти")


# ─── Onboarding ───────────────────────────────────────────────────────────────

GENDER_CHOICES = [
    ("", "— оберіть —"),
    ("male", "Чоловік"),
    ("female", "Жінка"),
    ("other", "Інше"),
    ("prefer_not", "Не вказувати"),
]

TIME_CHOICES = [(f"{h:02d}:{m:02d}", f"{h:02d}:{m:02d}")
                for h in range(0, 24) for m in (0, 30)]


class OnboardingForm(FlaskForm):
    """Multi-field onboarding form."""
    full_name = StringField("Ім'я та прізвище", validators=[DataRequired(), Length(max=120)])
    age = IntegerField("Вік", validators=[DataRequired(message="Вкажіть вік"), NumberRange(min=10, max=100)])
    gender = SelectField("Стать", choices=GENDER_CHOICES, validators=[DataRequired(message="Оберіть стать")])
    city = StringField("Місто", validators=[DataRequired(message="Вкажіть місто"), Length(max=100)])
    bio = TextAreaField("Про себе", validators=[Optional(), Length(max=1000)])
    available_from = SelectField("Доступний з", choices=TIME_CHOICES, default="09:00", validators=[DataRequired()])
    available_to = SelectField("Доступний до", choices=TIME_CHOICES, default="21:00", validators=[DataRequired()])
    avatar = FileField(
        "Фото профілю",
        validators=[FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Тільки зображення!")],
    )
    submit = SubmitField("Зберегти профіль")


# ─── Skills ───────────────────────────────────────────────────────────────────

LEVEL_CHOICES = [
    ("beginner", "Початківець"),
    ("elementary", "Елементарний"),
    ("intermediate", "Середній"),
    ("advanced", "Просунутий"),
    ("expert", "Експерт"),
    ("master", "Майстер"),
]

CATEGORY_CHOICES = [
    ("", "— оберіть категорію —"),
    ("IT та програмування", "💻 IT та програмування"),
    ("Дизайн і візуал", "🎨 Дизайн і візуал"),
    ("Мови та комунікація", "🌍 Мови та комунікація"),
    ("Освіта та науки", "📚 Освіта та науки"),
    ("Бізнес і кар'єра", "💼 Бізнес і кар'єра"),
    ("Маркетинг і контент", "📣 Маркетинг і контент"),
    ("Фото, відео та монтаж", "🎬 Фото, відео та монтаж"),
    ("Музика і звук", "🎵 Музика і звук"),
    ("Спорт і здоров'я", "💪 Спорт і здоров'я"),
    ("Кулінарія і побут", "🍳 Кулінарія і побут"),
    ("Мистецтво і handmade", "🖼 Мистецтво і handmade"),
    ("Інше", "📌 Інше"),
]

# Skills per category — used for autocomplete hints
SKILLS_BY_CATEGORY = {
    "IT та програмування": [
        "Python", "Flask", "Django", "FastAPI", "JavaScript", "TypeScript", "React",
        "Vue.js", "HTML/CSS", "SQL", "PostgreSQL", "MongoDB", "Git", "Docker",
        "Linux", "REST API", "Тестування ПЗ", "Алгоритми", "Data Science", "Machine Learning",
    ],
    "Дизайн і візуал": [
        "Figma", "UI/UX дизайн", "Веб-дизайн", "Adobe Photoshop", "Adobe Illustrator",
        "Canva", "Брендинг", "Логотипи", "Типографіка", "Презентації", "Ілюстрація",
        "Motion Design", "Blender", "3D моделювання", "Дизайн портфоліо",
    ],
    "Мови та комунікація": [
        "Англійська", "Українська для спілкування", "Німецька", "Французька", "Іспанська",
        "Польська", "Італійська", "Китайська", "Японська", "Корейська", "Публічні виступи",
        "Переговори", "Грамотне письмо", "Підготовка до співбесіди англійською",
    ],
    "Освіта та науки": [
        "Математика", "Алгебра", "Геометрія", "Математичний аналіз", "Статистика",
        "Фізика", "Хімія", "Біологія", "Історія", "Географія", "Підготовка до НМТ",
        "Підготовка до іспитів", "Академічне письмо", "Конспектування", "Репетиторство",
    ],
    "Бізнес і кар'єра": [
        "Проєктний менеджмент", "Product Management", "Бізнес-аналіз", "Фінансова грамотність",
        "Excel", "Google Sheets", "Продажі", "Переговори", "HR", "Резюме та LinkedIn",
        "Підготовка до співбесіди", "Стартапи", "Планування часу", "Нотатки і Notion",
    ],
    "Маркетинг і контент": [
        "SMM", "Instagram", "TikTok", "YouTube", "SEO", "Google Ads", "Meta Ads",
        "Email-маркетинг", "Копірайтинг", "Контент-план", "Сторітелінг", "Аналітика",
        "Особистий бренд", "Таргетована реклама", "Ком'юніті-менеджмент",
    ],
    "Фото, відео та монтаж": [
        "Фотографія", "Портретна зйомка", "Предметна зйомка", "Lightroom", "Відеомонтаж",
        "Adobe Premiere Pro", "DaVinci Resolve", "CapCut", "After Effects", "Зйомка Reels",
        "Сценарій відео", "Колірна корекція", "Звук для відео",
    ],
    "Музика і звук": [
        "Гітара", "Фортепіано", "Барабани", "Бас-гітара", "Скрипка", "Вокал",
        "Теорія музики", "Аранжування", "FL Studio", "Ableton Live", "Logic Pro",
        "Зведення звуку", "Мастеринг", "DJ", "Запис подкастів",
    ],
    "Спорт і здоров'я": [
        "Фітнес", "Йога", "Пілатес", "Стретчинг", "Біг", "Плавання", "Футбол",
        "Баскетбол", "Волейбол", "Теніс", "Бойові мистецтва", "Танці", "Харчові звички",
        "Домашні тренування", "Шахи",
    ],
    "Кулінарія і побут": [
        "Випічка", "Десерти", "Піца", "Паста", "Українська кухня", "Японська кухня",
        "Суші", "Веганська кухня", "Планування меню", "Домашня кава", "Консервація",
        "Організація простору", "Дрібний ремонт", "Догляд за рослинами",
    ],
    "Мистецтво і handmade": [
        "Живопис", "Акварель", "Олівцевий малюнок", "Скетчинг", "Цифровий арт",
        "Каліграфія", "Кераміка", "Ліплення", "Вишивка", "В'язання", "Шиття",
        "Комікси та манга", "Декор", "Рукоділля", "Арт-терапія",
    ],
    "Інше": [],
}

TYPE_CHOICES = [("offer", "Пропоную"), ("want", "Шукаю")]


class SkillForm(FlaskForm):
    """Create / edit a skill."""
    title = StringField("Назва навички", validators=[DataRequired(), Length(max=120)])
    description = TextAreaField("Опис", validators=[Optional(), Length(max=800)])
    category = SelectField("Категорія", choices=CATEGORY_CHOICES, validators=[DataRequired(message="Оберіть категорію")])
    subcategory = StringField("Підкатегорія", validators=[Optional(), Length(max=80)])
    level = SelectField("Рівень", choices=LEVEL_CHOICES, default="beginner")
    skill_type = SelectField("Тип", choices=TYPE_CHOICES, default="offer")
    submit = SubmitField("Зберегти")


class OnboardingSkillForm(FlaskForm):
    """Inline skill form used during onboarding (no separate submit)."""
    title = StringField("Назва навички", validators=[DataRequired(), Length(max=120)])
    category = SelectField("Категорія", choices=CATEGORY_CHOICES, validators=[DataRequired(message="Оберіть категорію")])
    level = SelectField("Рівень", choices=LEVEL_CHOICES, default="beginner")
    skill_type = SelectField("Тип", choices=TYPE_CHOICES, default="offer")


# ─── Exchanges ────────────────────────────────────────────────────────────────

class ExchangeCreateForm(FlaskForm):
    """Propose a new exchange."""
    receiver_id = HiddenField("Receiver", validators=[DataRequired()])
    offered_skill_id = SelectField("Моя навичка (пропоную)", coerce=int, validators=[Optional()])
    requested_skill_id = SelectField("Потрібна навичка", coerce=int, validators=[Optional()])
    message = TextAreaField("Повідомлення", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Надіслати пропозицію")


class MessageForm(FlaskForm):
    """Send a chat message with an optional attachment."""
    body = TextAreaField("Повідомлення", validators=[Optional(), Length(max=2000)])
    attachment = FileField(
        "Фото або файл",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "txt", "zip"],
                "Дозволені файли: зображення, PDF, DOC/DOCX, TXT або ZIP."
            ),
        ],
    )
    submit = SubmitField("Надіслати")


class SessionForm(FlaskForm):
    """Schedule a session."""
    scheduled_at = StringField("Дата та час (YYYY-MM-DDTHH:MM)", validators=[DataRequired()])
    duration_minutes = IntegerField(
        "Тривалість (хвилин)", default=60, validators=[NumberRange(min=15, max=480)]
    )
    notes = TextAreaField("Нотатки", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Запланувати")


class ReviewForm(FlaskForm):
    """Leave a review after exchange completion."""
    rating = SelectField(
        "Оцінка",
        choices=[(str(i), f"{'★' * i}{'☆' * (5 - i)} ({i})") for i in range(1, 6)],
        coerce=int,
        validators=[DataRequired()],
    )
    review_type = SelectField(
        "Тип оцінки",
        choices=[("teaching", "Навчання"), ("communication", "Спілкування")],
    )
    comment = TextAreaField("Коментар", validators=[Optional(), Length(max=800)])
    submit = SubmitField("Залишити відгук")


# ─── Profile Edit ─────────────────────────────────────────────────────────────

class ProfileEditForm(FlaskForm):
    """Edit user profile (reuses onboarding fields)."""
    full_name = StringField("Ім'я та прізвище", validators=[DataRequired(), Length(max=120)])
    age = IntegerField("Вік", validators=[DataRequired(message="Вкажіть вік"), NumberRange(min=10, max=100)])
    gender = SelectField("Стать", choices=GENDER_CHOICES, validators=[DataRequired(message="Оберіть стать")])
    city = StringField("Місто", validators=[DataRequired(message="Вкажіть місто"), Length(max=100)])
    bio = TextAreaField("Про себе", validators=[Optional(), Length(max=1000)])
    available_from = SelectField("Доступний з", choices=TIME_CHOICES, default="09:00", validators=[DataRequired()])
    available_to = SelectField("Доступний до", choices=TIME_CHOICES, default="21:00", validators=[DataRequired()])
    avatar = FileField(
        "Змінити фото",
        validators=[FileAllowed(["jpg", "jpeg", "png", "gif", "webp"], "Тільки зображення!")],
    )
    submit = SubmitField("Зберегти зміни")


# ─── Search ───────────────────────────────────────────────────────────────────

class SearchFilterForm(FlaskForm):
    """Sidebar filter form on /skills page."""
    class Meta:
        csrf = False  # GET form — no CSRF needed

    q = StringField("Пошук", validators=[Optional()])
    category = SelectField("Категорія", choices=CATEGORY_CHOICES, validators=[DataRequired(message="Оберіть категорію")])
    level = SelectField(
        "Рівень",
        choices=[("", "— всі —")] + LEVEL_CHOICES,
        validators=[Optional()],
    )
    skill_type = SelectField(
        "Тип",
        choices=[("", "— всі —"), ("offer", "Пропоную"), ("want", "Шукаю")],
        validators=[Optional()],
    )
    city = StringField("Місто", validators=[Optional()])
    gender = SelectField(
        "Стать",
        choices=[("", "— всі —"), ("male", "Чоловік"), ("female", "Жінка"), ("other", "Інше")],
        validators=[Optional()],
    )
    age_min = IntegerField("Вік від", validators=[Optional(), NumberRange(min=10)])
    age_max = IntegerField("Вік до", validators=[Optional(), NumberRange(max=100)])
    available_from = SelectField(
        "Доступний з", choices=[("", "— будь-який —")] + TIME_CHOICES, validators=[Optional()]
    )
    available_to = SelectField(
        "Доступний до", choices=[("", "— будь-який —")] + TIME_CHOICES, validators=[Optional()]
    )
    min_rating = IntegerField("Мін. рейтинг", validators=[Optional(), NumberRange(min=0)])
    min_reviews = IntegerField("Мін. відгуків", validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField("Застосувати")


# ─── Global Review ────────────────────────────────────────────────────────────

GLOBAL_REVIEW_CATEGORIES = [
    ("app",      "💬 Про застосунок"),
    ("user",     "👤 Про користувача"),
    ("exchange", "🔄 Про якість обміну"),
]

class GlobalReviewForm(FlaskForm):
    """Submit a platform-wide review."""
    category = SelectField(
        "Категорія",
        choices=GLOBAL_REVIEW_CATEGORIES,
        default="app",
        validators=[DataRequired()],
    )
    mentioned_username = StringField(
        "Тег користувача (для категорії «Про користувача»)",
        validators=[Optional(), Length(max=42)],
        description="Введіть @username користувача якого згадуєте"
    )
    rating = SelectField(
        "Оцінка",
        choices=[(str(i), f"{'★' * i}{'☆' * (5 - i)} ({i})") for i in range(1, 6)],
        coerce=int,
        validators=[DataRequired()],
    )
    title = StringField("Заголовок", validators=[Optional(), Length(max=120)])
    body = TextAreaField(
        "Текст відгуку",
        validators=[DataRequired(), Length(min=10, max=2000)],
    )
    submit = SubmitField("Опублікувати відгук")

    def validate_mentioned_username(self, field):
        if self.category.data == "user":
            if not field.data or not field.data.strip().lstrip("@"):
                raise ValidationError(
                    "Для відгуку «Про користувача» потрібно вказати @тег користувача."
                )
            val = field.data.lstrip("@").lower().strip()
            from models import User
            if not User.query.filter_by(username=val).first():
                raise ValidationError(f"Користувача @{val} не знайдено.")


# ─── Report ───────────────────────────────────────────────────────────────────

REPORT_REASONS = [
    ("spam",   "Спам"),
    ("abuse",  "Образи / Харасмент"),
    ("fake",   "Фейковий профіль"),
    ("fraud",  "Шахрайство"),
    ("other",  "Інше"),
]

class ReportForm(FlaskForm):
    """File a complaint against a user."""
    reported_id = HiddenField("Reported user", validators=[DataRequired()])
    reason = SelectField(
        "Причина",
        choices=REPORT_REASONS,
        validators=[DataRequired()],
    )
    description = TextAreaField(
        "Опис",
        validators=[DataRequired(), Length(min=10, max=1000)],
    )
    submit = SubmitField("Надіслати жалобу")


# ─── Ban ──────────────────────────────────────────────────────────────────────

class BanForm(FlaskForm):
    """Admin: ban a user."""
    reason = TextAreaField(
        "Причина бану",
        validators=[DataRequired(), Length(min=5, max=500)],
    )
    submit = SubmitField("Заблокувати")
