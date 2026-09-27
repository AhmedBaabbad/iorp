import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str | None = None) -> bool:
        try:
            if self.settings.email_mode == "console":
                logger.info("Transactional email (console mode): to=%s subject=%s\n%s", to_email, subject, text_body or html_body)
                return True
            message = MIMEMultipart("alternative")
            message["Subject"], message["From"], message["To"] = subject, self.settings.email_from, to_email
            if text_body:
                message.attach(MIMEText(text_body, "plain", "utf-8"))
            message.attach(MIMEText(html_body, "html", "utf-8"))
            with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port) as server:
                if self.settings.smtp_tls:
                    server.starttls()
                if self.settings.smtp_user:
                    server.login(self.settings.smtp_user, self.settings.smtp_password or "")
                server.send_message(message)
            return True
        except Exception:
            logger.exception("Transactional email delivery failed")
            return False
