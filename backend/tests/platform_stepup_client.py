"""Opt-in browser-equivalent handshake for pre-MFA Platform business tests.

Uses the real login password and real step-up endpoint, never fabricates grants or
overrides server authorization. Security/replay tests use the raw client instead.
"""
import pytest


@pytest.fixture
def verified_platform_browser(client, monkeypatch):
    original = client.request
    credentials = {}

    def request(method, url, **kwargs):
        path = str(url)
        headers = dict(kwargs.get('headers') or {})
        token = headers.get('Authorization', '').removeprefix('Bearer ')
        if method.upper() not in {'GET', 'HEAD', 'OPTIONS'} and token in credentials and (
            path.startswith('/api/v1/platform/organizations') or path.startswith('/api/v1/platform/administrators')
        ) and 'X-Platform-Step-Up' not in headers:
            verification = original('POST', '/api/v1/platform/mfa/step-up', headers=headers, json={
                'password': credentials[token], 'method': method.upper(), 'path': path.removeprefix('/api/v1'),
                'body': kwargs.get('json'),
            })
            if verification.status_code == 200:
                headers['X-Platform-Step-Up'] = verification.json()['authorization']
                kwargs['headers'] = headers
            else:
                # Invalidated sessions must still be tested at the actual requested endpoint.
                assert verification.status_code == 401, verification.text
        response = original(method, url, **kwargs)
        if path == '/api/v1/platform/login' and response.status_code == 200:
            credentials[response.json()['access_token']] = kwargs['json']['password']
        return response
    monkeypatch.setattr(client, 'request', request)
    return client
