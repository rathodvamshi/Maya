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
    retry_delay: int = 5,
    trace_id: Optional[str] = None,
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
            logger.info(f"[EmailSend] status=success recipient={recipient} subject='{subject}' attempt={attempt+1} trace={trace_id or '-'}")
            return
        except (smtplib.SMTPException, ssl.SSLError) as e:
            attempt += 1
            logger.warning(f"[EmailSend] status=retry recipient={recipient} attempt={attempt} error='{e}' trace={trace_id or '-'}")
            time.sleep(retry_delay)
    logger.error(f"[EmailSend] status=failed recipient={recipient} subject='{subject}' attempts={max_retries} trace={trace_id or '-'}")
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


def send_html_email(to: list, subject: str, html: str, text: str = None) -> None:
    """
    Send HTML email to multiple recipients as specified in requirements.
    """
    if not to:
        raise ValueError("No recipients provided")
    
    # Use the first recipient for the main send, or send to all
    recipient = to[0] if len(to) == 1 else ", ".join(to)
    
    # Use text version if provided, otherwise extract from HTML
    if not text:
        import re
        # Simple HTML to text conversion
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\s+', ' ', text).strip()
    
    send_email(recipient, subject, text, html=html)