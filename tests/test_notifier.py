from unittest.mock import patch, MagicMock
from notifier import build_html, send_report


def test_build_html_contains_domain():
    domains = [{'domain': 'abc.com', 'found_at': '2026-01-01 06:00:00'}]
    html = build_html(domains)
    assert 'abc.com' in html


def test_build_html_shows_count():
    domains = [
        {'domain': 'abc.com', 'found_at': '2026-01-01'},
        {'domain': 'abcd.com', 'found_at': '2026-01-01'},
    ]
    html = build_html(domains)
    assert '2 found' in html


def test_build_html_shows_length():
    domains = [{'domain': 'abc.com', 'found_at': '2026-01-01'}]
    html = build_html(domains)
    assert '>3<' in html  # length column value


def test_send_report_skips_on_empty():
    with patch('notifier.smtplib.SMTP_SSL') as mock_smtp:
        send_report([])
        mock_smtp.assert_not_called()


def test_send_report_calls_smtp_on_domains():
    domains = [{'domain': 'abc.com', 'found_at': '2026-01-01'}]
    mock_server = MagicMock()
    with patch('notifier.smtplib.SMTP_SSL') as mock_smtp:
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        send_report(domains)
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()


def test_send_report_subject_contains_count():
    domains = [{'domain': 'abc.com', 'found_at': '2026-01-01'}]
    captured = {}
    mock_server = MagicMock()
    def fake_sendmail(from_addr, to_addr, msg_str):
        captured['msg'] = msg_str
    mock_server.sendmail.side_effect = fake_sendmail
    with patch('notifier.smtplib.SMTP_SSL') as mock_smtp:
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
        send_report(domains)
    assert '1' in captured['msg']
