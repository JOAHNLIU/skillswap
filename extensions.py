# filepath: extensions.py
"""SkillSwap — Flask extensions initialization."""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_mail import Mail
from flask_socketio import SocketIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
cache = Cache()
mail = Mail()
socketio = SocketIO()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
compress = Compress()

login_manager.login_view = "auth.login"
login_manager.login_message = "Будь ласка, увійдіть щоб продовжити."
login_manager.login_message_category = "warning"
