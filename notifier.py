import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, NOTIFY_EMAIL

logger = logging.getLogger(__name__)


def build_html(domains):
    rows = ''.join(
        f'<tr><td>{d["domain"]}</td>'
        f'<td>{len(d["domain"]) - 4}</td>'
        f'<td>{d["found_at"]}</td></tr>'
        for d in domains
    )
    return (
        '<html><body>'
        f'<h2>Available .com Domains — {len(domains)} found</h2>'
        '<table border="1" cellpadding="6" style="border-collapse:collapse">'
        '<tr><th>Domain</th><th>Length</th><th>Found At</th></tr>'
        f'{rows}'
        '</table></body></html>'
    )


def send_crash_email(error: str):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = '[DOMAINO] Scanner Carpti!'
        msg['From'] = SMTP_USER
        msg['To'] = NOTIFY_EMAIL
        body = f'<html><body><h2>Scanner hata verdi ve yeniden baslatildi.</h2><pre>{error}</pre></body></html>'
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())
        logger.info('Crash email sent')
    except Exception as e:
        logger.warning(f'Crash email failed: {e}')


def send_report(domains):
    if not domains:
        logger.info('No available domains — skipping email')
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[DOMAINO] {len(domains)} Available .com Domains'
    msg['From'] = SMTP_USER
    msg['To'] = NOTIFY_EMAIL
    msg.attach(MIMEText(build_html(domains), 'html'))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, NOTIFY_EMAIL, msg.as_string())

    logger.info(f'Email sent: {len(domains)} domains → {NOTIFY_EMAIL}')
