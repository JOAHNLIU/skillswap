# filepath: skillswap/agreements/routes.py
from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Exchange, ExchangeAgreement
from skillswap.agreements import agreements_bp
from skillswap.audit import log_action


def _notify(user_id, title, body="", link="", notif_type=""):
    """Safe wrapper around notify() to avoid circular imports."""
    try:
        from skillswap.notifications.routes import notify
        notify(user_id=user_id, title=title, body=body, link=link, notif_type=notif_type)
    except Exception:
        pass


@agreements_bp.route("/exchange/<int:exchange_id>", methods=["GET", "POST"])
@login_required
def view(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    if exchange.status not in ("accepted", "completed"):
        flash("Контракт доступний лише для прийнятих обмінів.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    agreement = ExchangeAgreement.query.filter_by(exchange_id=exchange_id).first()

    if request.method == "POST" and not agreement:
        if current_user.id != exchange.proposer_id:
            flash("Умови встановлює ініціатор обміну.", "warning")
            return redirect(url_for("agreements.view", exchange_id=exchange_id))

        ip = (request.environ.get("HTTP_X_FORWARDED_FOR") or request.remote_addr or "")[:45]
        agreement = ExchangeAgreement(
            exchange_id=exchange_id,
            sessions_count=int(request.form.get("sessions_count", 1)),
            format=request.form.get("format", "online"),
            language=request.form.get("language", "Українська").strip(),
            deadline_days=int(request.form.get("deadline_days", 30)),
            description=request.form.get("description", "").strip(),
            proposer_agreed_at=datetime.now(timezone.utc),
            proposer_ip=ip,
        )
        db.session.add(agreement)
        log_action("agreement_created", "exchange", exchange_id,
                   new_value=f"sessions={agreement.sessions_count}")
        _notify(
            exchange.receiver_id,
            "Ініціатор встановив умови контракту",
            body="Перегляньте умови та підпишіть контракт, щоб відкрити дзвінок.",
            link=url_for("agreements.view", exchange_id=exchange.id),
            notif_type="agreement_created",
        )
        db.session.commit()
        flash("✅ Умови встановлено! Партнер отримав повідомлення для підпису.", "success")
        return redirect(url_for("agreements.view", exchange_id=exchange_id))

    return render_template(
        "agreements/view.html",
        title=f"Контракт — Обмін #{exchange_id}",
        exchange=exchange,
        agreement=agreement,
        is_proposer=current_user.id == exchange.proposer_id,
    )


@agreements_bp.route("/exchange/<int:exchange_id>/sign", methods=["POST"])
@login_required
def sign(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)

    agreement = ExchangeAgreement.query.filter_by(exchange_id=exchange_id).first()
    if not agreement:
        flash("Спочатку ініціатор має встановити умови.", "warning")
        return redirect(url_for("agreements.view", exchange_id=exchange_id))

    ip = (request.environ.get("HTTP_X_FORWARDED_FOR") or request.remote_addr or "")[:45]
    now = datetime.now(timezone.utc)

    if current_user.id == exchange.proposer_id and not agreement.proposer_agreed_at:
        agreement.proposer_agreed_at = now
        agreement.proposer_ip = ip
        _notify(
            exchange.receiver_id,
            "Ініціатор підписав контракт",
            body="Тепер потрібен ваш підпис для активації дзвінка.",
            link=url_for("agreements.view", exchange_id=exchange.id),
            notif_type="agreement_signed",
        )
        db.session.commit()
        flash("✅ Ви підписали контракт.", "success")
    elif current_user.id == exchange.receiver_id and not agreement.receiver_agreed_at:
        agreement.receiver_agreed_at = now
        agreement.receiver_ip = ip
        _notify(
            exchange.proposer_id,
            "Партнер підписав контракт",
            body="Контракт підписано обома сторонами. Дзвінок тепер доступний.",
            link=url_for("exchanges.detail", exchange_id=exchange.id),
            notif_type="agreement_signed",
        )
        log_action("agreement_signed_both", "exchange", exchange_id, new_value="fully_signed")
        db.session.commit()
        flash("✅ Контракт підписано обома сторонами! Дзвінок тепер доступний.", "success")
    else:
        flash("Ви вже підписали або немає прав.", "info")

    return redirect(url_for("agreements.view", exchange_id=exchange_id))
