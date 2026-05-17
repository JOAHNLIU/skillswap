# filepath: tests/conftest.py
"""SkillSwap — pytest configuration and fixtures."""

import pytest
from app import create_app
from extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """Create test Flask app with in-memory SQLite."""
    import os
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["WTF_CSRF_ENABLED"] = "False"
    application = create_app("default")
    application.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "MAIL_SUPPRESS_SEND": True,
        "LIMITER_ENABLED": False,
    })
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Rollback any changes after each test."""
    with app.app_context():
        yield
        _db.session.rollback()
        # Clean all tables
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


@pytest.fixture
def db(app):
    with app.app_context():
        yield _db


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(db, app):
    with app.app_context():
        from models import User
        existing = User.query.filter_by(email="admin@test.com").first()
        if existing:
            return existing
        u = User(
            email="admin@test.com", username="admin_test",
            full_name="Admin", is_admin=True, onboarding_done=True,
            email_verified=True, city="Kyiv",
            available_from="09:00", available_to="21:00",
        )
        u.set_password("testpass")
        db.session.add(u)
        db.session.commit()
        return u


@pytest.fixture
def regular_user(db, app):
    with app.app_context():
        from models import User
        existing = User.query.filter_by(email="user@test.com").first()
        if existing:
            return existing
        u = User(
            email="user@test.com", username="user_test",
            full_name="User", onboarding_done=True, email_verified=True,
            city="Lviv", available_from="10:00", available_to="20:00",
        )
        u.set_password("testpass")
        db.session.add(u)
        db.session.commit()
        return u


@pytest.fixture
def auth_client(client, admin_user, app):
    with app.app_context():
        from models import User
        u = User.query.filter_by(email="admin@test.com").first()
        uid = u.id
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
    return client
