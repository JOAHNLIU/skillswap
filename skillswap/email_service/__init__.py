import os
import re
import ssl
import smtplib
import secrets
import requests

from datetime import datetime, timezone, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import policy

from flask import current_app, url_for


def _bool_value(value, default=False):
    if value is None:
        return default

    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _plain_text(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _get_base_url():
    base_url = current_app.config.get("BASE_URL") or os.environ.get("BASE_URL")

    if base_url:
        return str(base_url).rstrip("/")

    return ""


def _set_email_token(user, token):
    if hasattr(user, "email_verification_token"):
        user.email_verification_token = token

    elif hasattr(user, "email_verify_token"):
        user.email_verify_token = token

    else:
        raise AttributeError(
            "User model has no email verification token field. "
            "Expected email_verification_token or email_verify_token."
        )

    if hasattr(user, "email_verification_expires"):
        user.email_verification_expires = datetime.now(timezone.utc) + timedelta(hours=24)


def _set_reset_token(user, token):
    if hasattr(user, "reset_token"):
        user.reset_token = token
    else:
        raise AttributeError("User model has no reset_token field.")

    if hasattr(user, "reset_token_expires"):
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=2)


def _build_message(sender, to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8").encode()
    msg["From"] = sender
    msg["To"] = to_email

    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    return msg.as_bytes(policy=policy.SMTP)


def _send_via_smtp(to_email, subject, html_body):
    smtp_server = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = int(current_app.config.get("MAIL_PORT", 465))
    smtp_username = current_app.config.get("MAIL_USERNAME")
    smtp_password = current_app.config.get("MAIL_PASSWORD")
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or smtp_username

    use_ssl = _bool_value(current_app.config.get("MAIL_USE_SSL"), default=(smtp_port == 465))
    use_tls = _bool_value(current_app.config.get("MAIL_USE_TLS"), default=(smtp_port == 587))

    if smtp_port == 465:
        use_ssl = True
        use_tls = False

    if smtp_port == 587:
        use_ssl = False
        use_tls = True

    print("=== SMTP SEND START ===", flush=True)
    print(f"=== SMTP SERVER: {smtp_server}:{smtp_port} ===", flush=True)
    print(f"=== SMTP SSL: {use_ssl} TLS: {use_tls} ===", flush=True)
    print(f"=== SMTP USER: {smtp_username} ===", flush=True)
    print(f"=== SMTP FROM: {sender} ===", flush=True)
    print(f"=== SMTP TO: {to_email} ===", flush=True)

    try:
        if not smtp_server or not smtp_username or not smtp_password or not sender:
            print("=== SMTP CONFIG ERROR ===", flush=True)
            return False

        message_bytes = _build_message(
            sender=sender,
            to_email=to_email,
            subject=subject,
            html_body=html_body,
        )

        context = ssl.create_default_context()

        if use_ssl:
            with smtplib.SMTP_SSL(
                host=smtp_server,
                port=smtp_port,
                timeout=10,
                context=context,
            ) as server:
                server.ehlo()
                server.login(smtp_username, smtp_password)
                server.sendmail(sender, [to_email], message_bytes)

        else:
            with smtplib.SMTP(
                host=smtp_server,
                port=smtp_port,
                timeout=10,
            ) as server:
                server.ehlo()

                if use_tls:
                    server.starttls(context=context)
                    server.ehlo()

                server.login(smtp_username, smtp_password)
                server.sendmail(sender, [to_email], message_bytes)

        print("=== SMTP SEND SUCCESS ===", flush=True)
        return True

    except Exception as e:
        print("=== SMTP SEND ERROR ===", flush=True)
        print(repr(e), flush=True)
        return False


def _send_via_resend(to_email, subject, html_body):
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip()

    print("=== RESEND SEND START ===", flush=True)
    print(f"=== RESEND FROM: {from_email} ===", flush=True)
    print(f"=== RESEND TO: {to_email} ===", flush=True)

    if not api_key:
        print("=== RESEND ERROR: RESEND_API_KEY is empty ===", flush=True)
        return False

    if not from_email:
        print("=== RESEND ERROR: RESEND_FROM_EMAIL is empty ===", flush=True)
        return False

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": _plain_text(html_body),
            },
            timeout=12,
        )

        print(
            f"=== RESEND RESPONSE: {response.status_code} {response.text} ===",
            flush=True,
        )

        if 200 <= response.status_code < 300:
            print("=== RESEND SEND SUCCESS ===", flush=True)
            return True

        print("=== RESEND SEND FAILED ===", flush=True)
        return False

    except Exception as e:
        print("=== RESEND SEND ERROR ===", flush=True)
        print(repr(e), flush=True)
        return False


