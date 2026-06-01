import asyncio
import time
import logging
import aiodns
import whois
from whois.parser import PywhoisError
import firebase_writer
from scoring import calc_score

logger = logging.getLogger(__name__)


async def dns_filter(domains, concurrency=100, on_progress=None):
    resolver = aiodns.DNSResolver()
    semaphore = asyncio.Semaphore(concurrency)
    total = len(domains)
    state = {"processed": 0, "last_current": 0.0, "last_progress": 0.0}

    loop = asyncio.get_event_loop()

    async def _check_one(domain):
        async with semaphore:
            state["processed"] += 1
            try:
                now = time.monotonic()

                # update_current async thread'de calistir — event loop'u bloke etme
                if now - state["last_current"] >= 1.0:
                    await loop.run_in_executor(None, firebase_writer.update_current, domain)
                    state["last_current"] = now

                # Progress callback her 2 saniyede bir
                if on_progress and now - state["last_progress"] >= 2.0:
                    on_progress(state["processed"], total)
                    state["last_progress"] = now

                await resolver.query(domain, 'A')
                return None
            except aiodns.error.DNSError as e:
                if e.args[0] == aiodns.error.ARES_ENOTFOUND:
                    return domain
                return None
            except Exception as e:
                logger.warning(f'DNS unexpected error for {domain}: {e}')
                return None

    tasks = [_check_one(d) for d in domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, str)]


def whois_verify(domain, retries=3, delay=1.5):
    """(is_available, expiry_or_None) tuple döner."""
    for attempt in range(retries):
        try:
            w = whois.whois(domain)
            registered = bool(
                w.domain_name or w.registrar or w.creation_date or w.expiration_date
            )
            if not registered:
                return True, None

            # Kayitliysa expiry tarihini cek
            expiry = w.expiration_date
            if isinstance(expiry, list):
                expiry = expiry[0]
            return False, expiry
        except PywhoisError as e:
            if 'no match' in str(e).lower():
                return True, None
            if attempt < retries - 1:
                logger.warning(f'WHOIS retry {attempt + 1} for {domain}: {e}')
                time.sleep(delay * (2 ** attempt))
            else:
                logger.error(f'WHOIS failed for {domain} after {retries} attempts: {e}')
                return False, None
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f'WHOIS retry {attempt + 1} for {domain}: {e}')
                time.sleep(delay * (2 ** attempt))
            else:
                logger.error(f'WHOIS failed for {domain} after {retries} attempts: {e}')
                return False, None


def check_batch(domains, dns_concurrency=100, on_progress=None, whois_delay=1.5,
                expiry_threshold=90, min_score=0, should_stop=None):
    from datetime import datetime, timezone

    candidates = asyncio.run(dns_filter(domains, dns_concurrency, on_progress))
    logger.info(f'DNS candidates: {len(candidates)} / {len(domains)}')

    if min_score > 0:
        before = len(candidates)
        candidates = [d for d in candidates if calc_score(d) >= min_score]
        skipped = before - len(candidates)
        logger.info(f'Quality filter (min_score={min_score}): {len(candidates)} pass, {skipped} skipped')

    available = []
    for i, domain in enumerate(candidates):
        if should_stop and i % 50 == 0 and should_stop():
            logger.info('Stop command received — halting WHOIS phase')
            break
        firebase_writer.update_current(domain)
        is_available, expiry = whois_verify(domain)
        if is_available:
            available.append(domain)
            logger.info(f'AVAILABLE: {domain}')
            firebase_writer.add_available(domain, length=len(domain) - 4)
        elif expiry and hasattr(expiry, 'replace'):
            try:
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                days_left = (expiry - datetime.now(timezone.utc)).days
                if 0 < days_left <= expiry_threshold:
                    firebase_writer.add_watch(domain, expiry.isoformat(), source='scan')
                    logger.info(f'WATCH ADDED ({days_left}d): {domain}')
            except Exception as e:
                logger.warning(f'Watch add failed for {domain}: {e}')
        time.sleep(whois_delay)
    return available
