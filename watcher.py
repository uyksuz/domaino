"""
Watcher: takip listesindeki domainlerin expiry tarihlerini kontrol eder,
7 gün ve 1 gun kaldığında push bildirimi gönderir.
"""
import logging
from datetime import datetime, timezone
import whois
from whois.parser import PywhoisError
import firebase_writer

logger = logging.getLogger(__name__)


def _fetch_expiry(domain: str):
    """WHOIS'ten expiry tarihini çeker. Bulamazsa None döner."""
    try:
        w = whois.whois(domain)
        expiry = w.expiration_date
        if isinstance(expiry, list):
            expiry = expiry[0]
        if expiry and hasattr(expiry, 'isoformat'):
            # timezone-naive ise UTC kabul et
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return expiry
    except PywhoisError:
        pass
    except Exception as e:
        logger.warning(f'WHOIS expiry fetch failed for {domain}: {e}')
    return None


def run_watcher():
    """Her scan döngüsü sonunda çalışır."""
    try:
        firebase_writer._init()
        from firebase_admin import db
        watches = db.reference('/watch').get() or {}
        now = datetime.now(timezone.utc)

        for key, data in watches.items():
            if not data:
                continue
            domain = data.get('domain', '')

            # Expiry tarihi yoksa WHOIS'ten çekmeyi dene
            expires_at = data.get('expires_at')
            if not expires_at:
                expiry = _fetch_expiry(domain)
                if expiry:
                    expires_at = expiry.isoformat()
                    db.reference(f'/watch/{key}').update({'expires_at': expires_at})
                else:
                    continue  # Hâlâ yok, sonraki döngüde tekrar dene

            # Kalan gün hesapla
            expiry_dt = datetime.fromisoformat(expires_at)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            days_left = (expiry_dt - now).days
            db.reference(f'/watch/{key}').update({'days_left': days_left})

            # Süresi 5 günden fazla geçmişse listeden sil
            if days_left < -5:
                db.reference(f'/watch/{key}').delete()
                logger.info(f'Watch removed (expired): {domain}')
                continue

            token = db.reference('/push_token').get()
            if not token:
                continue

            import requests

            # 7 gün bildirimi
            if days_left <= 7 and not data.get('notified_7'):
                try:
                    requests.post(
                        'https://exp.host/--/api/v2/push/send',
                        json={
                            'to': token,
                            'title': '⏰ Domain Sona Eriyor!',
                            'body': f'{domain} — {days_left} gün kaldı. Almak için hazır ol!',
                            'data': {'domain': domain, 'type': 'expiry_7'},
                            'sound': 'default',
                        },
                        timeout=10,
                    )
                    db.reference(f'/watch/{key}').update({'notified_7': True})
                    logger.info(f'Expiry 7-day notification sent: {domain}')
                except Exception as e:
                    logger.warning(f'Notification failed for {domain}: {e}')

            # 1 gün bildirimi
            if days_left <= 1 and not data.get('notified_1'):
                try:
                    requests.post(
                        'https://exp.host/--/api/v2/push/send',
                        json={
                            'to': token,
                            'title': '🚨 YARIN sona eriyor!',
                            'body': f'{domain} yarın boşa düşüyor. Alarm kur!',
                            'data': {'domain': domain, 'type': 'expiry_1'},
                            'sound': 'default',
                            'priority': 'high',
                        },
                        timeout=10,
                    )
                    db.reference(f'/watch/{key}').update({'notified_1': True})
                    logger.info(f'Expiry 1-day notification sent: {domain}')
                except Exception as e:
                    logger.warning(f'Notification failed for {domain}: {e}')

    except Exception as e:
        logger.error(f'Watcher failed: {e}', exc_info=True)
