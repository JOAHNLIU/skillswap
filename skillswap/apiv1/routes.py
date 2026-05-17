# filepath: skillswap/apiv1/routes.py
"""SkillSwap — REST API v1 with OpenAPI 3.0 + Swagger UI."""

from flask import jsonify, request
from flask_login import current_user
from extensions import db
from models import User, Skill, Exchange
from skillswap.apiv1 import apiv1_bp

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "SkillSwap API",
        "version": "1.0.0",
        "description": (
            "REST API для платформи бартерного обміну навичками.\n\n"
            "## Автентифікація\n"
            "**Bearer token**: `Authorization: Bearer <token>`  \n"
            "Генерується через `POST /api/v1/auth/token` (потрібна сесія браузера).  \n\n"
            "**Session**: стандартна cookie-сесія (для браузерного доступу)."
        ),
    },
    "servers": [
        {"url": "/api/v1", "description": "v1 (current)"},
        {"url": "/api",    "description": "Legacy (deprecated)"},
    ],
    "tags": [
        {"name": "Auth",      "description": "Токени"},
        {"name": "Users",     "description": "Профілі"},
        {"name": "Skills",    "description": "Навички"},
        {"name": "Exchanges", "description": "Обміни"},
        {"name": "Matches",   "description": "Матчинг"},
        {"name": "Stats",     "description": "Статистика"},
        {"name": "Trust",     "description": "Trust Score"},
    ],
    "paths": {
        "/auth/token": {"post": {
            "tags": ["Auth"], "summary": "Генерувати API токен",
            "security": [{"sessionAuth": []}],
            "responses": {"200": {"description": "Токен згенеровано",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TokenResponse"}}}}}}},
        "/auth/token/revoke": {"post": {
            "tags": ["Auth"], "summary": "Анулювати токен",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "responses": {"200": {"description": "Анульовано"}}}},
        "/users": {"get": {
            "tags": ["Users"], "summary": "Список користувачів",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [
                {"name": "page",  "in": "query", "schema": {"type": "integer", "default": 1}},
                {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 100}},
                {"name": "city",  "in": "query", "schema": {"type": "string"}},
            ],
            "responses": {"200": {"description": "Список",
                "content": {"application/json": {"schema": {"type": "object",
                    "properties": {"data": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                                   "total": {"type": "integer"}, "page": {"type": "integer"}}}}}}}}},
        "/users/{id}": {"get": {
            "tags": ["Users"], "summary": "Профіль юзера",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "Профіль"},
                          "404": {"description": "Не знайдено"}}}},
        "/skills": {"get": {
            "tags": ["Skills"], "summary": "Список навичок",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [
                {"name": "type",     "in": "query", "schema": {"type": "string", "enum": ["offer","want"]}},
                {"name": "category", "in": "query", "schema": {"type": "string"}},
                {"name": "q",        "in": "query", "schema": {"type": "string"}},
                {"name": "page",     "in": "query", "schema": {"type": "integer", "default": 1}},
            ],
            "responses": {"200": {"description": "Список"}}}},
        "/skills/{id}/trust": {"get": {
            "tags": ["Trust", "Skills"], "summary": "Trust Score навички",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [{"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}],
            "responses": {"200": {"description": "Trust score",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TrustScore"}}}}}}},
        "/exchanges": {"get": {
            "tags": ["Exchanges"], "summary": "Мої обміни",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [{"name": "status", "in": "query",
                "schema": {"type": "string",
                           "enum": ["pending","accepted","completed","rejected","disputed","cancelled"]}}],
            "responses": {"200": {"description": "Список обмінів"}}}},
        "/matches": {"get": {
            "tags": ["Matches"], "summary": "Рекомендовані матчі (ML 0–100%)",
            "security": [{"bearerAuth": []}, {"sessionAuth": []}],
            "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer", "default": 10}}],
            "responses": {"200": {"description": "Матчі"}}}},
        "/stats": {"get": {
            "tags": ["Stats"], "summary": "Статистика платформи (публічно)",
            "responses": {"200": {"description": "Статистика",
                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/PlatformStats"}}}}}}},
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "Token"},
            "sessionAuth": {"type": "apiKey", "in": "cookie", "name": "session"},
        },
        "schemas": {
            "TokenResponse": {"type": "object", "properties": {
                "token": {"type": "string"}, "message": {"type": "string"}}},
            "User": {"type": "object", "properties": {
                "id": {"type": "integer"}, "full_name": {"type": "string"},
                "username": {"type": "string"}, "city": {"type": "string"},
                "rating_points": {"type": "number"}, "review_count": {"type": "integer"},
                "is_verified": {"type": "boolean"}, "avatar": {"type": "string"}}},
            "TrustScore": {"type": "object", "properties": {
                "skill_id": {"type": "integer"}, "skill_title": {"type": "string"},
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "badge": {"type": "string"}, "endorsements": {"type": "integer"},
                "verified_exchanges": {"type": "integer"}, "positive_reviews": {"type": "integer"}}},
            "PlatformStats": {"type": "object", "properties": {
                "total_users": {"type": "integer"}, "total_skills": {"type": "integer"},
                "total_exchanges": {"type": "integer"}, "completed_exchanges": {"type": "integer"},
                "api_version": {"type": "string"}}},
        }
    },
}

SWAGGER_HTML = """<!DOCTYPE html>
<html lang="uk">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>SkillSwap API Docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"/>
  <style>body{margin:0;} .swagger-ui .topbar{background:#6366f1;}</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
  SwaggerUIBundle({
    url: "/api/v1/openapi.json",
    dom_id: "#swagger-ui",
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "StandaloneLayout",
    deepLinking: true,
    tryItOutEnabled: true,
  });
</script>
</body>
</html>"""


def _auth_user():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        u = User.query.filter_by(api_token=auth[7:].strip()).first()
        if u: return u
    if current_user.is_authenticated: return current_user
    return None


@apiv1_bp.route("/docs")
def docs():
    return SWAGGER_HTML, 200, {"Content-Type": "text/html"}


@apiv1_bp.route("/openapi.json")
def openapi_spec():
    return jsonify(OPENAPI_SPEC)


@apiv1_bp.route("/auth/token", methods=["POST"])
def generate_token():
    from flask_login import login_required
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    import secrets
    user.api_token = secrets.token_hex(32)
    db.session.commit()
    return jsonify({"token": user.api_token, "message": "Зберігай у безпечному місці!"})


@apiv1_bp.route("/auth/token/revoke", methods=["POST"])
def revoke_token():
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    user.api_token = None
    db.session.commit()
    return jsonify({"message": "Токен анульовано."})


@apiv1_bp.route("/users")
def users():
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    page  = request.args.get("page", 1, type=int)
    limit = min(request.args.get("limit", 20, type=int), 100)
    city  = request.args.get("city", "")
    q = User.query.filter_by(onboarding_done=True)
    if city: q = q.filter(User.city.ilike(f"%{city}%"))
    total = q.count()
    data  = q.order_by(User.rating_points.desc()).offset((page-1)*limit).limit(limit).all()
    return jsonify({"data": [_u(u) for u in data], "total": total, "page": page, "limit": limit})


@apiv1_bp.route("/users/<int:uid>")
def user_detail(uid: int):
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    u = User.query.get_or_404(uid)
    d = _u(u)
    d.update({"bio": u.bio, "available_from": u.available_from, "available_to": u.available_to,
               "teaching_rating": u.teaching_rating, "communication_rating": u.communication_rating,
               "skills_offer": [_s(s) for s in u.get_skills_offer()],
               "skills_want":  [_s(s) for s in u.get_skills_want()]})
    return jsonify(d)


@apiv1_bp.route("/skills")
def skills():
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    t = request.args.get("type",""); cat = request.args.get("category","")
    q_str = request.args.get("q",""); page = request.args.get("page",1,type=int)
    q = Skill.query
    if t:   q = q.filter_by(skill_type=t)
    if cat: q = q.filter_by(category=cat)
    if q_str:
        from sqlalchemy import or_
        toks = q_str.split()
        q = q.filter(or_(*[Skill.title.ilike(f"%{t}%") for t in toks]))
    return jsonify([_s(s) for s in q.offset((page-1)*50).limit(50).all()])


@apiv1_bp.route("/skills/<int:sid>/trust")
def skill_trust(sid: int):
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    skill = Skill.query.get_or_404(sid)
    try:
        from skillswap.trust.engine import compute_trust_score, get_trust_badge
        from models import SkillTrustScore
        rec = SkillTrustScore.query.filter_by(skill_id=sid).first()
        if not rec:
            compute_trust_score(skill)
            rec = SkillTrustScore.query.filter_by(skill_id=sid).first()
        _, badge = get_trust_badge(rec.score if rec else 0)
        return jsonify({"skill_id": sid, "skill_title": skill.title,
                        "score": rec.score if rec else 0, "badge": badge,
                        "endorsements": rec.endorsements_count if rec else 0,
                        "verified_exchanges": rec.verified_exchanges if rec else 0,
                        "positive_reviews": rec.positive_reviews if rec else 0})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@apiv1_bp.route("/exchanges")
def exchanges():
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    status = request.args.get("status","")
    q = Exchange.query.filter(
        (Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id))
    if status: q = q.filter_by(status=status)
    return jsonify([{"id": e.id, "proposer_id": e.proposer_id, "receiver_id": e.receiver_id,
                     "status": e.status, "message": e.message,
                     "created_at": e.created_at.isoformat()} for e in q.limit(50).all()])


@apiv1_bp.route("/matches")
def matches():
    user = _auth_user()
    if not user: return jsonify({"error": "Unauthorized"}), 401
    limit = request.args.get("limit", 10, type=int)
    from skillswap.skills.matching import get_matches
    return jsonify([{"user_id": m["user"].id, "full_name": m["user"].full_name,
                     "username": m["user"].username, "city": m["user"].city,
                     "match_score": m["match_score"], "avatar": m["user"].avatar_or_default(),
                     "rating_points": m["user"].rating_points,
                     "is_verified": m["user"].is_verified}
                    for m in get_matches(user, limit=limit)])


@apiv1_bp.route("/stats")
def stats():
    return jsonify({"total_users": User.query.count(), "total_skills": Skill.query.count(),
                    "total_exchanges": Exchange.query.count(),
                    "completed_exchanges": Exchange.query.filter_by(status="completed").count(),
                    "skills_offer": Skill.query.filter_by(skill_type="offer").count(),
                    "skills_want":  Skill.query.filter_by(skill_type="want").count(),
                    "api_version": "1.0.0"})


def _u(u: User) -> dict:
    return {"id": u.id, "full_name": u.full_name, "username": u.username, "city": u.city,
            "rating_points": u.rating_points, "review_count": u.review_count,
            "is_verified": u.is_verified, "avatar": u.avatar_or_default()}

def _s(s: Skill) -> dict:
    ts = s.trust_score
    return {"id": s.id, "title": s.title, "category": s.category, "level": s.level,
            "type": s.skill_type, "user_id": s.user_id,
            "user_name": s.user.full_name or s.user.email,
            "trust_score": ts.score if ts else None}
