# filepath: tests/test_models.py
"""SkillSwap — Unit tests for database models."""
import pytest


def test_password_hashing(app, db):
    with app.app_context():
        from models import User
        u = User(email="pw@test.com", username="pwtest")
        u.set_password("secret123")
        assert u.check_password("secret123") is True
        assert u.check_password("wrong") is False
        assert "secret123" not in u.password_hash


def test_avatar_or_default(app, db):
    with app.app_context():
        from models import User
        u = User(email="av@test.com", username="avtest", full_name="Test User")
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        url = u.avatar_or_default()
        assert "ui-avatars.com" in url or url.startswith("/")


def test_is_banned_false(app, db):
    with app.app_context():
        from models import User
        u = User(email="ban@test.com", username="bantest")
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        assert u.is_banned is False


def test_skill_creation(app, db):
    with app.app_context():
        from models import User, Skill
        u = User(email="sk@test.com", username="sktest", onboarding_done=True)
        u.set_password("pass")
        db.session.add(u)
        db.session.commit()
        s = Skill(title="Python", category="Програмування",
                  level="expert", skill_type="offer", user_id=u.id)
        db.session.add(s)
        db.session.commit()
        assert s.id is not None
        assert s.title == "Python"


def test_exchange_status_label(app, db):
    with app.app_context():
        from models import User, Exchange
        u1 = User(email="ex1@test.com", username="ex1test"); u1.set_password("p")
        u2 = User(email="ex2@test.com", username="ex2test"); u2.set_password("p")
        db.session.add_all([u1, u2])
        db.session.commit()
        ex = Exchange(proposer_id=u1.id, receiver_id=u2.id, status="completed")
        db.session.add(ex)
        db.session.commit()
        label, color = ex.status_label()
        assert label == "Завершено"


def test_match_score(app, db):
    with app.app_context():
        from models import User, Skill
        from skillswap.skills.matching import compute_match_score
        u1 = User(email="m1@test.com", username="m1test",
                  available_from="09:00", available_to="21:00")
        u1.set_password("p")
        u2 = User(email="m2@test.com", username="m2test",
                  available_from="09:00", available_to="21:00")
        u2.set_password("p")
        db.session.add_all([u1, u2])
        db.session.commit()
        s1 = Skill(title="Python", category="Програмування",
                   level="expert", skill_type="offer", user_id=u1.id)
        s2 = Skill(title="Python", category="Програмування",
                   level="beginner", skill_type="want", user_id=u2.id)
        db.session.add_all([s1, s2])
        db.session.commit()
        score = compute_match_score(u1, u2)
        assert score >= 40


def test_global_review_category(app, db):
    with app.app_context():
        from models import User, GlobalReview
        u = User(email="gr@test.com", username="grtest"); u.set_password("p")
        db.session.add(u)
        db.session.commit()
        r = GlobalReview(author_id=u.id, category="app", rating=5, body="Great!")
        db.session.add(r)
        db.session.commit()
        icon, label = r.category_label()
        assert icon == "💬"
