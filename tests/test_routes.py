# filepath: tests/test_routes.py
"""SkillSwap — Integration tests for HTTP routes."""
import pytest


class TestPublicRoutes:
    def test_login_page(self, client):
        assert client.get("/auth/login").status_code == 200

    def test_register_page(self, client):
        assert client.get("/auth/register").status_code == 200

    def test_forgot_password(self, client):
        assert client.get("/auth/forgot-password").status_code == 200

    def test_api_stats(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.get_json()
        assert "total_users" in data

    def test_protected_redirect(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 302


class TestAuthenticatedRoutes:
    def test_dashboard(self, auth_client):
        assert auth_client.get("/dashboard").status_code == 200

    def test_skills_list(self, auth_client):
        assert auth_client.get("/skills/").status_code == 200

    def test_my_skills(self, auth_client):
        assert auth_client.get("/skills/my").status_code == 200

    def test_skill_create_form(self, auth_client):
        assert auth_client.get("/skills/create").status_code == 200

    def test_exchanges_list(self, auth_client):
        assert auth_client.get("/exchanges/").status_code == 200

    def test_users_list(self, auth_client):
        assert auth_client.get("/users/").status_code == 200

    def test_reviews_wall(self, auth_client):
        assert auth_client.get("/reviews/").status_code == 200

    def test_notifications(self, auth_client):
        assert auth_client.get("/notifications/").status_code == 200

    def test_support(self, auth_client):
        assert auth_client.get("/support/").status_code == 200

    def test_api_matches(self, auth_client):
        r = auth_client.get("/api/matches")
        assert r.status_code == 200

    def test_api_activity(self, auth_client):
        assert auth_client.get("/api/activity").status_code == 200

    def test_api_autocomplete(self, auth_client):
        assert auth_client.get("/api/skills/autocomplete?q=Py").status_code == 200


class TestAdminRoutes:
    def test_admin_dashboard(self, auth_client):
        assert auth_client.get("/admin/").status_code == 200

    def test_admin_users(self, auth_client):
        assert auth_client.get("/admin/users").status_code == 200

    def test_admin_reports(self, auth_client):
        assert auth_client.get("/admin/reports").status_code == 200

    def test_admin_banned(self, auth_client):
        assert auth_client.get("/admin/banned").status_code == 200

    def test_admin_tickets(self, auth_client):
        assert auth_client.get("/admin/tickets").status_code == 200

    def test_admin_charts(self, auth_client):
        assert auth_client.get("/admin/charts-data").status_code == 200

    def test_non_admin_blocked(self, app, client):
        with app.app_context():
            from models import User
            u = User(email="nonadmin@test.com", username="nonadmin",
                     onboarding_done=True, email_verified=True)
            u.set_password("pass")
            from extensions import db
            db.session.add(u)
            db.session.commit()
            uid = u.id
        with client.session_transaction() as sess:
            sess["_user_id"] = str(uid)
            sess["_fresh"] = True
        assert client.get("/admin/").status_code == 403
