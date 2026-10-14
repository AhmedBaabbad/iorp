import pytest
from app.cli import configure_email


def test_ascii_password_preserved_including_spaces(monkeypatch):
    value=' Example-Only_482! '
    monkeypatch.setattr(configure_email,'getpass',lambda _:value)
    assert configure_email.read_smtp_password()==value


@pytest.mark.parametrize('mark',['\u200f','\u200e','\u00a0','\n','ع'])
def test_hidden_or_non_ascii_input_reprompted_without_disclosing_secret(monkeypatch,capsys,mark):
    bad='Synthetic-only-482!'+mark
    entries=iter([bad,'Retyped-only_583!'])
    monkeypatch.setattr(configure_email,'getpass',lambda _:next(entries))
    assert configure_email.read_smtp_password()=='Retyped-only_583!'
    output=capsys.readouterr().err
    assert 'No login was attempted' in output and bad not in output and 'Synthetic' not in output


def test_repeated_invalid_input_is_bounded(monkeypatch):
    calls=[]
    monkeypatch.setattr(configure_email,'getpass',lambda _:(calls.append(1) or 'example\u200f'))
    with pytest.raises(ValueError,match='Configuration unchanged'):
        configure_email.read_smtp_password()
    assert len(calls)==3


def test_empty_input_does_not_retry(monkeypatch):
    monkeypatch.setattr(configure_email,'getpass',lambda _:'')
    with pytest.raises(ValueError,match='No password supplied'):
        configure_email.read_smtp_password()
