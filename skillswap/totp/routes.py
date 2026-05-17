# filepath: skillswap/totp/routes.py
"""
SkillSwap — Two-Factor Authentication (TOTP).
Setup, verify, disable via Google Authenticator / Authy.
"""

import io
import base64
import pyotp
import qrcode
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from extensions import db
from skillswap.totp import totp_bp


def _generate_qr_base64(uri: str) -> str:
    """Generate QR code as base64 PNG string."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@totp_bp.route("/setup", methods=["GET", "POST"])
@login_required
def setup():
    """Show QR code and confirm TOTP setup."""
    user = current_user
    if user.totp_enabled:
        flash("2FA вже увімкнено.", "info")
        return redirect(url_for("users.profile", user_id=user.id))

    # Generate secret if not exists
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        db.session.commit()

    totp = pyotp.TOTP(user.totp_secret)
    uri = totp.provisioning_uri(
        name=user.email,
        issuer_name="SkillSwap"
    )
    qr_b64 = _generate_qr_base64(uri)

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        if totp.verify(code, valid_window=1):
            user.totp_enabled = True
            db.session.commit()
            flash("✅ Двофакторна автентифікація увімкнена!", "success")
            return redirect(url_for("users.profile", user_id=user.id))
        flash("❌ Невірний код. Спробуйте ще раз.", "danger")

    return render_template(
        "totp/setup.html",
        title="Налаштування 2FA",
        qr_b64=qr_b64,
        secret=user.totp_secret,
    )


@totp_bp.route("/disable", methods=["POST"])
@login_required
def disable():
    """Disable TOTP for current user."""
    code = request.form.get("code", "").strip()
    user = current_user
    if not user.totp_enabled or not user.totp_secret:
        flash("2FA не увімкнено.", "info")
        return redirect(url_for("users.profile", user_id=user.id))
    totp = pyotp.TOTP(user.totp_secret)
    if totp.verify(code, valid_window=1):
        user.totp_enabled = False
        user.totp_secret = None
        db.session.commit()
        flash("2FA вимкнено.", "warning")
    else:
        flash("Невірний код.", "danger")
    return redirect(url_for("users.profile", user_id=user.id))


@totp_bp.route("/verify", methods=["GET", "POST"])
def verify():
    """Verify TOTP code after password login (second factor)."""
    if "pending_user_id" not in session:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        from flask_login import login_user
        from models import User
        from datetime import datetime, timezone
        code = request.form.get("code", "").strip()
        user = db.session.get(User, session["pending_user_id"])
        if user:
            valid = False
            # Check TOTP app code
            if user.totp_secret:
                totp = pyotp.TOTP(user.totp_secret)
                if totp.verify(code, valid_window=1):
                    valid = True
            # Check email code
            if not valid and user.totp_email_code and user.totp_email_expires:
                expires = user.totp_email_expires
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if (user.totp_email_code == code and
                        datetime.now(timezone.utc) < expires):
                    valid = True
                    user.totp_email_code = None
                    user.totp_email_expires = None
                    db.session.commit()
            if valid:
                session.pop("pending_user_id", None)
                login_user(user)
                flash("Ласкаво просимо! 🎉", "success")
                return redirect(url_for("main.dashboard"))
        flash("Невірний або застарілий код. Спробуйте ще раз.", "danger")

    return render_template("totp/verify.html", title="Введіть код 2FA")


# ── Email-based 2FA ───────────────────────────────────────────────────────────

@totp_bp.route("/send-email-code", methods=["POST"])
def send_email_code():
    """Send a 6-digit code to user email for 2FA. Valid 5 minutes."""
    if "pending_user_id" not in session:
        return redirect(url_for("auth.login"))

    from models import User
    from extensions import db as _db
    import random
    from datetime import datetime, timezone, timedelta

    user = _db.session.get(User, session["pending_user_id"])
    if not user:
        return redirect(url_for("auth.login"))

    code = f"{random.randint(0, 999999):06d}"
    user.totp_email_code = code
    user.totp_email_expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    _db.session.commit()

    try:
        from skillswap.email_service import send_exchange_notification
        send_exchange_notification(
            user,
            "Код підтвердження входу",
            f"""
            <h3>Код входу в SkillSwap</h3>
            <p>Ваш одноразовий код підтвердження:</p>
            <div style="font-size:2.5rem;font-weight:bold;letter-spacing:.5rem;
                        color:#6366f1;text-align:center;padding:1rem;
                        background:#f0f4ff;border-radius:12px;margin:1rem 0;">
              {code}
            </div>
            <p style="color:#666;font-size:13px;">Код дійсний 5 хвилин.<br>
            Якщо ви не намагались увійти — змініть пароль.</p>
            """
        )
        flash("📧 Код надіслано на вашу пошту.", "success")
    except Exception:
        flash(f"⚠️ Не вдалося надіслати лист. Код для тестування: {code}", "warning")

    return redirect(url_for("totp.verify"))