def send_email(to_email, subject, html_body):
    provider = (
        os.environ.get("EMAIL_PROVIDER")
        or current_app.config.get("EMAIL_PROVIDER")
        or "smtp"
    ).strip().lower()

    print(f"=== EMAIL PROVIDER: {provider} ===", flush=True)

    if provider == "resend":
        return _send_via_resend(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
        )

    return _send_via_smtp(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
    )


def send_verification_email(user):
    from extensions import db

    token = secrets.token_urlsafe(32)

    _set_email_token(user, token)
    db.session.commit()

    base_url = _get_base_url()

    if base_url:
        verify_url = f"{base_url}/auth/verify-email/{token}"
    else:
        verify_url = url_for("auth.verify_email", token=token, _external=True)

    html = f"""
    <!doctype html>
    <html lang="uk">
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 560px; margin: auto; padding: 24px;">
        <h2 style="color: #6366f1;">
            SkillSwap - підтвердження email
        </h2>

        <p>Привіт!</p>

        <p>
            Для завершення реєстрації підтвердьте вашу email-адресу.
            Це потрібно, щоб ніхто не міг створити акаунт на чужу пошту.
        </p>

        <p style="margin: 28px 0;">
            <a href="{verify_url}"
               style="background: #6366f1; color: #ffffff; padding: 13px 26px;
                      border-radius: 24px; text-decoration: none; font-weight: bold;">
                Підтвердити email
            </a>
        </p>

        <p style="font-size: 13px; color: #666;">
            Якщо кнопка не працює, скопіюйте це посилання:
            <br>
            <a href="{verify_url}">{verify_url}</a>
        </p>
    </body>
    </html>
    """

    return send_email(
        to_email=user.email,
        subject="SkillSwap - підтвердження email",
        html_body=html,
    )


def send_password_reset_email(user):
    from extensions import db

    token = secrets.token_urlsafe(32)

    _set_reset_token(user, token)
    db.session.commit()

    base_url = _get_base_url()

    if base_url:
        reset_url = f"{base_url}/auth/reset-password/{token}"
    else:
        reset_url = url_for("auth.reset_password", token=token, _external=True)

    html = f"""
    <!doctype html>
    <html lang="uk">
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 560px; margin: auto; padding: 24px;">
        <h2 style="color: #6366f1;">
            SkillSwap - відновлення паролю
        </h2>

        <p>
            Для вашого акаунта створено запит на встановлення нового паролю.
        </p>

        <p style="margin: 28px 0;">
            <a href="{reset_url}"
               style="background: #6366f1; color: #ffffff; padding: 13px 26px;
                      border-radius: 24px; text-decoration: none; font-weight: bold;">
                Встановити новий пароль
            </a>
        </p>

        <p style="font-size: 13px; color: #666;">
            Посилання дійсне 2 години.
            Якщо це були не ви, просто проігноруйте цей лист.
            <br>
            <a href="{reset_url}">{reset_url}</a>
        </p>
    </body>
    </html>
    """

    return send_email(
        to_email=user.email,
        subject="SkillSwap - відновлення паролю",
        html_body=html,
    )


def send_exchange_notification(user, subject, body_html):
    return send_email(
        to_email=user.email,
        subject=f"SkillSwap - {subject}",
        html_body=body_html,
    )