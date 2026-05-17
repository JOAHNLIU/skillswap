from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required

from extensions import db
from models import User
from skillswap.email_service import send_verification_email, send_password_reset_email
from . import auth_bp


def _get_email_token(user):
    return getattr(user, "email_verification_token", None) or getattr(user, "email_verify_token", None)


def _clear_email_token(user):
    if hasattr(user, "email_verification_token"):
        user.email_verification_token = None

    if hasattr(user, "email_verify_token"):
        user.email_verify_token = None

    if hasattr(user, "email_verification_expires"):
        user.email_verification_expires = None


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        if not getattr(current_user, "email_verified", False):
            return redirect(url_for("auth.check_email"))

        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        print("=== REGISTER POST ===", flush=True)
        print(f"=== REGISTER EMAIL: {email} ===", flush=True)

        if not full_name or not email or not password:
            flash("Заповніть усі поля.", "danger")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Пошта вже зареєстрована. Увійдіть або скористайтесь відновленням паролю.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            full_name=full_name,
            email=email,
            email_verified=False,
        )

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        login_user(user)

        try:
            sent = send_verification_email(user)
            print(f"=== REGISTER EMAIL SEND RESULT: {sent} ===", flush=True)

            if sent:
                flash("Лист підтвердження надіслано. Перевірте пошту.", "success")
            else:
                flash("Не вдалося надіслати лист. Натисніть «Надіслати лист повторно».", "danger")

        except Exception as e:
            print(f"=== REGISTER EMAIL SEND ERROR: {e} ===", flush=True)
            flash("Не вдалося надіслати лист. Натисніть «Надіслати лист повторно».", "danger")

        return redirect(url_for("auth.check_email"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if not getattr(current_user, "email_verified", False):
            return redirect(url_for("auth.check_email"))

        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        action = request.form.get("action", "login")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        print("=== LOGIN POST ===", flush=True)
        print(f"=== LOGIN ACTION: {action} ===", flush=True)
        print(f"=== LOGIN EMAIL: {email} ===", flush=True)

        if action == "reset_password":
            session["password_reset_email"] = email

            if not email:
                flash("Спочатку введіть email акаунта у полі входу.", "warning")
                return redirect(url_for("auth.login"))

            user = User.query.filter_by(email=email).first()

            print(f"=== PASSWORD RESET USER EXISTS: {bool(user)} ===", flush=True)

            if user:
                try:
                    sent = send_password_reset_email(user)
                    print(f"=== PASSWORD RESET SEND RESULT: {sent} ===", flush=True)
                except Exception as e:
                    print(f"=== PASSWORD RESET SEND ERROR: {e} ===", flush=True)

            flash(
                "Якщо акаунт із цією поштою існує, ми надіслали лист для встановлення нового паролю.",
                "info",
            )
            return redirect(url_for("auth.forgot_password_sent"))

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Неправильний email або пароль.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user)

        if not getattr(user, "email_verified", False):
            print("=== LOGIN USER EMAIL NOT VERIFIED ===", flush=True)

            try:
                sent = send_verification_email(user)
                print(f"=== LOGIN VERIFICATION EMAIL SEND RESULT: {sent} ===", flush=True)

                if sent:
                    flash("Лист підтвердження надіслано. Перевірте пошту.", "success")
                else:
                    flash("Не вдалося надіслати лист автоматично. Натисніть «Надіслати лист повторно».", "danger")

            except Exception as e:
                print(f"=== LOGIN VERIFICATION EMAIL SEND ERROR: {e} ===", flush=True)
                flash("Не вдалося надіслати лист автоматично. Натисніть «Надіслати лист повторно».", "danger")

            return redirect(url_for("auth.check_email"))

        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Ви вийшли з акаунта.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/check-email")
@login_required
def check_email():
    if getattr(current_user, "email_verified", False):
        return redirect(url_for("onboarding.profile"))

    return render_template("auth/check_email.html")


@auth_bp.route("/resend-verification", methods=["GET", "POST"])
@login_required
def resend_verification():
    print("=== RESEND VERIFICATION CLICKED ===", flush=True)
    print(f"=== CURRENT USER EMAIL: {current_user.email} ===", flush=True)

    if getattr(current_user, "email_verified", False):
        flash("Email вже підтверджено.", "success")
        return redirect(url_for("main.dashboard"))

    try:
        sent = send_verification_email(current_user)
        print(f"=== RESEND VERIFICATION RESULT: {sent} ===", flush=True)

        if sent:
            flash("Лист підтвердження повторно надіслано. Перевірте пошту.", "success")
        else:
            flash("Не вдалося надіслати лист. Перевірте SMTP-налаштування.", "danger")

    except Exception as e:
        print(f"=== RESEND VERIFICATION ERROR: {e} ===", flush=True)
        flash(f"Помилка надсилання листа: {str(e)}", "danger")

    return redirect(url_for("auth.check_email"))


@auth_bp.route("/verify-email/<token>")
@login_required
def verify_email(token):
    stored_token = _get_email_token(current_user)

    if not stored_token or stored_token != token:
        flash("Недійсне посилання підтвердження.", "danger")
        return redirect(url_for("auth.check_email"))

    expires = getattr(current_user, "email_verification_expires", None)

    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires < datetime.now(timezone.utc):
            flash("Посилання підтвердження застаріло. Надішліть лист повторно.", "danger")
            return redirect(url_for("auth.check_email"))

    current_user.email_verified = True
    _clear_email_token(current_user)

    db.session.commit()

    flash("Email успішно підтверджено.", "success")
    return redirect(url_for("onboarding.profile"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password/sent")
def forgot_password_sent():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    return render_template("auth/forgot_password_sent.html")


@auth_bp.route("/forgot-password/resend", methods=["POST"])
def resend_password_reset():
    print("=== PASSWORD RESET RESEND CLICKED ===", flush=True)

    if current_user.is_authenticated:
        print("=== PASSWORD RESET RESEND BLOCKED: USER AUTHENTICATED ===", flush=True)
        return redirect(url_for("main.dashboard"))

    email = session.get("password_reset_email", "").strip().lower()

    print(f"=== PASSWORD RESET RESEND EMAIL FROM SESSION: {email} ===", flush=True)

    if not email:
        flash("Email для повторного надсилання не знайдено. Введіть email на сторінці входу.", "warning")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    print(f"=== PASSWORD RESET RESEND USER EXISTS: {bool(user)} ===", flush=True)

    if user:
        try:
            sent = send_password_reset_email(user)
            print(f"=== PASSWORD RESET RESEND SEND RESULT: {sent} ===", flush=True)
        except Exception as e:
            print(f"=== PASSWORD RESET RESEND SEND ERROR: {e} ===", flush=True)

    flash(
        "Якщо акаунт із цією поштою існує, ми повторно надіслали лист.",
        "info",
    )

    return redirect(url_for("auth.forgot_password_sent"))


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    user = User.query.filter_by(reset_token=token).first()

    if not user:
        flash("Посилання недійсне або застаріле.", "danger")
        return redirect(url_for("auth.login"))

    expires = getattr(user, "reset_token_expires", None)

    if expires:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires < datetime.now(timezone.utc):
            flash("Посилання застаріло. Створіть новий запит.", "danger")
            return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if len(password) < 6:
            flash("Пароль має містити мінімум 6 символів.", "danger")
            return render_template("auth/reset_password.html", token=token)

        if password != password2:
            flash("Паролі не збігаються.", "danger")
            return render_template("auth/reset_password.html", token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expires = None

        db.session.commit()

        session.pop("password_reset_email", None)

        flash("Пароль успішно змінено. Увійдіть із новим паролем.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)