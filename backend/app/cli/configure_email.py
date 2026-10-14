"""Configure Hostinger SMTP locally; passwords are prompted, never command-line arguments."""
import argparse
from getpass import getpass
from pathlib import Path
import smtplib
import ssl
import sys
from dotenv import set_key
from app.core.config import Settings


def read_smtp_password():
    """smtplib.login encodes AUTH responses as ASCII. Never alter a secret silently."""
    for _ in range(3):
        password = getpass('Password for iorp@rehanh.com (hidden): ')
        if not password:
            raise ValueError('No password supplied. Configuration unchanged.')
        if password.isascii() and all(32 <= ord(char) <= 126 for char in password):
            return password
        print('Password input contains non-ASCII or control characters unsupported by Python SMTP login. '
              'Switch the keyboard to English and type it manually; copied text may contain invisible marks. '
              'If the mailbox password itself uses non-ASCII characters, change it in Hostinger first. '
              'No login was attempted and no characters were removed.', file=sys.stderr)
    raise ValueError('Password input could not be encoded. Configuration unchanged.')


def main():
    parser=argparse.ArgumentParser(description='Configure verified Hostinger email. Does not send a message.')
    parser.add_argument('--frontend-url',required=True,help='URL used by recipients, e.g. http://localhost:3000 for local testing')
    parser.add_argument('--platform-url',help='Defaults to the same frontend URL')
    parser.add_argument('--provider',choices=['hostinger','titan'],default='hostinger')
    args=parser.parse_args()
    path=Path(__file__).resolve().parents[2]/'.env'
    host='smtp.hostinger.com' if args.provider=='hostinger' else 'smtp.titan.email'
    settings=Settings(_env_file=path,frontend_url=args.frontend_url,
        platform_frontend_url=args.platform_url or args.frontend_url,smtp_ssl=True,smtp_tls=False)
    try:
        password=read_smtp_password()
    except ValueError as exc:
        parser.exit(1,str(exc)+'\n')
    try:
        with smtplib.SMTP_SSL(host,465,timeout=15,context=ssl.create_default_context()) as server:
            server.login('iorp@rehanh.com',password)
    except smtplib.SMTPAuthenticationError:
        parser.exit(1,'Hostinger rejected the mailbox login. Check the mailbox password (not the hPanel password) '
                    'and whether the mailbox uses Hostinger Email or Titan (--provider titan). Configuration unchanged.\n')
    except UnicodeEncodeError:
        parser.exit(1,'SMTP encountered a character encoding error after input validation. '
                    'Report this message without including your password. Configuration unchanged.\n')
    except Exception as exc:
        parser.exit(1,f'SMTP verification failed ({type(exc).__name__}). Configuration unchanged.\n')
    values={'EMAIL_MODE':'smtp','EMAIL_FROM':'iorp@rehanh.com','EMAIL_FROM_NAME':'IORP','SMTP_HOST':host,
        'SMTP_PORT':'465','SMTP_SSL':'true','SMTP_TLS':'false','SMTP_USER':'iorp@rehanh.com',
        'SMTP_PASSWORD':password,'FRONTEND_URL':settings.frontend_url,'PLATFORM_FRONTEND_URL':settings.platform_frontend_url}
    for key,value in values.items():
        set_key(str(path),key,value,quote_mode='always')
    print('SMTP authenticated; backend/.env configured. Restart the backend. No test email was sent.')


if __name__=='__main__':
    main()
