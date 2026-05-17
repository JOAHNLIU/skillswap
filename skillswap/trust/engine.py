# filepath: skillswap/trust/engine.py
"""SkillSwap — Trust Score Engine (0-100 per skill)."""

from __future__ import annotations


def compute_trust_score(skill) -> float:
    from models import Endorsement, Exchange, Review, Dispute, SkillTrustScore
    from extensions import db

    record = SkillTrustScore.query.filter_by(skill_id=skill.id).first()
    if not record:
        record = SkillTrustScore(skill_id=skill.id)
        db.session.add(record)

    score = 0.0

    # Partners who completed an exchange with this user
    completed_partners = set()
    for ex in Exchange.query.filter(
        ((Exchange.proposer_id == skill.user_id) |
         (Exchange.receiver_id == skill.user_id)),
        Exchange.status == "completed"
    ).all():
        pid = ex.receiver_id if ex.proposer_id == skill.user_id else ex.proposer_id
        completed_partners.add(pid)

    # Endorsements — verified (+10) vs unverified (+3)
    endorsements = Endorsement.query.filter_by(skill_id=skill.id).all()
    for e in endorsements:
        score += 10 if e.endorser_id in completed_partners else 3
    record.endorsements_count = len(endorsements)

    # Completed exchanges with this skill offered
    completed_with = Exchange.query.filter_by(
        offered_skill_id=skill.id, status="completed"
    ).count()
    score += completed_with * 8
    record.verified_exchanges = completed_with

    # Teaching reviews for this user
    reviews = Review.query.filter_by(
        reviewee_id=skill.user_id, review_type="teaching"
    ).all()
    positive = sum(1 for r in reviews if r.rating >= 4)
    negative = sum(1 for r in reviews if r.rating <= 2)
    score += positive * 5
    score -= negative * 8
    record.positive_reviews = positive

    # Dispute penalty
    disputes_count = 0
    try:
        disputes_count = Dispute.query.join(
            Exchange, Dispute.exchange_id == Exchange.id
        ).filter(
            Exchange.offered_skill_id == skill.id,
            Dispute.reason.in_(["poor_quality", "fraud"]),
            Dispute.status.like("resolved_%")
        ).count()
    except Exception:
        pass
    score -= disputes_count * 15

    record.score = round(max(0.0, min(100.0, score)), 1)
    db.session.commit()
    return record.score


def get_trust_badge(score: float) -> tuple:
    if score >= 80: return "🏆", "Експерт"
    if score >= 60: return "⭐", "Досвідчений"
    if score >= 40: return "✅", "Перевірений"
    if score >= 20: return "🔰", "Початківець"
    return "❓", "Невідомо"
