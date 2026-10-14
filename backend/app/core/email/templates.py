from html import escape


def _template(locale: str, reset_url: str, name: str, brand: str, minutes: int, platform: bool, invitation: bool = False) -> tuple[str, str, str]:
    raw_name, raw_brand, raw_url = name, brand, reset_url
    if locale == "ar":
        if invitation:  # SEC-003: a new account; its owner chooses the password
            hours = minutes // 60
            subject = f"تفعيل حسابك — {brand}"
            greeting, requested = f"مرحبًا {name}،", f"أُنشئ لك حساب في {brand}. اختر كلمة مرورك بنفسك لتفعيله."
            action, expiry, ignore = "تفعيل الحساب", f"هذا الرابط صالح لمدة {hours} ساعة ويُستخدم مرة واحدة فقط. إذا انتهت مدته فاطلب من المسؤول إعادة إرساله.", "إذا لم تكن تتوقع هذه الرسالة، يمكنك تجاهلها."
        else:
            subject = f"إعادة ضبط كلمة المرور — {brand}"
            greeting, requested = f"مرحبًا {name}،", f"تم طلب إعادة ضبط كلمة المرور لحسابك في {brand}."
            action, expiry, ignore = "إعادة ضبط كلمة المرور", f"هذا الرابط صالح لمدة {minutes} دقيقة ويُستخدم مرة واحدة فقط.", "إذا لم تطلب ذلك، يمكنك تجاهل هذه الرسالة."
        direction = "rtl"
    else:
        if invitation:
            hours = minutes // 60
            subject = f"Activate your account — {brand}"
            greeting, requested = f"Hello {name},", f"An account was created for you at {brand}. Choose your own password to activate it."
            action, expiry, ignore = "Activate account", f"This link is valid for {hours} hours and can only be used once. If it expires, ask your administrator to send it again.", "If you were not expecting this, you can safely ignore this email."
        else:
            subject = f"Password Reset — {brand}"
            greeting, requested = f"Hello {name},", f"A password reset was requested for your account at {brand}."
            action, expiry, ignore = "Reset Password", f"This link is valid for {minutes} minutes and can only be used once.", "If you did not request this, you can safely ignore this email."
        direction = "ltr"
    text = f"{greeting}\n\n{requested}\n\n{reset_url}\n\n{expiry}\n\n{ignore}"
    name, brand, reset_url = escape(raw_name), escape(raw_brand), escape(raw_url, quote=True)
    greeting, requested = escape(greeting), escape(requested)
    fallback = 'إذا لم يعمل الزر، انسخ الرابط التالي وافتحه في المتصفح:' if locale == 'ar' else 'If the button does not work, copy this link into your browser:'
    security = 'لا تشارك هذا الرابط أو كلمة المرور مع أي شخص.' if locale == 'ar' else 'Do not share this link or your password with anyone.'
    text += f"\n\n{security}"
    html = f'<div dir="{direction}" style="font-family:Segoe UI,Tahoma,sans-serif;max-width:600px;margin:auto;padding:20px"><h2>{action}</h2><p>{greeting}</p><p>{requested}</p><p style="text-align:center;margin:30px"><a href="{reset_url}" style="background:#2563eb;color:white;padding:12px 32px;text-decoration:none;border-radius:8px">{action}</a></p><p>{expiry}</p><p>{fallback}</p><p dir="ltr" style="word-break:break-all"><a href="{reset_url}">{reset_url}</a></p><p>{ignore}</p><p>{security}</p><hr><small>{brand}</small></div>'

    return subject, html, text


def build_tenant_reset_email(locale: str, reset_url: str, user_name: str, org_name: str, expiry_minutes: int = 30, invitation: bool = False):
    return _template(locale, reset_url, user_name, f"{org_name} — IORP", expiry_minutes, False, invitation)


def build_platform_reset_email(locale: str, reset_url: str, account_name: str, expiry_minutes: int = 30, invitation: bool = False):
    return _template(locale, reset_url, account_name, "IORP Platform" if locale != "ar" else "منصة IORP", expiry_minutes, True, invitation)
