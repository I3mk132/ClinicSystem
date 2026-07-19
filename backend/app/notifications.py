"""
Pluggable notification service for OTP codes (account verification & password
reset). Two channels, each with a swappable provider selected purely from
.env - no code changes needed to go from local development to production:

  EMAIL_PROVIDER = "console" (default) -> prints the email to the backend log
  EMAIL_PROVIDER = "smtp"              -> sends a real email via SMTP

  SMS_PROVIDER = "console" (default)   -> prints the SMS to the backend log
  SMS_PROVIDER = "twilio"              -> sends a real SMS via Twilio

"console" is the default so the whole verification/reset flow works out of
the box with zero external accounts - perfect for local development and for
demoing this template. Switch to real providers by filling in the SMTP_* /
TWILIO_* values in .env and installing `twilio` (see requirements.txt).
"""
import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger("clinic.notifications")
logging.basicConfig(level=logging.INFO)


def _send_email_console(to: str, subject: str, body: str) -> None:
    logger.info(
        "\n"
        "==================== EMAIL (console provider) ====================\n"
        f"To:      {to}\n"
        f"Subject: {subject}\n"
        f"{body}\n"
        "===================================================================="
    )


def _send_email_smtp(to: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError("EMAIL_PROVIDER=smtp but SMTP_HOST is not configured in .env")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>"
    msg["To"] = to

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM_ADDRESS, [to], msg.as_string())


def _send_sms_console(to: str, body: str) -> None:
    logger.info(
        "\n"
        "==================== SMS (console provider) ======================\n"
        f"To: {to}\n"
        f"{body}\n"
        "===================================================================="
    )


def _send_sms_twilio(to: str, body: str) -> None:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        raise RuntimeError("SMS_PROVIDER=twilio but TWILIO_* settings are not configured in .env")
    try:
        from twilio.rest import Client  # optional dependency, see requirements.txt
    except ImportError as exc:
        raise RuntimeError("SMS_PROVIDER=twilio requires the 'twilio' package: pip install twilio") from exc

    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    client.messages.create(to=to, from_=settings.TWILIO_FROM_NUMBER, body=body)


def send_email(to: str, subject: str, body: str) -> None:
    if settings.EMAIL_PROVIDER == "smtp":
        _send_email_smtp(to, subject, body)
    else:
        _send_email_console(to, subject, body)


def send_sms(to: str, body: str) -> None:
    if settings.SMS_PROVIDER == "twilio":
        _send_sms_twilio(to, body)
    else:
        _send_sms_console(to, body)


def send_otp(channel: str, destination: str, code: str, purpose: str, lang: str = "ar") -> None:
    """
    channel: "email" or "phone"
    purpose: "password_reset" (the only OTP flow left - signup OTP was removed)
    """
    texts = {
        "ar": {
            "password_reset": ("رمز إعادة تعيين كلمة المرور", f"رمز إعادة تعيين كلمة المرور هو: {code}\nصالح لمدة {settings.OTP_EXPIRE_MINUTES} دقائق. إذا لم تطلب هذا، تجاهل الرسالة."),
        },
        "tr": {
            "password_reset": ("Şifre Sıfırlama Kodu", f"Şifre sıfırlama kodunuz: {code}\n{settings.OTP_EXPIRE_MINUTES} dakika geçerlidir. Bu talebi siz yapmadıysanız bu mesajı yok sayın."),
        },
    }
    subject, body = texts.get(lang, texts["ar"])[purpose]

    if channel == "email":
        send_email(destination, subject, body)
    else:
        send_sms(destination, body)
