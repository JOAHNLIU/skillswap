# filepath: skillswap/trust/routes.py
from flask import render_template, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from extensions import db
from models import Skill, SkillTrustScore
from skillswap.trust import trust_bp
from skillswap.trust.engine import compute_trust_score, get_trust_badge


@trust_bp.route("/skill/<int:skill_id>")
@login_required
def skill_detail(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    record = SkillTrustScore.query.filter_by(skill_id=skill_id).first()
    if not record:
        compute_trust_score(skill)
        record = SkillTrustScore.query.filter_by(skill_id=skill_id).first()
    badge_icon, badge_label = get_trust_badge(record.score if record else 0)
    return render_template("trust/skill_detail.html", title=f"Trust — {skill.title}",
                           skill=skill, record=record,
                           badge_icon=badge_icon, badge_label=badge_label)


@trust_bp.route("/skill/<int:skill_id>/recalc", methods=["POST"])
@login_required
def recalculate(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    new_score = compute_trust_score(skill)
    flash(f"✅ Trust Score оновлено: {new_score}/100", "success")
    return redirect(url_for("trust.skill_detail", skill_id=skill_id))


@trust_bp.route("/leaderboard")
@login_required
def leaderboard():
    top = (SkillTrustScore.query
           .filter(SkillTrustScore.score > 0)
           .order_by(SkillTrustScore.score.desc())
           .limit(20).all())
    entries = []
    for ts in top:
        skill = db.session.get(Skill, ts.skill_id)
        if skill:
            icon, label = get_trust_badge(ts.score)
            entries.append({"skill": skill, "score": ts.score,
                            "badge_icon": icon, "badge_label": label})
    return render_template("trust/leaderboard.html",
                           title="Топ перевірених навичок", entries=entries)


@trust_bp.route("/api/skill/<int:skill_id>")
@login_required
def api_skill_trust(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    record = SkillTrustScore.query.filter_by(skill_id=skill_id).first()
    if not record:
        compute_trust_score(skill)
        record = SkillTrustScore.query.filter_by(skill_id=skill_id).first()
    icon, label = get_trust_badge(record.score if record else 0)
    return jsonify({
        "skill_id": skill_id, "skill_title": skill.title,
        "score": record.score if record else 0, "badge": label,
        "endorsements": record.endorsements_count if record else 0,
        "verified_exchanges": record.verified_exchanges if record else 0,
        "positive_reviews": record.positive_reviews if record else 0,
    })
