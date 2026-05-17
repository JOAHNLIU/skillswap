# filepath: skillswap/api/routes.py
"""
SkillSwap — REST API Blueprint.
Endpoints: /api/skills, /api/users, /api/stats, /api/matches
"""

import secrets
from functools import wraps
from flask import jsonify, request
from flask_login import login_required, current_user
from models import User, Skill, Exchange
from extensions import db, cache
from skillswap.api import api_bp
from skillswap.skills.matching import get_matches


def token_or_session_required(f):
    """Allow access via Bearer token OR session login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:].strip()
            user = User.query.filter_by(api_token=token).first()
            if not user:
                return jsonify({"error": "Invalid token"}), 401
            # Inject user as current_user equivalent
            request._api_user = user
            return f(*args, **kwargs)
        # Fall back to session
        from flask_login import current_user as cu
        if not cu.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        request._api_user = cu
        return f(*args, **kwargs)
    return decorated


def get_api_user():
    """Return current API user (token or session)."""
    return getattr(request, "_api_user", current_user)


@api_bp.route("/token/generate", methods=["POST"])
@login_required
def generate_token():
    """Generate or regenerate API token for the current user."""
    current_user.api_token = secrets.token_hex(32)
    db.session.commit()
    return jsonify({"token": current_user.api_token,
                    "message": "Зберігайте токен у безпечному місці!"})


@api_bp.route("/token/revoke", methods=["POST"])
@login_required
def revoke_token():
    """Revoke (delete) the current user's API token."""
    current_user.api_token = None
    db.session.commit()
    return jsonify({"message": "Токен анульовано."})


# ── Skills ────────────────────────────────────────────────────────────────────

@api_bp.route("/skills", methods=["GET"])
@login_required
def api_skills():
    """Return all skills as JSON, optional ?type=offer|want&category=X."""
    skill_type = request.args.get("type", "")
    category = request.args.get("category", "")
    q = request.args.get("q", "")

    query = Skill.query
    if skill_type:
        query = query.filter_by(skill_type=skill_type)
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(Skill.title.ilike(f"%{q}%"))

    skills = query.limit(100).all()
    return jsonify([
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "category": s.category,
            "level": s.level,
            "type": s.skill_type,
            "user_id": s.user_id,
            "user_name": s.user.full_name or s.user.email,
        }
        for s in skills
    ])


# ── Users ─────────────────────────────────────────────────────────────────────

@api_bp.route("/users", methods=["GET"])
@login_required
def api_users():
    """Return all completed-onboarding users as JSON."""
    users = User.query.filter_by(onboarding_done=True).limit(100).all()
    return jsonify([
        {
            "id": u.id,
            "full_name": u.full_name,
            "city": u.city,
            "rating_points": u.rating_points,
            "review_count": u.review_count,
            "avatar": u.avatar_or_default(),
        }
        for u in users
    ])


# ── Stats ─────────────────────────────────────────────────────────────────────

@api_bp.route("/stats", methods=["GET"])
def api_stats():
    """Return platform-wide statistics."""
    return jsonify({
        "total_users": User.query.count(),
        "total_skills": Skill.query.count(),
        "total_exchanges": Exchange.query.count(),
        "completed_exchanges": Exchange.query.filter_by(status="completed").count(),
        "pending_exchanges": Exchange.query.filter_by(status="pending").count(),
        "skills_offer": Skill.query.filter_by(skill_type="offer").count(),
        "skills_want": Skill.query.filter_by(skill_type="want").count(),
    })


# ── Matches ───────────────────────────────────────────────────────────────────

@api_bp.route("/matches", methods=["GET"])
@login_required
def api_matches():
    """Return top matches for the current user."""
    limit = request.args.get("limit", 10, type=int)
    matches = get_matches(current_user, limit=limit)
    return jsonify([
        {
            "user_id": m["user"].id,
            "full_name": m["user"].full_name,
            "city": m["user"].city,
            "match_score": m["match_score"],
            "avatar": m["user"].avatar_or_default(),
            "rating_points": m["user"].rating_points,
        }
        for m in matches
    ])


@api_bp.route("/skills/autocomplete")
@login_required
def skills_autocomplete():
    """Return skill title suggestions for autocomplete. ?q=py&limit=8"""
    from models import Skill
    q = request.args.get("q", "").strip()
    limit = min(request.args.get("limit", 8, type=int), 20)
    if len(q) < 1:
        return jsonify([])
    results = (
        Skill.query
        .with_entities(Skill.title, Skill.category)
        .filter(Skill.title.ilike(f"{q}%"))
        .distinct()
        .order_by(Skill.title)
        .limit(limit)
        .all()
    )
    return jsonify([{"title": r.title, "category": r.category or ""} for r in results])


@api_bp.route("/activity")
@login_required
@cache.cached(timeout=20)
def activity_feed():
    """Return latest 30 activity events as JSON."""
    from models import ActivityEvent, BannedUser
    banned_ids = {r[0] for r in db.session.query(BannedUser.user_id).all()}
    events = (
        ActivityEvent.query
        .filter(~ActivityEvent.actor_id.in_(banned_ids) if banned_ids else True)
        .order_by(ActivityEvent.created_at.desc())
        .limit(30)
        .all()
    )
    return jsonify([
        {
            "id": e.id,
            "actor_id": e.actor_id,
            "actor_name": f"@{e.actor.username}" if e.actor.username else (e.actor.email.split("@")[0] if e.actor.email else "user"),
            "actor_avatar": e.actor.avatar_or_default(),
            "actor_url": f"/users/{e.actor_id}",
            "event_type": e.event_type,
            "icon": e.icon(),
            "label": e.label(),
            "object_title": e.object_title,
            "created_at": e.created_at.strftime("%d.%m %H:%M"),
        }
        for e in events
    ])


# ── Endorsements ──────────────────────────────────────────────────────────────

@api_bp.route("/skills/<int:skill_id>/endorse", methods=["POST"])
@login_required
def endorse_skill(skill_id: int):
    """Toggle endorsement on a skill. Returns {endorsed: bool, count: int}."""
    from models import Skill, Endorsement
    from extensions import db, cache as _db
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id == current_user.id:
        return jsonify({"error": "Cannot endorse own skill"}), 400

    existing = Endorsement.query.filter_by(
        endorser_id=current_user.id, skill_id=skill_id
    ).first()

    if existing:
        _db.session.delete(existing)
        _db.session.commit()
        endorsed = False
    else:
        _db.session.add(Endorsement(endorser_id=current_user.id, skill_id=skill_id))
        _db.session.commit()
        endorsed = True

    count = skill.endorsements.count()
    return jsonify({"endorsed": endorsed, "count": count})


@api_bp.route("/users/autocomplete")
@login_required
def users_autocomplete():
    """Return user @username suggestions. ?q=jo"""
    q = request.args.get("q", "").strip().lstrip("@")
    if len(q) < 1:
        return jsonify([])
    users = (
        User.query
        .filter(User.username.ilike(f"{q}%"), User.id != current_user.id)
        .limit(8).all()
    )
    return jsonify([
        {"username": u.username, "full_name": u.full_name or "",
         "avatar": u.avatar_or_default()}
        for u in users if u.username
    ])
