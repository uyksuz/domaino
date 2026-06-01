import logging
import logging.handlers
import time
from datetime import datetime, timezone, date
from pathlib import Path

from config import DAILY_SLICE_5CHAR, DAILY_SLICE_6CHAR, DNS_CONCURRENCY
from db import init_db, get_progress, save_progress, get_total_count, get_today_domains
from generator import get_slice, total_count, LENGTHS
from checker import check_batch
from notifier import send_report, send_crash_email
from watcher import run_watcher
import firebase_writer

_LOG_DIR = Path(__file__).parent / 'logs'
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.handlers.TimedRotatingFileHandler(
            _LOG_DIR / 'domaino.log', when='D', backupCount=14
        ),
    ],
    format='%(asctime)s %(levelname)s %(message)s',
)
logger = logging.getLogger(__name__)

_DEFAULT_SLICES = {3: None, 4: None, 5: DAILY_SLICE_5CHAR, 6: DAILY_SLICE_6CHAR}
_CHUNK = 5_000  # Progress kaydedilme ve stop kontrol sıklığı


def _scan_length(length, ctrl):
    scan_key = f'scan_{length}'
    if not ctrl.get(scan_key, True):
        logger.info(f'Length {length}: disabled in settings, skipping')
        return []

    total = total_count(length)
    default_slice = _DEFAULT_SLICES.get(length)

    # Kontrol panelinden override
    if length == 5:
        slice_size = ctrl.get('slice', default_slice or total)
    elif length == 6:
        slice_size = ctrl.get('slice_6', default_slice or total)
    else:
        slice_size = default_slice or total

    start_offset = get_progress(length)
    if start_offset >= total:
        if slice_size is None or slice_size >= total:
            logger.info(f'Length {length}: already fully scanned, skipping this cycle')
            return []
        start_offset = 0
        logger.info(f'Length {length}: full cycle complete — restarting from 0')

    if ctrl['command'] == 'stop':
        logger.info(f'Length {length}: stop command received, skipping')
        return []

    end_offset = min(start_offset + (slice_size or total), total)
    scan_started_at = datetime.now(timezone.utc).isoformat()
    all_available = []

    # Stop checker: Firebase'i en fazla 30 saniyede bir sorgular
    _stop_ts = [0.0]
    def _should_stop():
        now = time.monotonic()
        if now - _stop_ts[0] < 30.0:
            return False
        _stop_ts[0] = now
        return firebase_writer.get_control_settings().get('command') == 'stop'

    chunk_start = start_offset
    while chunk_start < end_offset:
        # Chunk başında stop kontrolü + ayarları tazele
        fresh_ctrl = firebase_writer.get_control_settings()
        if fresh_ctrl['command'] == 'stop':
            logger.info(f'Length {length}: stop command at offset {chunk_start}, halting')
            break

        chunk_end = min(chunk_start + _CHUNK, end_offset)
        domains = get_slice(length, chunk_start, chunk_end - chunk_start)
        logger.info(f'Length {length}: scanning {len(domains)} domains from offset {chunk_start}')

        firebase_writer.set_scan_status(
            scanning=True, length=length, offset=chunk_start, total=total,
            started_at=scan_started_at,
        )

        def _on_progress(processed, _total, _base=chunk_start):
            firebase_writer.set_scan_status(
                scanning=True, length=length,
                offset=_base + processed, total=total,
                started_at=scan_started_at,
            )

        found = check_batch(
            domains,
            fresh_ctrl['concurrency'],
            on_progress=_on_progress,
            whois_delay=fresh_ctrl.get('whois_delay', 1.5),
            expiry_threshold=fresh_ctrl.get('expiry_threshold', 90),
            min_score=fresh_ctrl.get('min_score', 0),
            should_stop=_should_stop,
        )
        all_available.extend(found)

        chunk_start = chunk_end
        save_progress(length, chunk_start)
        firebase_writer.set_scan_status(
            scanning=False, length=length, offset=chunk_start, total=total,
        )
        logger.info(f'Length {length}: chunk done at {chunk_start} — {len(found)} available')

    logger.info(f'Length {length}: done — {len(all_available)} available found')
    return all_available


def main():
    logger.info('DOMAINO scan started')
    init_db()
    ctrl = firebase_writer.get_control_settings()

    today_found = []
    for length in LENGTHS:
        try:
            found = _scan_length(length, ctrl)
            today_found.extend(found)
        except Exception as e:
            logger.error(f'Length {length} scan failed: {e}', exc_info=True)

    firebase_writer.update_stats(
        total_found=get_total_count(),
        today_found=len(today_found),
    )

    today_str = date.today().isoformat()
    try:
        send_report(get_today_domains(today_str))
    except Exception as e:
        logger.error(f'Email report failed: {e}')

    logger.info(
        f'DOMAINO scan complete — today: {len(today_found)}, '
        f'total in DB: {len(all_available)}'
    )
    run_watcher()


if __name__ == '__main__':
    import os, sys
    LOCK = Path(__file__).parent / '.scanner.lock'
    if LOCK.exists():
        pid = LOCK.read_text().strip()
        try:
            os.kill(int(pid), 0)
            logger.warning(f'Scanner already running (PID {pid}), exiting.')
            sys.exit(0)
        except (ProcessLookupError, ValueError):
            pass  # Eski PID ölmüş, lock'u geçersiz say
    LOCK.write_text(str(os.getpid()))

    consecutive_crashes = 0

    while True:
        try:
            ctrl = firebase_writer.get_control_settings()
        except Exception:
            ctrl = {}

        if ctrl.get('command') == 'stop':
            logger.info('Stop command active, waiting...')
            time.sleep(30)
            consecutive_crashes = 0
            continue

        try:
            main()
            consecutive_crashes = 0
        except Exception as e:
            consecutive_crashes += 1
            logger.error(f'Scanner crashed (#{consecutive_crashes}): {e}', exc_info=True)
            try:
                send_crash_email(f'Crash #{consecutive_crashes}\n\n{e}')
            except Exception:
                pass
            # Ust uste 3 crash: 5 dakika bekle
            wait = 300 if consecutive_crashes >= 3 else 60
            logger.info(f'Restarting in {wait}s...')
            time.sleep(wait)
            continue

        loop_delay = ctrl.get('loop_delay', 60)
        logger.info(f'Cycle complete — next in {loop_delay}s')
        time.sleep(loop_delay)

    LOCK.unlink(missing_ok=True)
