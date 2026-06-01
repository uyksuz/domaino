import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / '.env')


def _require(name):
    val = os.getenv(name)
    if not val:
        raise ValueError(f"Required env var {name!r} is not set")
    return val


def _int_env(name, default):
    raw = os.getenv(name, str(default))
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Env var {name!r} must be an integer, got {raw!r}")


SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = _int_env('SMTP_PORT', 465)
SMTP_USER = _require('SMTP_USER')
SMTP_PASS = _require('SMTP_PASS')
NOTIFY_EMAIL = _require('NOTIFY_EMAIL')
DAILY_SLICE_5CHAR = _int_env('DAILY_SLICE_5CHAR', 50000)
DAILY_SLICE_6CHAR = _int_env('DAILY_SLICE_6CHAR', 50000)
DNS_CONCURRENCY = _int_env('DNS_CONCURRENCY', 100)
