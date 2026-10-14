import ssl
from unittest.mock import MagicMock
import pytest
from app.core.config import Settings
from app.core.email.service import EmailService
from app.core.email.templates import build_tenant_reset_email, build_platform_reset_email


@pytest.mark.real_email
@pytest.mark.parametrize('implicit', [True, False])
def test_smtp_tls_verified_and_utf8_multipart(monkeypatch, implicit):
    service=EmailService()
    service.settings=Settings(_env_file=None,debug=False,email_mode='smtp',email_from='iorp@rehanh.com',
        smtp_host='smtp.hostinger.com',smtp_port=465 if implicit else 587,smtp_ssl=implicit,smtp_tls=not implicit,
        smtp_user='iorp@rehanh.com',smtp_password='test-only')
    smtp=MagicMock()
    server=smtp.return_value.__enter__.return_value
    monkeypatch.setattr('app.core.email.service.smtplib.SMTP_SSL' if implicit else 'app.core.email.service.smtplib.SMTP',smtp)
    assert service.send_email('test@example.test','إعادة تعيين كلمة المرور','<p>مرحبًا</p>','مرحبًا')
    context=smtp.call_args.kwargs['context'] if implicit else server.starttls.call_args.kwargs['context']
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
    server.login.assert_called_once_with('iorp@rehanh.com','test-only')
    message=server.send_message.call_args.args[0]
    assert message['From']=='IORP <iorp@rehanh.com>' and message['Date'] and message['Message-ID']
    assert [p.get_content_type() for p in message.get_payload()]==['text/plain','text/html']
    assert all(p.get_content_charset()=='utf-8' for p in message.get_payload())


@pytest.mark.parametrize('locale,direction', [('ar','rtl'),('en','ltr')])
def test_template_localization_escaping_and_copyable_link(locale,direction):
    url='https://app.example.test/reset-password?token=example&lang='+locale
    subject,html,text=build_tenant_reset_email(locale,url,'<script>','A & B')
    assert f'dir="{direction}"' in html and '<script>' not in html
    assert '&lt;script&gt;' in html and '&amp;' in html
    assert url in text and 'A & B' in subject and '&amp;' not in text
    assert html.count('href=')==2
    assert ('إعادة' if locale=='ar' else 'Password Reset') in build_platform_reset_email(locale,url,'Admin')[0]


@pytest.mark.parametrize('locale', ['ar', 'en'])
def test_an_activation_email_says_activate_and_24_hours(locale):
    """SEC-003: a new account's link is an activation, valid 24 hours, not a reset."""
    subject, html, text = build_tenant_reset_email(locale, 'https://app.example.test/reset-password?token=t&invite=1', 'New User', 'Org', 24 * 60, True)
    assert ('تفعيل' if locale == 'ar' else 'Activate') in subject and '24' in text and '1440' not in text


@pytest.mark.parametrize('url',['javascript:alert(1)','https://user:pass@example.test','https://app.example.test?next=evil','https://app.example.test/#fragment'])
def test_unsafe_reset_base_url_rejected(url):
    with pytest.raises(ValueError):Settings(_env_file=None,debug=False,frontend_url=url)


def test_conflicting_tls_modes_rejected():
    with pytest.raises(ValueError):Settings(_env_file=None,debug=False,smtp_ssl=True,smtp_tls=True)
