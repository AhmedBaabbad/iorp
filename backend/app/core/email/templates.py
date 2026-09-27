from html import escape


def _template(locale: str, reset_url: str, name: str, brand: str, minutes: int, platform: bool) -> tuple[str, str, str]:
    name, brand, reset_url = escape(name), escape(brand), escape(reset_url, quote=True)
    if locale == "ar":
        subject = f"إعادة ضبط كلمة المرور — {brand}"
        greeting, requested = f"مرحبًا {name}،", f"تم طلب إعادة ضبط كلمة المرور لحسابك في {brand}."
        action, expiry, ignore = "إعادة ضبط كلمة المرور", f"هذا الرابط صالح لمدة {minutes} دقيقة فقط.", "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة."
        direction = "rtl"
    else:
        subject = f"Password Reset — {brand}"
        greeting, requested = f"Hello {name},", f"A password reset was requested for your account at {brand}."
        action, expiry, ignore = "Reset Password", f"This link is valid for {minutes} minutes only.", "If you did not request this, you can safely ignore this email."
        direction = "ltr"
    html = f'<div dir="{direction}" style="font-family:Segoe UI,Tahoma,sans-serif;max-width:600px;margin:auto;padding:20px"><h2>{action}</h2><p>{greeting}</p><p>{requested}</p><p style="text-align:center;margin:30px"><a href="{reset_url}" style="background:#2563eb;color:white;padding:12px 32px;text-decoration:none;border-radius:8px">{action}</a></p><p>{expiry}</p><p>{ignore}</p><hr><small>{brand}</small></div>'
    text = f"{greeting}\n\n{requested}\n\n{reset_url}\n\n{expiry}\n\n{ignore}"
    return subject, html, text


def build_tenant_reset_email(locale: str, reset_url: str, user_name: str, org_name: str, expiry_minutes: int = 30):
    return _template(locale, reset_url, user_name, f"{org_name} — IORP", expiry_minutes, False)


def build_platform_reset_email(locale: str, reset_url: str, account_name: str, expiry_minutes: int = 30):
    return _template(locale, reset_url, account_name, "IORP Platform" if locale != "ar" else "منصة IORP", expiry_minutes, True)
