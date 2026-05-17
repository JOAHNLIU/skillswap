# filepath: skillswap/admin/routes.py
"""
SkillSwap — Admin Blueprint.
Access: тільки users з is_admin=True.
Права надаються виключно через CLI: flask make-admin <email>
"""

import os
from functools import wraps
from flask import render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from extensions import db
from models import User, Skill, Exchange, Review, Notification
from skillswap.admin import admin_bp


# ── Decorator ─────────────────────────────────────────────────────────────

def admin_required(f):
    """Allow access only to users with is_admin=True."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────────────────────

@admin_bp.route("/")
@admin_required
def dashboard():
    from models import Report, BannedUser, SupportTicket
    stats = {
        "users":           User.query.count(),
        "admins":          User.query.filter_by(is_admin=True).count(),
        "skills":          Skill.query.count(),
        "exchanges":       Exchange.query.count(),
        "completed":       Exchange.query.filter_by(status="completed").count(),
        "pending":         Exchange.query.filter_by(status="pending").count(),
        "reviews":         Review.query.count(),
        "notifications":   Notification.query.count(),
        "skills_offer":    Skill.query.filter_by(skill_type="offer").count(),
        "skills_want":     Skill.query.filter_by(skill_type="want").count(),
        "reports_pending": Report.query.filter_by(status="pending").count(),
        "banned":          BannedUser.query.count(),
        "tickets_open":    SupportTicket.query.filter_by(status="open").count(),
    }
    recent_users = User.query.order_by(User.created_at.desc()).limit(8).all()
    return render_template(
        "admin/dashboard.html",
        title="Адмін-панель",
        stats=stats,
        recent_users=recent_users,
    )


# ── Users ─────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@admin_required
def users():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        query = query.filter(
            (User.email.ilike(f"%{q}%")) | (User.full_name.ilike(f"%{q}%"))
        )
    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template(
        "admin/users.html",
        title="Адмін — Юзери",
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id: int):
    if user_id == current_user.id:
        flash("Не можна видалити власний акаунт.", "danger")
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    from skillswap.audit import log_action
    log_action("delete_user", "user", user_id,
               old_value=user.email, new_value="deleted")
    db.session.delete(user)
    db.session.commit()
    flash(f"Юзера {user.email} видалено.", "warning")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-verify", methods=["POST"])
@admin_required
def toggle_verify(user_id: int):
    """Grant or revoke verified badge."""
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    action = "надано" if user.is_verified else "знято"
    flash(f"Верифікацію {action} для {user.email}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/tickets")
@admin_required
def tickets():
    """Admin view of all support tickets."""
    from models import SupportTicket
    status = request.args.get("status", "open")
    query = SupportTicket.query
    if status:
        query = query.filter_by(status=status)
    tickets_list = query.order_by(SupportTicket.created_at.desc()).all()
    return render_template("admin/tickets.html", title="Тікети підтримки",
                           tickets=tickets_list, status=status)


@admin_bp.route("/tickets/<int:ticket_id>/reply", methods=["POST"])
@admin_required
def reply_ticket(ticket_id: int):
    """Admin reply to a support ticket."""
    from models import SupportTicket
    ticket = SupportTicket.query.get_or_404(ticket_id)
    reply = request.form.get("reply", "").strip()
    new_status = request.form.get("status", ticket.status)
    if reply:
        ticket.admin_reply = reply
    if new_status in ("open", "in_progress", "resolved", "closed"):
        ticket.status = new_status
    db.session.commit()
    flash("Відповідь збережено.", "success")
    return redirect(url_for("admin.tickets"))


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id: int):
    """Grant or revoke admin rights. Only superadmin (id=1) can do this."""
    if current_user.id != 1:
        flash("Тільки головний адмін може керувати правами.", "danger")
        abort(403)
    if user_id == current_user.id:
        flash("Не можна змінити власні права.", "danger")
        return redirect(url_for("admin.users"))
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    action = "надано" if user.is_admin else "забрано"
    flash(f"Права адміна {action} для {user.email}.", "success")
    return redirect(url_for("admin.users"))


# ── Skills ────────────────────────────────────────────────────────────────

@admin_bp.route("/skills")
@admin_required
def skills():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "").strip()
    query = Skill.query
    if q:
        query = query.filter(Skill.title.ilike(f"%{q}%"))
    pagination = query.order_by(Skill.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template(
        "admin/skills.html",
        title="Адмін — Навички",
        pagination=pagination,
        q=q,
    )


@admin_bp.route("/skills/<int:skill_id>/delete", methods=["POST"])
@admin_required
def delete_skill(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    db.session.delete(skill)
    db.session.commit()
    flash(f"Навичку «{skill.title}» видалено.", "warning")
    return redirect(url_for("admin.skills"))


# ── Exchanges ─────────────────────────────────────────────────────────────

@admin_bp.route("/exchanges")
@admin_required
def exchanges():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "")
    query = Exchange.query
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(Exchange.created_at.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template(
        "admin/exchanges.html",
        title="Адмін — Обміни",
        pagination=pagination,
        status=status,
    )


# ── Reports management ────────────────────────────────────────────────────

@admin_bp.route("/reports")
@admin_required
def reports():
    """List all user reports."""
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "pending")
    from models import Report
    query = Report.query
    if status:
        query = query.filter_by(status=status)
    pagination = query.order_by(Report.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template(
        "admin/reports.html",
        title="Адмін — Жалоби",
        pagination=pagination,
        status=status,
    )


@admin_bp.route("/reports/<int:report_id>/update", methods=["POST"])
@admin_required
def update_report(report_id: int):
    """Change report status."""
    from models import Report
    report = Report.query.get_or_404(report_id)
    new_status = request.form.get("status", "reviewed")
    if new_status in ("reviewed", "dismissed", "pending"):
        report.status = new_status
        db.session.commit()
        flash(f"Статус жалоби #{report_id} змінено на «{new_status}».", "success")
    return redirect(url_for("admin.reports"))


# ── Ban management ────────────────────────────────────────────────────────

@admin_bp.route("/banned")
@admin_required
def banned_list():
    """List all banned users."""
    from models import BannedUser
    bans = BannedUser.query.order_by(BannedUser.banned_at.desc()).all()
    return render_template(
        "admin/banned.html",
        title="Адмін — Заблоковані",
        bans=bans,
    )


@admin_bp.route("/users/<int:user_id>/ban", methods=["GET", "POST"])
@admin_required
def ban_user(user_id: int):
    """Ban a user account."""
    from models import BannedUser
    from forms import BanForm
    if user_id == current_user.id:
        flash("Не можна заблокувати себе.", "danger")
        return redirect(url_for("admin.users"))

    user = User.query.get_or_404(user_id)
    if user.ban_record:
        flash(f"{user.email} вже заблоковано.", "warning")
        return redirect(url_for("admin.users"))

    form = BanForm()
    if form.validate_on_submit():
        ban = BannedUser(
            user_id=user.id,
            banned_by_id=current_user.id,
            reason=form.reason.data.strip(),
        )
        db.session.add(ban)
        db.session.commit()
        flash(f"Користувача {user.email} заблоковано.", "warning")
        return redirect(url_for("admin.users"))

    return render_template(
        "admin/ban_form.html",
        title="Заблокувати користувача",
        form=form,
        target_user=user,
    )


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id: int):
    """Remove ban from user."""
    from models import BannedUser
    ban = BannedUser.query.filter_by(user_id=user_id).first_or_404()
    from skillswap.audit import log_action
    log_action("unban_user", "user", user_id,
               old_value="banned", new_value="active")
    from skillswap.audit import log_action
    log_action('unban_user','user',user_id,old_value='banned',new_value='active')
    db.session.delete(ban)
    db.session.commit()
    flash(f"Бан знято.", "success")
    return redirect(url_for("admin.banned_list"))


# ── Export CSV ────────────────────────────────────────────────────────────

@admin_bp.route("/export/users")
@admin_required
def export_users():
    """Export all users as CSV."""
    import csv
    import io
    from flask import Response
    users = User.query.order_by(User.created_at.desc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id","email","full_name","city","age","gender",
                 "rating_points","review_count","is_admin","is_banned","created_at"])
    for u in users:
        cw.writerow([u.id, u.email, u.full_name, u.city, u.age,
                     u.gender, u.rating_points, u.review_count,
                     u.is_admin, u.is_banned,
                     u.created_at.strftime("%Y-%m-%d %H:%M")])
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=skillswap_users.csv"}
    )


@admin_bp.route("/export/exchanges")
@admin_required
def export_exchanges():
    """Export all exchanges as CSV."""
    import csv, io
    from flask import Response
    exchanges = Exchange.query.order_by(Exchange.created_at.desc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["id","proposer","receiver","status","created_at"])
    for ex in exchanges:
        cw.writerow([ex.id, ex.proposer.email, ex.receiver.email,
                     ex.status, ex.created_at.strftime("%Y-%m-%d %H:%M")])
    return Response(io.StringIO(si.getvalue()).read(),
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=skillswap_exchanges.csv"})


@admin_bp.route("/charts-data")
@admin_required
def charts_data():
    """Return JSON data for admin charts (registrations per day, exchanges per day)."""
    from flask import jsonify
    from sqlalchemy import func, text
    # Use strftime for SQLite compatibility
    reg_data = (
        db.session.query(
            func.strftime("%Y-%m-%d", User.created_at).label("day"),
            func.count(User.id).label("count")
        )
        .group_by("day")
        .order_by("day")
        .limit(30)
        .all()
    )
    exch_data = (
        db.session.query(
            func.strftime("%Y-%m-%d", Exchange.created_at).label("day"),
            func.count(Exchange.id).label("count")
        )
        .group_by("day")
        .order_by("day")
        .limit(30)
        .all()
    )
    return jsonify({
        "registrations": [{"day": r.day, "count": r.count} for r in reg_data],
        "exchanges":     [{"day": r.day, "count": r.count} for r in exch_data],
    })


# ── Audit Log ─────────────────────────────────────────────────────────────────

@admin_bp.route("/audit")
@admin_required
def audit_log():
    """View immutable audit trail."""
    from models import AuditLog
    from skillswap.rbac import has_permission
    if not has_permission(current_user, "can_view_audit_log"):
        abort(403)
    page   = request.args.get("page", 1, type=int)
    action = request.args.get("action", "")
    query  = AuditLog.query
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    return render_template("admin/audit.html", title="Аудит-лог",
                           pagination=pagination, action=action)


# ── Disputes ──────────────────────────────────────────────────────────────────

@admin_bp.route("/disputes")
@admin_required
def disputes_list():
    """List all disputes."""
    from models import Dispute
    status = request.args.get("status", "open")
    query  = Dispute.query
    if status:
        query = query.filter_by(status=status)
    disputes = query.order_by(Dispute.created_at.desc()).all()
    return render_template("admin/disputes.html", title="Диспути",
                           disputes=disputes, status=status)


# ── RBAC Management ───────────────────────────────────────────────────────────

@admin_bp.route("/roles")
@admin_required
def roles():
    """Show all roles and their permissions."""
    from models import Role
    from skillswap.rbac import has_permission
    if not has_permission(current_user, "can_manage_admins"):
        abort(403)
    all_roles = Role.query.order_by(Role.priority).all()
    return render_template("admin/roles.html", title="Ролі та права",
                           roles=all_roles)


@admin_bp.route("/users/<int:user_id>/set-role", methods=["POST"])
@admin_required
def set_user_role(user_id: int):
    """Assign a role to a user."""
    from models import Role
    from skillswap.rbac import has_permission
    from skillswap.audit import log_action
    if not has_permission(current_user, "can_manage_admins"):
        abort(403)
    user = User.query.get_or_404(user_id)
    role_slug = request.form.get("role_slug", "")
    role = Role.query.filter_by(slug=role_slug).first()
    if not role:
        flash("Роль не знайдена.", "danger")
        return redirect(url_for("admin.users"))

    # Remove old roles, assign new. Dynamic relationship returns AppenderQuery,
    # therefore .clear() is not available; delete association rows directly.
    from models import user_roles
    db.session.execute(user_roles.delete().where(user_roles.c.user_id == user.id))
    if role_slug != "user":   # "user" = no special role needed
        user.roles.append(role)

    # Keep legacy is_admin flag in sync for admin_required decorator.
    user.is_admin = role.priority >= 20
    db.session.commit()
    log_action("set_user_role", "user", user_id,
               new_value=role_slug, actor_id=current_user.id)
    db.session.commit()
    flash(f"Роль «{role.name}» призначено для {user.email}.", "success")
    return redirect(url_for("admin.users"))

