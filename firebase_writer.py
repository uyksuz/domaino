import logging
import os
import threading
import requests
from datetime import datetime, date

import firebase_admin
from firebase_admin import credentials, db

from db import domain_exists, save_available
from godaddy import get_appraisal

logger = logging.getLogger(__name__)
_app = None


def _init():
    global _app
    if _app is not None:
        return
    try:
        _app = firebase_admin.get_app()
    except ValueError:
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH', '')
        db_url = os.environ.get('FIREBASE_DB_URL', '')
        if not cred_path or not db_url:
            raise ValueError('FIREBASE_CREDENTIALS_PATH and FIREBASE_DB_URL must be set')
        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred, {'databaseURL': db_url})


def _domain_to_key(domain: str) -> str:
    """Firebase key olarak kullanilabilecek deterministik anahtar uretir.
    Ayni domain her zaman ayni key'i uretir — bu Firebase duplikasyonunu onler."""
    return domain.replace('.', '-')


def set_scan_status(scanning: bool, length: int, offset: int, total: int, started_at: str = None):
    """started_at verilmezse ve scanning=True ise simdiki zamani kullanir.
    Progress callback'lerinde orijinal started_at gecilerek ETA bozulmasi onlenir."""
    try:
        _init()
        if started_at is None and scanning:
            started_at = datetime.utcnow().isoformat() + 'Z'
        db.reference('/scan/status').set({
            'scanning': scanning,
            'length': length,
            'offset': offset,
            'total': total,
            'started_at': started_at,
        })
    except Exception as e:
        logger.warning(f'Firebase set_scan_status failed: {e}')


def update_current(domain: str):
    try:
        _init()
        db.reference('/scan/current').set(domain)
    except Exception as e:
        logger.warning(f'Firebase update_current failed: {e}')


def _fetch_and_update_appraisal(safe_key: str, domain: str):
    """GoDaddy appraisal verisini background thread'de çekip Firebase'i günceller."""
    try:
        appraisal = get_appraisal(domain)
        if not appraisal:
            return
        _init()
        db.reference(f'/available/{safe_key}').update({
            'goValue':          appraisal.get('goValue'),
            'listPrice':        appraisal.get('listPrice'),
            'minPrice':         appraisal.get('minPrice'),
            'maxPrice':         appraisal.get('maxPrice'),
            'salesProbability': appraisal.get('salesProbability'),
        })
    except Exception as e:
        logger.warning(f'Appraisal update failed for {domain}: {e}')


def add_available(domain: str, length: int):
    """Domaine ozel deterministik key kullanarak Firebase'e ekler.
    Duplicate kontrolu local DB uzerinden yapilir."""
    try:
        _init()
        # Daha once bulunmussa Firebase'e tekrar yazma, bildirim de gonderme
        if domain_exists(domain):
            logger.debug(f'Duplicate skipped: {domain}')
            return

        safe_key = _domain_to_key(domain)
        entry = {
            'domain': domain,
            'found_at': datetime.utcnow().isoformat() + 'Z',
            'length': length,
            'favorited': False,
            'note': '',
        }
        db.reference(f'/available/{safe_key}').set(entry)
        # Local DB'ye de kaydet (sonraki calismalarda duplicate kontrolu icin)
        save_available(domain)
        send_push_notification(domain, safe_key)
        # GoDaddy appraisal'ı WHOIS döngüsünü bloke etmemek için arka planda çalıştır
        threading.Thread(
            target=_fetch_and_update_appraisal,
            args=(safe_key, domain),
            daemon=True,
        ).start()
    except Exception as e:
        logger.warning(f'Firebase add_available failed: {e}')


def update_stats(total_found: int, today_found: int):
    try:
        _init()
        ref = db.reference('/stats')
        stats = ref.get() or {}
        history = stats.get('history', [])
        today_str = date.today().isoformat()
        found = next((e for e in history if e['date'] == today_str), None)
        if found:
            found['count'] = today_found
        else:
            history.append({'date': today_str, 'count': today_found})
        history = sorted(history, key=lambda x: x['date'])[-30:]
        ref.set({
            'total_found': total_found,
            'today_found': today_found,
            'last_run': datetime.utcnow().isoformat() + 'Z',
            'history': history,
        })
    except Exception as e:
        logger.warning(f'Firebase update_stats failed: {e}')


def send_push_notification(domain: str, firebase_key: str):
    try:
        _init()
        token = db.reference('/push_token').get()
        if not token:
            return
        requests.post(
            'https://exp.host/--/api/v2/push/send',
            json={
                'to': token,
                'title': '🟢 Müsait Domain!',
                'body': f'{domain} müsait bulundu',
                'data': {'domain': domain, 'id': firebase_key},
                'sound': 'default',
            },
            headers={'Content-Type': 'application/json'},
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        logger.warning(f'Push notification failed: {e}')


def add_watch(domain: str, expires_at: str, source: str = 'scan'):
    """Takip listesine domain ekler. Daha once eklenmisse atlar."""
    try:
        _init()
        key = _domain_to_key(domain)
        ref = db.reference(f'/watch/{key}')
        if ref.get() is not None:
            return
        from datetime import datetime, timezone
        expiry_dt = datetime.fromisoformat(expires_at)
        if expiry_dt.tzinfo is None:
            expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
        days_left = (expiry_dt - datetime.now(timezone.utc)).days
        ref.set({
            'domain': domain,
            'expires_at': expires_at,
            'days_left': days_left,
            'added_at': datetime.utcnow().isoformat() + 'Z',
            'source': source,
            'notified_7': False,
            'notified_1': False,
        })
    except Exception as e:
        logger.warning(f'add_watch failed for {domain}: {e}')


def get_control_settings() -> dict:
    try:
        _init()
        ctrl = db.reference('/control').get() or {}
        return {
            'command':           ctrl.get('command', 'run'),
            'concurrency':       int(ctrl.get('concurrency', 100)),
            'slice':             int(ctrl.get('slice', 50000)),
            'slice_6':           int(ctrl.get('slice_6', 50000)),
            'scan_3':            bool(ctrl.get('scan_3', True)),
            'scan_4':            bool(ctrl.get('scan_4', True)),
            'scan_5':            bool(ctrl.get('scan_5', True)),
            'scan_6':            bool(ctrl.get('scan_6', False)),
            'expiry_threshold':  int(ctrl.get('expiry_threshold', 90)),
            'whois_delay':       float(ctrl.get('whois_delay', 1.5)),
            'loop_delay':        int(ctrl.get('loop_delay', 60)),
            'min_score':         int(ctrl.get('min_score', 0)),
        }
    except Exception as e:
        logger.warning(f'Firebase get_control_settings failed: {e}')
        return {
            'command': 'run', 'concurrency': 100,
            'slice': 50000, 'slice_6': 50000,
            'scan_3': True, 'scan_4': True, 'scan_5': True, 'scan_6': False,
            'expiry_threshold': 90, 'whois_delay': 1.5, 'loop_delay': 60,
            'min_score': 0,
        }
