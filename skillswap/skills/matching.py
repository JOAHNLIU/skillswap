# filepath: skillswap/skills/matching.py
"""SkillSwap — lightweight matching engine.

The previous version had optional sklearn/numpy recommendations. For Render Free
this version uses deterministic Python-only scoring, so deployment is lighter and
cold starts are faster.
"""

from __future__ import annotations

from typing import List
from models import User


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def _tokens(text: str | None) -> set[str]:
    return {part for part in _normalize(text).replace(",", " ").split() if len(part) > 2}


def _time_overlap(fa, ta, fb, tb) -> bool:
    try:
        def minutes(value: str) -> int:
            hours, mins = value.split(":")
            return int(hours) * 60 + int(mins)
        return minutes(fa) < minutes(tb) and minutes(fb) < minutes(ta)
    except Exception:
        return False


def _skill_sets(user: User) -> tuple[set[str], set[str]]:
    offered = {skill.title.lower() for skill in user.skills.filter_by(skill_type="offer").all()}
    wanted = {skill.title.lower() for skill in user.skills.filter_by(skill_type="want").all()}
    return offered, wanted


def compute_match_score(me: User, other: User) -> int:
    """Compute a 0..100 barter compatibility score."""
    if me.id == other.id:
        return 0

    my_offer, my_want = _skill_sets(me)
    other_offer, other_want = _skill_sets(other)

    score = 0

    # Main barter logic: I can teach what they want, and they can teach what I want.
    if my_offer & other_want:
        score += 35
    if other_offer & my_want:
        score += 35

    # Partial textual overlap helps when titles are similar but not identical.
    my_offer_tokens = set().union(*[_tokens(x) for x in my_offer]) if my_offer else set()
    my_want_tokens = set().union(*[_tokens(x) for x in my_want]) if my_want else set()
    other_offer_tokens = set().union(*[_tokens(x) for x in other_offer]) if other_offer else set()
    other_want_tokens = set().union(*[_tokens(x) for x in other_want]) if other_want else set()

    if my_offer_tokens & other_want_tokens:
        score += 10
    if other_offer_tokens & my_want_tokens:
        score += 10

    if me.city and other.city and me.city.lower() == other.city.lower():
        score += 5

    if _time_overlap(
        me.available_from or "00:00",
        me.available_to or "23:59",
        other.available_from or "00:00",
        other.available_to or "23:59",
    ):
        score += 3

    if other.rating_points and other.rating_points > 20:
        score += 2

    return min(score, 100)


def get_matches(user: User, limit: int = 20) -> List[dict]:
    """Return cached top matches for the current user."""
    try:
        from extensions import cache
        cache_key = f"matches_{user.id}_{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        result = _compute_matches(user, limit)
        cache.set(cache_key, result, timeout=300)
        return result
    except Exception:
        return _compute_matches(user, limit)


def _compute_matches(user: User, limit: int = 20) -> List[dict]:
    from extensions import db
    from models import BannedUser

    banned_ids = {row[0] for row in db.session.query(BannedUser.user_id).all()}
    query = User.query.filter(User.id != user.id, User.onboarding_done == True)
    if banned_ids:
        query = query.filter(~User.id.in_(banned_ids))

    results = []
    for candidate in query.limit(200).all():
        score = compute_match_score(user, candidate)
        if score > 0:
            results.append({"user": candidate, "match_score": score})

    results.sort(key=lambda item: item["match_score"], reverse=True)
    return results[:limit]


def get_ml_recommendations(user: User, limit: int = 10) -> List[dict]:
    """Compatibility alias retained for templates/routes that call ML recommendations."""
    return get_matches(user, limit)
