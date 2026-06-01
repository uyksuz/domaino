# Domaino — Domain Scanner

A Python daemon that scans all possible 3–6 character `.com` domains, checks their availability via DNS/WHOIS, scores them, and writes results to Firebase Realtime Database.

## Features

- Generates every combination of 3–6 character `.com` domains
- Async DNS resolution with configurable concurrency
- WHOIS expiry checks with threshold filtering
- Domain scoring engine
- Firebase Realtime Database integration (live status, results, control)
- Email reports via SMTP (Gmail)
- Start/stop control from Firebase without restarting the process
- SQLite-backed progress — resumes from where it left off after a crash
- Process lock file to prevent duplicate runs

## Requirements

- Python 3.10+
- A Firebase project with Realtime Database enabled
- A `firebase-credentials.json` service account key (not committed)

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password
NOTIFY_EMAIL=you@gmail.com
DAILY_SLICE_5CHAR=50000
DAILY_SLICE_6CHAR=50000
DNS_CONCURRENCY=100
```

Place your Firebase service account key at `firebase-credentials.json`.

## Run

```bash
python main.py
```

The scanner runs in a continuous loop. Send `{"command": "stop"}` to the Firebase `control` node to pause it remotely.

## Project Structure

```
main.py            # Entry point, scan loop
checker.py         # Async DNS + WHOIS availability checks
generator.py       # Domain combination generator
scoring.py         # Domain quality scorer
firebase_writer.py # Firebase read/write helpers
db.py              # SQLite progress tracking
notifier.py        # Email report sender
watcher.py         # Firebase listener for real-time control
config.py          # Env var loading
```

## Tests

```bash
pytest
```
