def send_welcome_email(to_email: str) -> None:
        subject = "Welcome to Project Maya!"
        body = (
                "Thank you for registering with Project Maya.\n\n"
                "Your account is now active. Enjoy exploring our features!"
        )
        html_body = f"""
        <html>
            <body>
                <h2>Welcome to Project Maya!</h2>
                <p>Thank you for registering. Your account is now active.</p>
                <p>Enjoy exploring our features!</p>
            </body>
        </html>
        """
        send_email(to_email, subject, body, html=html_body)
import smtplib
import ssl
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.config import settings
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class EmailSendError(Exception):
    pass


def send_email(
    recipient: str,
    subject: str,
    body: str,
    html: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: int = 5
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.MAIL_FROM
    msg["To"] = recipient

    msg.attach(MIMEText(body, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    attempt = 0
    while attempt < max_retries:
        try:
            if settings.MAIL_SSL_TLS:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT, context=context) as server:
                    server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT, timeout=15) as server:
                    if settings.MAIL_STARTTLS:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    server.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
                    server.send_message(msg)
            logger.info(f"Email sent to {recipient}")
            return
        except (smtplib.SMTPException, ssl.SSLError) as e:
            attempt += 1
            logger.warning(f"Attempt {attempt} failed to send email to {recipient}: {e}")
            time.sleep(retry_delay)
    raise EmailSendError(f"Failed to send email to {recipient} after {max_retries} attempts.")


def send_otp_email(to_email: str, otp_code: str) -> None:
    subject = "Your Verification Code"
    body = (
        f"Your OTP is: {otp_code}\n\n"
        "It will expire in 5 minutes. Ignore if you didn't request it."
    )
    html_body = f"""
    <html>
      <body>
        <p>Your OTP is: <strong>{otp_code}</strong></p>
        <p>This code will expire in 5 minutes. If you didn't request this, you can ignore it.</p>
      </body>
    </html>
    """
    send_email(to_email, subject, body, html=html_body)
