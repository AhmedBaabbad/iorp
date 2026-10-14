"""Account alerts by e-mail (SEC-002): best effort — an alert that cannot be sent never blocks the change it reports."""
import logging
from html import escape

from app.core.email.service import EmailService

logger = logging.getLogger(__name__)

TEXT = {
    "ar": ("تم تغيير بريد الدخول لحسابك", "مرحبًا {name}،",
           "تم تغيير البريد الإلكتروني لحسابك من {old} إلى {new} بواسطة {actor}.",
           "إن لم تكن تعلم بهذا التغيير فتواصل مع مسؤول النظام فورًا."),
    "en": ("Your sign-in e-mail was changed", "Hello {name},",
           "The e-mail of your account was changed from {old} to {new} by {actor}.",
           "If you did not expect this change, contact your administrator at once."),
}


def alert_email_change(user, old: str, new: str, actor=None, email: EmailService | None = None) -> None:
    """Tells both the old and the new address that the account's sign-in e-mail changed, and by whom."""
    lang = "en" if user.preferred_locale == "en" else "ar"
    subject, hello, line, warn = TEXT[lang]
    values = dict(name=user.full_name, old=old, new=new,
                  actor=getattr(actor, "full_name", None) or ("المسؤول" if lang == "ar" else "an administrator"))
    paragraphs = [hello.format(**values), line.format(**values), warn]
    html = (f'<div dir="{"rtl" if lang == "ar" else "ltr"}" style="font-family:Segoe UI,Tahoma,sans-serif">'
            + "".join(f"<p>{escape(p)}</p>" for p in paragraphs) + "</div>")
    try:
        service = email or EmailService()
        for address in sorted({old, new}):
            service.send_email(address, subject, html, "\n\n".join(paragraphs))
    except Exception:  # noqa: BLE001
        logger.exception("E-mail change alert not sent")
