# Domaino Mobile App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python domain scanner'a Firebase entegrasyonu ekle ve taramayı canlı izleyen, müsait domainleri listeleyen, favori/not/bildirim destekli bir Expo mobil uygulaması yaz.

**Architecture:** Python scanner firebase-admin ile Realtime DB'ye yazar; Expo app Firebase onValue listener'larıyla anlık güncelleme alır; push notification Expo Push API üzerinden çalışır, auth gerekmez.

**Tech Stack:** Python `firebase-admin`, Expo SDK 53, Firebase JS SDK v10, Expo Router, NativeWind v4, Zustand, FlashList, Expo Notifications, React Native Reanimated v3

---

## File Map

### Phase A — Python Backend (mevcut proje: `/home/domaino/domaino/`)

| Dosya | İşlem | Sorumluluk |
|-------|-------|-----------|
| `firebase_writer.py` | CREATE | Firebase yazma fonksiyonları |
| `checker.py` | MODIFY | Her DNS kontrolünde `update_current`, bulunca `add_available` çağır |
| `main.py` | MODIFY | Tarama başı/sonu `set_scan_status`, bitiş `update_stats`, kontrol loop |
| `requirements.txt` | MODIFY | `firebase-admin`, `requests` ekle |
| `.env` / `.env.example` | MODIFY | `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_DB_URL` ekle |
| `tests/test_firebase_writer.py` | CREATE | Unit testler (mock ile) |

### Phase B — Expo App (yeni proje: `/home/domaino/domaino-app/`)

| Dosya | İşlem | Sorumluluk |
|-------|-------|-----------|
| `types.ts` | CREATE | Paylaşılan TypeScript tipleri |
| `lib/firebase.ts` | CREATE | Firebase init + db ref |
| `lib/scoring.ts` | CREATE | Domain skor hesabı (pure functions) |
| `lib/useScanner.ts` | CREATE | Scan status + current domain hook |
| `lib/useAvailable.ts` | CREATE | Available domains hook + write ops |
| `lib/useStats.ts` | CREATE | Stats hook |
| `lib/notifications.ts` | CREATE | Push token kayıt |
| `components/ScoreBar.tsx` | CREATE | Skor göstergesi (0-100) |
| `components/ScanProgress.tsx` | CREATE | Progress bar + canlı ticker |
| `components/FilterBar.tsx` | CREATE | Uzunluk toggle + pattern arama |
| `components/DomainCard.tsx` | CREATE | Swipeable domain kartı |
| `app/_layout.tsx` | CREATE | Root layout, Firebase + notification init |
| `app/(tabs)/_layout.tsx` | CREATE | Tab bar yapılandırması |
| `app/(tabs)/index.tsx` | CREATE | Live Feed ekranı |
| `app/(tabs)/available.tsx` | CREATE | Available Domains ekranı |
| `app/(tabs)/favorites.tsx` | CREATE | Favorites ekranı |
| `app/(tabs)/stats.tsx` | CREATE | Stats ekranı |
| `app/(tabs)/control.tsx` | CREATE | Control Panel ekranı |
| `app/domain/[id].tsx` | CREATE | Domain detay sheet |
| `__tests__/scoring.test.ts` | CREATE | Skor unit testleri |

---

## Phase A — Python Backend

### Task 1: Firebase Writer Modülü

**Files:**
- Create: `firebase_writer.py`
- Create: `tests/test_firebase_writer.py`
- Modify: `requirements.txt`
- Modify: `.env.example`

- [ ] **Step 1: requirements.txt güncelle**

```
aiodns
whois
python-dotenv
firebase-admin
requests
```

- [ ] **Step 2: .env.example güncelle**

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_gmail@gmail.com
SMTP_PASS=your_app_password_here
NOTIFY_EMAIL=your_notify@email.com
DAILY_SLICE_5CHAR=50000
DNS_CONCURRENCY=100
FIREBASE_CREDENTIALS_PATH=/home/domaino/domaino/firebase-credentials.json
FIREBASE_DB_URL=https://your-project-default-rtdb.firebaseio.com
```

- [ ] **Step 3: Failing test yaz**

```python
# tests/test_firebase_writer.py
from unittest.mock import patch, MagicMock, call
import pytest

@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch):
    monkeypatch.setenv('FIREBASE_CREDENTIALS_PATH', '/fake/creds.json')
    monkeypatch.setenv('FIREBASE_DB_URL', 'https://fake.firebaseio.com')
    with patch('firebase_admin.credentials.Certificate') as mock_cert, \
         patch('firebase_admin.initialize_app') as mock_init, \
         patch('firebase_admin.db') as mock_db, \
         patch('firebase_admin.get_app', side_effect=ValueError):
        mock_ref = MagicMock()
        mock_db.reference.return_value = mock_ref
        yield mock_db, mock_ref

def test_set_scan_status_writes_correct_fields(mock_firebase):
    mock_db, mock_ref = mock_firebase
    import firebase_writer
    firebase_writer._app = MagicMock()  # skip init

    firebase_writer.set_scan_status(scanning=True, length=5, offset=1000, total=11881376)

    mock_db.reference.assert_called_with('/scan/status')
    args = mock_ref.set.call_args[0][0]
    assert args['scanning'] is True
    assert args['length'] == 5
    assert args['offset'] == 1000
    assert args['total'] == 11881376

def test_update_current_sets_domain(mock_firebase):
    mock_db, mock_ref = mock_firebase
    import firebase_writer
    firebase_writer._app = MagicMock()

    firebase_writer.update_current('xkq.com')

    mock_db.reference.assert_called_with('/scan/current')
    mock_ref.set.assert_called_with('xkq.com')

def test_add_available_pushes_and_notifies(mock_firebase):
    mock_db, mock_ref = mock_firebase
    import firebase_writer
    firebase_writer._app = MagicMock()

    with patch.object(firebase_writer, 'send_push_notification') as mock_push:
        firebase_writer.add_available('xkq.com', length=3)

    mock_db.reference.assert_any_call('/available')
    pushed = mock_ref.push.call_args[0][0]
    assert pushed['domain'] == 'xkq.com'
    assert pushed['length'] == 3
    assert pushed['favorited'] is False
    mock_push.assert_called_once_with('xkq.com')

def test_firebase_errors_are_swallowed(mock_firebase):
    mock_db, mock_ref = mock_firebase
    mock_ref.set.side_effect = Exception('network error')
    import firebase_writer
    firebase_writer._app = MagicMock()

    # Should not raise
    firebase_writer.update_current('abc.com')
    firebase_writer.set_scan_status(False, 3, 0, 17576)
```

- [ ] **Step 4: Test'in fail ettiğini doğrula**

```bash
cd /home/domaino/domaino && source venv/bin/activate
pytest tests/test_firebase_writer.py -v
```
Beklenen: `ImportError: No module named 'firebase_writer'`

- [ ] **Step 5: firebase_writer.py yaz**

```python
# firebase_writer.py
import logging
import os
import requests
from datetime import datetime, date

import firebase_admin
from firebase_admin import credentials, db

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


def set_scan_status(scanning: bool, length: int, offset: int, total: int):
    try:
        _init()
        db.reference('/scan/status').set({
            'scanning': scanning,
            'length': length,
            'offset': offset,
            'total': total,
            'started_at': datetime.utcnow().isoformat() + 'Z' if scanning else None,
        })
    except Exception as e:
        logger.warning(f'Firebase set_scan_status failed: {e}')


def update_current(domain: str):
    try:
        _init()
        db.reference('/scan/current').set(domain)
    except Exception as e:
        logger.warning(f'Firebase update_current failed: {e}')


def add_available(domain: str, length: int):
    try:
        _init()
        db.reference('/available').push({
            'domain': domain,
            'found_at': datetime.utcnow().isoformat() + 'Z',
            'length': length,
            'favorited': False,
            'note': '',
        })
        send_push_notification(domain)
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


def send_push_notification(domain: str):
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
                'data': {'domain': domain},
                'sound': 'default',
            },
            headers={'Content-Type': 'application/json'},
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        logger.warning(f'Push notification failed: {e}')


def get_control_settings() -> dict:
    """Returns {'command': 'run'|'stop', 'slice': int, 'concurrency': int}"""
    try:
        _init()
        ctrl = db.reference('/control').get() or {}
        return {
            'command': ctrl.get('command', 'run'),
            'slice': int(ctrl.get('slice', 50000)),
            'concurrency': int(ctrl.get('concurrency', 100)),
        }
    except Exception as e:
        logger.warning(f'Firebase get_control_settings failed: {e}')
        return {'command': 'run', 'slice': 50000, 'concurrency': 100}
```

- [ ] **Step 6: Testleri çalıştır, geçtiğini doğrula**

```bash
pytest tests/test_firebase_writer.py -v
```
Beklenen: 5 PASSED

- [ ] **Step 7: pip install**

```bash
pip install firebase-admin requests
```

- [ ] **Step 8: Commit**

```bash
cd /home/domaino/domaino
git add firebase_writer.py tests/test_firebase_writer.py requirements.txt .env.example
git commit -m "feat: add firebase_writer module with push notifications"
```

---

### Task 2: checker.py ve main.py Entegrasyonu

**Files:**
- Modify: `checker.py`
- Modify: `main.py`

- [ ] **Step 1: checker.py — update_current ve add_available çağrılarını ekle**

`_check_one` fonksiyonuna Firebase çağrısı ekle. `check_batch` fonksiyonuna available domain bildirimi ekle.

Mevcut `checker.py`'deki `_check_one` ve `check_batch` fonksiyonlarını şunlarla değiştir:

```python
# checker.py — dosyanın başına ekle (diğer import'lardan sonra)
import firebase_writer


async def _check_one(resolver, semaphore, domain):
    async with semaphore:
        try:
            firebase_writer.update_current(domain)   # ← YENİ
            await resolver.query(domain, 'A')
            return None
        except aiodns.error.DNSError as e:
            if e.args[0] == aiodns.error.ARES_ENOTFOUND:
                return domain
            return None
        except Exception as e:
            logger.warning(f'DNS unexpected error for {domain}: {e}')
            return None


def check_batch(domains, dns_concurrency=100):
    candidates = asyncio.run(dns_filter(domains, dns_concurrency))
    logger.info(f'DNS candidates: {len(candidates)} / {len(domains)}')
    available = []
    for domain in candidates:
        if whois_verify(domain):
            available.append(domain)
            logger.info(f'AVAILABLE: {domain}')
            length = len(domain) - 4  # ".com" = 4 chars
            firebase_writer.add_available(domain, length)  # ← YENİ
        time.sleep(1.5)
    return available
```

- [ ] **Step 2: main.py — scan status ve stats güncellemelerini ekle**

`_scan_length` ve `main` fonksiyonlarını güncelle:

```python
# main.py — dosyanın başına ekle
import firebase_writer


def _scan_length(length):
    total = total_count(length)
    slice_size = _SLICE_SIZES[length] or total
    offset = get_progress(length) if _SLICE_SIZES[length] else 0

    if offset >= total:
        offset = 0
        logger.info(f'Length {length}: full cycle complete — restarting from 0')

    # Control settings from Firebase (override env defaults if set)
    ctrl = firebase_writer.get_control_settings()
    if ctrl['command'] == 'stop':
        logger.info(f'Length {length}: stop command received, skipping')
        return []
    if length == 5 and ctrl['slice'] != slice_size:
        slice_size = ctrl['slice']
        logger.info(f'Length {length}: slice overridden to {slice_size} by Firebase control')

    domains = get_slice(length, offset, slice_size)
    logger.info(f'Length {length}: scanning {len(domains)} domains from offset {offset}')

    firebase_writer.set_scan_status(
        scanning=True, length=length, offset=offset, total=total
    )

    available = check_batch(domains, ctrl['concurrency'])
    for domain in available:
        save_available(domain)

    save_progress(length, offset + len(domains))
    firebase_writer.set_scan_status(
        scanning=False, length=length, offset=offset + len(domains), total=total
    )
    logger.info(f'Length {length}: done — {len(available)} available found')
    return available


def main():
    logger.info('DOMAINO scan started')
    init_db()

    today_found = []
    for length in LENGTHS:
        try:
            found = _scan_length(length)
            today_found.extend(found)
        except Exception as e:
            logger.error(f'Length {length} scan failed: {e}', exc_info=True)

    all_available = get_all_available()
    firebase_writer.update_stats(
        total_found=len(all_available), today_found=len(today_found)
    )
    send_report(all_available)
    logger.info(
        f'DOMAINO scan complete — today: {len(today_found)}, '
        f'total in DB: {len(all_available)}'
    )
```

- [ ] **Step 3: Smoke test — Firebase credentials olmadan çalıştır, hata yutulduğunu doğrula**

```bash
cd /home/domaino/domaino && source venv/bin/activate
FIREBASE_CREDENTIALS_PATH="" FIREBASE_DB_URL="" python -c "
from checker import check_batch
# Firebase yazma hataları yutulmalı, exception çıkmamalı
result = check_batch(['nonexistent-domain-xyz123.com'], dns_concurrency=5)
print('OK, result:', result)
"
```
Beklenen: `OK, result: []` (exception yok)

- [ ] **Step 4: Commit**

```bash
git add checker.py main.py
git commit -m "feat: integrate firebase_writer into scanner pipeline"
```

---

### Task 3: Firebase Credentials Kurulumu (VPS)

**Files:**
- Firebase Console'dan credentials JSON indir
- `.env` güncelle

- [ ] **Step 1: Firebase Console'da Realtime Database oluştur**

1. https://console.firebase.google.com → proje aç (veya yeni oluştur)
2. Build → Realtime Database → Create database → Test mode
3. Project Settings → Service Accounts → Generate new private key → JSON indir
4. JSON dosyasını VPS'e kopyala:

```bash
# Local makinende (JSON'u indirdikten sonra):
scp firebase-credentials.json domaino@<VPS_IP>:/home/domaino/domaino/firebase-credentials.json
```

- [ ] **Step 2: .env'i güncelle**

```bash
# /home/domaino/domaino/.env dosyasına ekle:
echo 'FIREBASE_CREDENTIALS_PATH=/home/domaino/domaino/firebase-credentials.json' >> /home/domaino/domaino/.env
echo 'FIREBASE_DB_URL=https://YOUR-PROJECT-default-rtdb.firebaseio.com' >> /home/domaino/domaino/.env
```

- [ ] **Step 3: Firebase bağlantısını test et**

```bash
cd /home/domaino/domaino && source venv/bin/activate
python -c "
from dotenv import load_dotenv; load_dotenv('.env')
import firebase_writer
firebase_writer.set_scan_status(scanning=False, length=3, offset=0, total=17576)
print('Firebase OK')
"
```
Beklenen: `Firebase OK` (Console → Realtime DB'de `/scan/status` oluştu)

- [ ] **Step 4: .gitignore'a credentials ekle**

```bash
echo 'firebase-credentials.json' >> /home/domaino/domaino/.gitignore
git add .gitignore .env
git commit -m "chore: add firebase credentials to gitignore, update env"
```

---

## Phase B — Expo App

### Task 4: Expo Proje Scaffold

**Files:**
- Create: `/home/domaino/domaino-app/` (yeni proje)

- [ ] **Step 1: Expo projesi oluştur**

```bash
cd /home/domaino
npx create-expo-app domaino-app --template blank-typescript
cd domaino-app
```

- [ ] **Step 2: Bağımlılıkları yükle**

```bash
npx expo install expo-router expo-notifications expo-constants expo-device
npx expo install firebase
npx expo install react-native-reanimated react-native-gesture-handler
npm install nativewind tailwindcss
npm install zustand
npm install @shopify/flash-list
npm install react-native-svg
npm install victory-native
```

- [ ] **Step 3: NativeWind v4 kurulumu**

```bash
npx tailwindcss init
```

`tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{js,jsx,ts,tsx}', './components/**/*.{js,jsx,ts,tsx}'],
  presets: [require('nativewind/preset')],
  theme: { extend: {} },
  plugins: [],
};
```

`babel.config.js`:
```javascript
module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxImportSource: 'nativewind' }],
      'nativewind/babel',
    ],
  };
};
```

`metro.config.js`:
```javascript
const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');

const config = getDefaultConfig(__dirname);
module.exports = withNativeWind(config, { input: './global.css' });
```

`global.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 4: app.json güncelle (Expo Router için)**

```json
{
  "expo": {
    "name": "Domaino",
    "slug": "domaino",
    "version": "1.0.0",
    "scheme": "domaino",
    "web": { "bundler": "metro" },
    "plugins": [
      "expo-router",
      [
        "expo-notifications",
        {
          "icon": "./assets/icon.png",
          "color": "#10b981"
        }
      ]
    ],
    "android": { "adaptiveIcon": { "foregroundImage": "./assets/adaptive-icon.png" } },
    "ios": { "bundleIdentifier": "com.domaino.app" }
  }
}
```

- [ ] **Step 5: Klasör yapısını oluştur**

```bash
mkdir -p app/\(tabs\) app/domain lib components __tests__
```

- [ ] **Step 6: .env.local oluştur**

```
EXPO_PUBLIC_FIREBASE_API_KEY=xxx
EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN=xxx.firebaseapp.com
EXPO_PUBLIC_FIREBASE_DB_URL=https://xxx-default-rtdb.firebaseio.com
EXPO_PUBLIC_FIREBASE_PROJECT_ID=xxx
EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET=xxx.appspot.com
EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=xxx
EXPO_PUBLIC_FIREBASE_APP_ID=xxx
```

- [ ] **Step 7: Expo çalıştığını kontrol et**

```bash
npx expo start
```
Beklenen: QR kodu görünür, Metro bundler başlar.

---

### Task 5: Types ve Firebase Lib

**Files:**
- Create: `types.ts`
- Create: `lib/firebase.ts`

- [ ] **Step 1: types.ts**

```typescript
// types.ts
export interface AvailableDomain {
  id: string;
  domain: string;
  found_at: string;
  length: number;
  favorited: boolean;
  note: string;
}

export interface ScanStatus {
  scanning: boolean;
  length: number;
  offset: number;
  total: number;
  started_at: string | null;
}

export interface StatsDay {
  date: string;
  count: number;
}

export interface Stats {
  total_found: number;
  today_found: number;
  last_run: string;
  history: StatsDay[];
}

export interface ControlSettings {
  command: 'run' | 'stop';
  slice: number;
  concurrency: number;
}
```

- [ ] **Step 2: lib/firebase.ts**

```typescript
// lib/firebase.ts
import { initializeApp, getApps, getApp } from 'firebase/app';
import { getDatabase } from 'firebase/database';

const firebaseConfig = {
  apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
  databaseURL: process.env.EXPO_PUBLIC_FIREBASE_DB_URL,
  projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
};

const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const db = getDatabase(app);
```

- [ ] **Step 3: Commit**

```bash
git init && git add types.ts lib/firebase.ts
git commit -m "feat: add types and firebase config"
```

---

### Task 6: Domain Scoring

**Files:**
- Create: `lib/scoring.ts`
- Create: `__tests__/scoring.test.ts`

- [ ] **Step 1: Failing testleri yaz**

```typescript
// __tests__/scoring.test.ts
import { scoreDomain } from '../lib/scoring';

describe('scoreDomain', () => {
  it('3-char domain gets higher length score than 5-char', () => {
    const s3 = scoreDomain('abc.com');
    const s5 = scoreDomain('abcde.com');
    expect(s3.length).toBeGreaterThan(s5.length);
  });

  it('CVC pattern (bat.com) scores higher than consonant-heavy (xkq.com)', () => {
    const cvc = scoreDomain('bat.com');
    const hard = scoreDomain('xkq.com');
    expect(cvc.pronounce).toBeGreaterThan(hard.pronounce);
  });

  it('total is between 0 and 100', () => {
    ['abc.com', 'xkqbz.com', 'aaa.com', 'bat.com'].forEach(d => {
      const { total } = scoreDomain(d);
      expect(total).toBeGreaterThanOrEqual(0);
      expect(total).toBeLessThanOrEqual(100);
    });
  });

  it('CVCV pattern scores high on memory', () => {
    const { memory } = scoreDomain('bale.com');
    expect(memory).toBeGreaterThanOrEqual(70);
  });
});
```

- [ ] **Step 2: Test çalıştır, fail ettiğini doğrula**

```bash
npx jest __tests__/scoring.test.ts
```
Beklenen: `Cannot find module '../lib/scoring'`

- [ ] **Step 3: lib/scoring.ts yaz**

```typescript
// lib/scoring.ts
export interface DomainScore {
  total: number;
  length: number;
  pronounce: number;
  memory: number;
}

const VOWELS = new Set(['a', 'e', 'i', 'o', 'u']);

function lengthScore(name: string): number {
  if (name.length === 3) return 100;
  if (name.length === 4) return 75;
  return 50;
}

function pronounceScore(name: string): number {
  const chars = name.split('');
  const vowelRatio = chars.filter(c => VOWELS.has(c)).length / name.length;

  let maxConsecutiveConsonants = 0;
  let run = 0;
  for (const c of chars) {
    run = VOWELS.has(c) ? 0 : run + 1;
    maxConsecutiveConsonants = Math.max(maxConsecutiveConsonants, run);
  }

  const vowelScore = Math.min(100, vowelRatio * 250);
  const penalty = Math.max(0, (maxConsecutiveConsonants - 2) * 20);
  return Math.max(0, Math.round(vowelScore - penalty));
}

function memoryScore(name: string): number {
  const chars = name.split('');
  const hasRepeat = chars.some((c, i) => i > 0 && c === chars[i - 1]);

  const isCvc =
    name.length === 3 &&
    !VOWELS.has(name[0]) && VOWELS.has(name[1]) && !VOWELS.has(name[2]);
  const isCvcv =
    name.length === 4 &&
    !VOWELS.has(name[0]) && VOWELS.has(name[1]) &&
    !VOWELS.has(name[2]) && VOWELS.has(name[3]);

  let score = 70;
  if (isCvc || isCvcv) score = 100;
  if (hasRepeat) score -= 15;
  return Math.max(0, score);
}

export function scoreDomain(domain: string): DomainScore {
  const name = domain.replace(/\.com$/, '');
  const length = lengthScore(name);
  const pronounce = pronounceScore(name);
  const memory = memoryScore(name);
  const total = Math.round(length * 0.5 + pronounce * 0.35 + memory * 0.15);
  return { total, length, pronounce, memory };
}
```

- [ ] **Step 4: Testleri geçir**

```bash
npx jest __tests__/scoring.test.ts
```
Beklenen: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add lib/scoring.ts __tests__/scoring.test.ts
git commit -m "feat: add domain scoring algorithm"
```

---

### Task 7: Firebase Hooks

**Files:**
- Create: `lib/useScanner.ts`
- Create: `lib/useAvailable.ts`
- Create: `lib/useStats.ts`

- [ ] **Step 1: lib/useScanner.ts**

```typescript
// lib/useScanner.ts
import { useEffect, useState } from 'react';
import { ref, onValue } from 'firebase/database';
import { db } from './firebase';
import { ScanStatus } from '../types';

export interface ScannerState {
  status: ScanStatus | null;
  current: string;
  connected: boolean;
}

export function useScanner(): ScannerState {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [current, setCurrent] = useState('');
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const connRef = ref(db, '.info/connected');
    const statusRef = ref(db, '/scan/status');
    const currentRef = ref(db, '/scan/current');

    const unsubConn = onValue(connRef, snap => setConnected(snap.val() ?? false));
    const unsubStatus = onValue(statusRef, snap => setStatus(snap.val()));
    const unsubCurrent = onValue(currentRef, snap => setCurrent(snap.val() ?? ''));

    return () => { unsubConn(); unsubStatus(); unsubCurrent(); };
  }, []);

  return { status, current, connected };
}
```

- [ ] **Step 2: lib/useAvailable.ts**

```typescript
// lib/useAvailable.ts
import { useEffect, useState, useCallback } from 'react';
import { ref, onValue, update } from 'firebase/database';
import { db } from './firebase';
import { AvailableDomain } from '../types';

export function useAvailable() {
  const [domains, setDomains] = useState<AvailableDomain[]>([]);

  useEffect(() => {
    const availRef = ref(db, '/available');
    const unsub = onValue(availRef, snap => {
      const val = snap.val();
      if (!val) return setDomains([]);
      const list: AvailableDomain[] = Object.entries(val).map(([id, d]: any) => ({
        id,
        domain: d.domain,
        found_at: d.found_at,
        length: d.length,
        favorited: d.favorited ?? false,
        note: d.note ?? '',
      }));
      list.sort((a, b) => b.found_at.localeCompare(a.found_at));
      setDomains(list);
    });
    return unsub;
  }, []);

  const toggleFavorite = useCallback((id: string, favorited: boolean) => {
    update(ref(db, `/available/${id}`), { favorited });
  }, []);

  const setNote = useCallback((id: string, note: string) => {
    update(ref(db, `/available/${id}`), { note });
  }, []);

  return { domains, toggleFavorite, setNote };
}
```

- [ ] **Step 3: lib/useStats.ts**

```typescript
// lib/useStats.ts
import { useEffect, useState } from 'react';
import { ref, onValue } from 'firebase/database';
import { db } from './firebase';
import { Stats } from '../types';

export function useStats(): Stats | null {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    const unsub = onValue(ref(db, '/stats'), snap => {
      setStats(snap.val());
    });
    return unsub;
  }, []);

  return stats;
}
```

- [ ] **Step 4: Commit**

```bash
git add lib/useScanner.ts lib/useAvailable.ts lib/useStats.ts
git commit -m "feat: add firebase realtime hooks"
```

---

### Task 8: Push Notifications

**Files:**
- Create: `lib/notifications.ts`

- [ ] **Step 1: lib/notifications.ts**

```typescript
// lib/notifications.ts
import React, { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { ref, set } from 'firebase/database';
import { db } from './firebase';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) return null;

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') return null;

  const projectId = Constants.expoConfig?.extra?.eas?.projectId;
  const token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;

  await set(ref(db, '/push_token'), token);
  return token;
}

export function useNotificationNavigation(
  onDomainNotification: (domain: string) => void
) {
  const response = Notifications.useLastNotificationResponse();
  useEffect(() => {
    if (!response) return;
    const domain = response.notification.request.content.data?.domain as string | undefined;
    if (domain) onDomainNotification(domain);
  }, [response]);
}
```

- [ ] **Step 2: Commit**

```bash
git add lib/notifications.ts
git commit -m "feat: add expo push notification registration"
```

---

### Task 9: Bileşenler — ScoreBar ve ScanProgress

**Files:**
- Create: `components/ScoreBar.tsx`
- Create: `components/ScanProgress.tsx`

- [ ] **Step 1: components/ScoreBar.tsx**

```tsx
// components/ScoreBar.tsx
import React from 'react';
import { View, Text } from 'react-native';
import { DomainScore } from '../lib/scoring';

function scoreColor(total: number): string {
  if (total >= 80) return '#10b981'; // green
  if (total >= 60) return '#f59e0b'; // amber
  return '#ef4444'; // red
}

interface Props {
  score: DomainScore;
  compact?: boolean;
}

export function ScoreBar({ score, compact = false }: Props) {
  const color = scoreColor(score.total);
  return (
    <View className="w-full">
      <View className="flex-row items-center justify-between mb-1">
        <Text className="text-xs text-zinc-400">Skor</Text>
        <Text className="text-xs font-bold" style={{ color }}>{score.total}</Text>
      </View>
      <View className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <View
          className="h-full rounded-full"
          style={{ width: `${score.total}%`, backgroundColor: color }}
        />
      </View>
      {!compact && (
        <View className="flex-row justify-between mt-1">
          <Text className="text-[10px] text-zinc-500">Uzunluk {score.length}</Text>
          <Text className="text-[10px] text-zinc-500">Okunuş {score.pronounce}</Text>
          <Text className="text-[10px] text-zinc-500">Hafıza {score.memory}</Text>
        </View>
      )}
    </View>
  );
}
```

- [ ] **Step 2: components/ScanProgress.tsx**

```tsx
// components/ScanProgress.tsx
import React from 'react';
import { View, Text } from 'react-native';
import { ScanStatus } from '../types';

function eta(offset: number, total: number, startedAt: string | null): string {
  if (!startedAt || offset === 0) return '—';
  const elapsed = (Date.now() - new Date(startedAt).getTime()) / 1000;
  const rate = offset / elapsed; // domains/sec
  if (rate === 0) return '—';
  const remaining = (total - offset) / rate;
  const hours = Math.floor(remaining / 3600);
  const mins = Math.floor((remaining % 3600) / 60);
  return hours > 0 ? `~${hours}s ${mins}dk` : `~${mins}dk`;
}

interface Props {
  status: ScanStatus;
  current: string;
}

export function ScanProgress({ status, current }: Props) {
  const pct = status.total > 0 ? (status.offset / status.total) * 100 : 0;
  return (
    <View className="bg-zinc-900 rounded-xl p-4 mx-4">
      <View className="flex-row justify-between mb-2">
        <Text className="text-sm font-semibold text-white">
          {status.length}-Karakter Tarama
        </Text>
        <Text className="text-sm text-emerald-400">{pct.toFixed(1)}%</Text>
      </View>

      <View className="h-2 bg-zinc-800 rounded-full overflow-hidden mb-2">
        <View
          className="h-full bg-emerald-500 rounded-full"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </View>

      <View className="flex-row justify-between mb-3">
        <Text className="text-xs text-zinc-400">
          {status.offset.toLocaleString()} / {status.total.toLocaleString()}
        </Text>
        <Text className="text-xs text-zinc-400">
          ETA {eta(status.offset, status.total, status.started_at)}
        </Text>
      </View>

      <View className="flex-row items-center gap-2">
        <View className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <Text className="text-xs text-zinc-300 font-mono" numberOfLines={1}>
          {current || '—'}
        </Text>
      </View>
    </View>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/ScoreBar.tsx components/ScanProgress.tsx
git commit -m "feat: add ScoreBar and ScanProgress components"
```

---

### Task 10: FilterBar ve DomainCard

**Files:**
- Create: `components/FilterBar.tsx`
- Create: `components/DomainCard.tsx`

- [ ] **Step 1: components/FilterBar.tsx**

```tsx
// components/FilterBar.tsx
import React from 'react';
import { View, Text, TouchableOpacity, TextInput } from 'react-native';

export type LengthFilter = 'all' | '3' | '4' | '5';
export type PatternMode = 'starts' | 'contains' | 'ends';

interface Props {
  length: LengthFilter;
  onLengthChange: (l: LengthFilter) => void;
  pattern: string;
  patternMode: PatternMode;
  onPatternChange: (p: string) => void;
  onPatternModeChange: (m: PatternMode) => void;
}

const LENGTHS: LengthFilter[] = ['all', '3', '4', '5'];
const MODES: PatternMode[] = ['starts', 'contains', 'ends'];
const MODE_LABELS: Record<PatternMode, string> = {
  starts: 'Başlar',
  contains: 'İçerir',
  ends: 'Biter',
};

export function FilterBar({
  length, onLengthChange,
  pattern, patternMode,
  onPatternChange, onPatternModeChange,
}: Props) {
  return (
    <View className="px-4 gap-3 mb-2">
      <View className="flex-row gap-2">
        {LENGTHS.map(l => (
          <TouchableOpacity
            key={l}
            onPress={() => onLengthChange(l)}
            className={`px-3 py-1.5 rounded-full ${length === l ? 'bg-emerald-500' : 'bg-zinc-800'}`}
          >
            <Text className={`text-xs font-semibold ${length === l ? 'text-white' : 'text-zinc-400'}`}>
              {l === 'all' ? 'Tümü' : `${l} Harf`}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <View className="flex-row gap-2 items-center">
        <View className="flex-row gap-1">
          {MODES.map(m => (
            <TouchableOpacity
              key={m}
              onPress={() => onPatternModeChange(m)}
              className={`px-2 py-1 rounded-md ${patternMode === m ? 'bg-zinc-700' : 'bg-zinc-900'}`}
            >
              <Text className="text-[10px] text-zinc-300">{MODE_LABELS[m]}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <TextInput
          className="flex-1 bg-zinc-800 rounded-lg px-3 py-1.5 text-white text-sm"
          placeholder="filtrele..."
          placeholderTextColor="#71717a"
          value={pattern}
          onChangeText={onPatternChange}
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>
    </View>
  );
}
```

- [ ] **Step 2: components/DomainCard.tsx**

```tsx
// components/DomainCard.tsx
import React from 'react';
import { View, Text, TouchableOpacity, Linking, Share, Platform } from 'react-native';
import Animated, {
  useAnimatedStyle, useSharedValue, withSpring, runOnJS,
} from 'react-native-reanimated';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { AvailableDomain } from '../types';
import { scoreDomain } from '../lib/scoring';
import { ScoreBar } from './ScoreBar';

const SWIPE_THRESHOLD = 80;

interface Props {
  item: AvailableDomain;
  onFavorite: (id: string, favorited: boolean) => void;
  onPress: (id: string) => void;
}

export function DomainCard({ item, onFavorite, onPress }: Props) {
  const score = scoreDomain(item.domain);
  const translateX = useSharedValue(0);

  const pan = Gesture.Pan()
    .onUpdate(e => { translateX.value = e.translationX; })
    .onEnd(e => {
      if (e.translationX > SWIPE_THRESHOLD) {
        runOnJS(onFavorite)(item.id, !item.favorited);
      } else if (e.translationX < -SWIPE_THRESHOLD) {
        runOnJS(Clipboard.setStringAsync)(item.domain);
      }
      translateX.value = withSpring(0);
    });

  const animStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  return (
    <GestureDetector gesture={pan}>
      <Animated.View style={animStyle}>
        <TouchableOpacity
          onPress={() => onPress(item.id)}
          className="bg-zinc-900 mx-4 mb-2 rounded-xl p-4"
          activeOpacity={0.8}
        >
          <View className="flex-row items-center justify-between mb-2">
            <Text className="text-lg font-bold text-white">{item.domain}</Text>
            <TouchableOpacity onPress={() => onFavorite(item.id, !item.favorited)}>
              <Text className="text-xl">{item.favorited ? '⭐' : '☆'}</Text>
            </TouchableOpacity>
          </View>

          <ScoreBar score={score} compact />

          <View className="flex-row items-center justify-between mt-2">
            <Text className="text-xs text-zinc-500">
              {new Date(item.found_at).toLocaleDateString('tr-TR')}
            </Text>
            <Text className="text-xs text-zinc-600">← kopyala · favori →</Text>
          </View>
        </TouchableOpacity>
      </Animated.View>
    </GestureDetector>
  );
}
```

> Not: `Clipboard` import'u için `import * as Clipboard from 'expo-clipboard';` ve `npx expo install expo-clipboard` gerekli.

- [ ] **Step 3: expo-clipboard yükle**

```bash
npx expo install expo-clipboard
```

`DomainCard.tsx` başına ekle:
```typescript
import * as Clipboard from 'expo-clipboard';
```

- [ ] **Step 4: Commit**

```bash
git add components/FilterBar.tsx components/DomainCard.tsx
git commit -m "feat: add FilterBar and swipeable DomainCard"
```

---

### Task 11: App Layout

**Files:**
- Create: `app/_layout.tsx`
- Create: `app/(tabs)/_layout.tsx`

- [ ] **Step 1: app/_layout.tsx**

```tsx
// app/_layout.tsx
import React, { useEffect } from 'react';
import { Stack, useRouter } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { registerForPushNotifications, useNotificationNavigation } from '../lib/notifications';
import '../global.css';

export default function RootLayout() {
  const router = useRouter();

  useEffect(() => {
    registerForPushNotifications();
  }, []);

  useNotificationNavigation((domain) => {
    router.push(`/domain/${encodeURIComponent(domain)}`);
  });

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen
          name="domain/[id]"
          options={{ presentation: 'modal', headerShown: true, title: 'Domain Detay' }}
        />
      </Stack>
    </GestureHandlerRootView>
  );
}
```

- [ ] **Step 2: app/(tabs)/_layout.tsx**

```tsx
// app/(tabs)/_layout.tsx
import React from 'react';
import { Tabs } from 'expo-router';
import { Text } from 'react-native';

function TabIcon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.5 }}>{emoji}</Text>;
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: '#09090b', borderTopColor: '#27272a' },
        tabBarActiveTintColor: '#10b981',
        tabBarInactiveTintColor: '#71717a',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Canlı',
          tabBarIcon: ({ focused }) => <TabIcon emoji="📡" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="available"
        options={{
          title: 'Müsait',
          tabBarIcon: ({ focused }) => <TabIcon emoji="🟢" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="favorites"
        options={{
          title: 'Favoriler',
          tabBarIcon: ({ focused }) => <TabIcon emoji="⭐" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="stats"
        options={{
          title: 'İstatistik',
          tabBarIcon: ({ focused }) => <TabIcon emoji="📊" focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="control"
        options={{
          title: 'Kontrol',
          tabBarIcon: ({ focused }) => <TabIcon emoji="⚙️" focused={focused} />,
        }}
      />
    </Tabs>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add app/_layout.tsx app/\(tabs\)/_layout.tsx
git commit -m "feat: app layout with tabs and notification routing"
```

---

### Task 12: Live Feed Ekranı

**Files:**
- Create: `app/(tabs)/index.tsx`

- [ ] **Step 1: app/(tabs)/index.tsx**

```tsx
// app/(tabs)/index.tsx
import React, { useState, useCallback } from 'react';
import { View, Text, FlatList, SafeAreaView } from 'react-native';
import { useScanner } from '../../lib/useScanner';
import { useAvailable } from '../../lib/useAvailable';
import { ScanProgress } from '../../components/ScanProgress';
import { scoreDomain } from '../../lib/scoring';

const MAX_FEED = 50;

export default function LiveFeedScreen() {
  const { status, current, connected } = useScanner();
  const { domains } = useAvailable();
  const [feedLog, setFeedLog] = useState<string[]>([]);

  // Append current domain to feed log
  React.useEffect(() => {
    if (current) {
      setFeedLog(prev => [current, ...prev].slice(0, MAX_FEED));
    }
  }, [current]);

  const recentAvailable = domains.slice(0, 5).map(d => d.domain);

  return (
    <SafeAreaView className="flex-1 bg-black">
      {/* Header */}
      <View className="px-4 pt-4 pb-3 flex-row items-center justify-between">
        <Text className="text-xl font-bold text-white">📡 Canlı Tarama</Text>
        <View className={`flex-row items-center gap-1.5 px-2 py-1 rounded-full ${connected ? 'bg-emerald-950' : 'bg-zinc-800'}`}>
          <View className={`w-1.5 h-1.5 rounded-full ${connected ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
          <Text className={`text-xs ${connected ? 'text-emerald-400' : 'text-zinc-500'}`}>
            {connected ? 'Bağlı' : 'Bağlanıyor'}
          </Text>
        </View>
      </View>

      {/* Progress */}
      {status ? (
        status.scanning ? (
          <ScanProgress status={status} current={current} />
        ) : (
          <View className="bg-zinc-900 rounded-xl mx-4 p-4">
            <Text className="text-zinc-400 text-center">⏸ Scanner beklemede</Text>
          </View>
        )
      ) : (
        <View className="bg-zinc-900 rounded-xl mx-4 p-4">
          <Text className="text-zinc-500 text-center text-sm">Bağlanılıyor...</Text>
        </View>
      )}

      {/* Recent available highlight */}
      {recentAvailable.length > 0 && (
        <View className="mx-4 mt-3 mb-1">
          <Text className="text-xs text-zinc-500 mb-1">Son bulunanlar</Text>
          <View className="flex-row flex-wrap gap-2">
            {recentAvailable.map(d => (
              <View key={d} className="bg-emerald-950 border border-emerald-800 rounded-lg px-2 py-1">
                <Text className="text-emerald-300 text-xs font-mono">{d}</Text>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* Feed log */}
      <Text className="text-xs text-zinc-600 px-4 mt-3 mb-1">Taranan domainler</Text>
      <FlatList
        data={feedLog}
        keyExtractor={(item, i) => `${item}-${i}`}
        renderItem={({ item }) => {
          const isAvailable = recentAvailable.includes(item);
          return (
            <View className={`flex-row items-center px-4 py-0.5 ${isAvailable ? 'bg-emerald-950/30' : ''}`}>
              <Text className={`font-mono text-xs ${isAvailable ? 'text-emerald-400 font-bold' : 'text-zinc-600'}`}>
                {isAvailable ? '✓ ' : '  '}{item}
              </Text>
            </View>
          );
        }}
        ListEmptyComponent={
          <Text className="text-zinc-700 text-xs text-center mt-8">
            Tarama başladığında burada görünür
          </Text>
        }
      />
    </SafeAreaView>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add app/\(tabs\)/index.tsx
git commit -m "feat: live feed screen with scan progress and domain log"
```

---

### Task 13: Available ve Favorites Ekranları

**Files:**
- Create: `app/(tabs)/available.tsx`
- Create: `app/(tabs)/favorites.tsx`

- [ ] **Step 1: app/(tabs)/available.tsx**

```tsx
// app/(tabs)/available.tsx
import React, { useState, useMemo } from 'react';
import { View, Text, SafeAreaView } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import { useAvailable } from '../../lib/useAvailable';
import { DomainCard } from '../../components/DomainCard';
import { FilterBar, LengthFilter, PatternMode } from '../../components/FilterBar';
import { AvailableDomain } from '../../types';

function applyFilters(
  domains: AvailableDomain[],
  length: LengthFilter,
  pattern: string,
  patternMode: PatternMode
): AvailableDomain[] {
  return domains.filter(d => {
    const name = d.domain.replace('.com', '');
    if (length !== 'all' && d.length !== parseInt(length)) return false;
    if (pattern) {
      if (patternMode === 'starts' && !name.startsWith(pattern)) return false;
      if (patternMode === 'contains' && !name.includes(pattern)) return false;
      if (patternMode === 'ends' && !name.endsWith(pattern)) return false;
    }
    return true;
  });
}

export default function AvailableScreen() {
  const { domains, toggleFavorite } = useAvailable();
  const router = useRouter();
  const [length, setLength] = useState<LengthFilter>('all');
  const [pattern, setPattern] = useState('');
  const [patternMode, setPatternMode] = useState<PatternMode>('contains');

  const filtered = useMemo(
    () => applyFilters(domains, length, pattern, patternMode),
    [domains, length, pattern, patternMode]
  );

  return (
    <SafeAreaView className="flex-1 bg-black">
      <View className="px-4 pt-4 pb-3">
        <Text className="text-xl font-bold text-white">
          🟢 Müsait Domainler
          <Text className="text-sm font-normal text-zinc-500"> ({filtered.length})</Text>
        </Text>
      </View>

      <FilterBar
        length={length} onLengthChange={setLength}
        pattern={pattern} patternMode={patternMode}
        onPatternChange={setPattern} onPatternModeChange={setPatternMode}
      />

      <FlashList
        data={filtered}
        estimatedItemSize={120}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <DomainCard
            item={item}
            onFavorite={toggleFavorite}
            onPress={id => router.push(`/domain/${id}`)}
          />
        )}
        ListEmptyComponent={
          <Text className="text-zinc-600 text-center mt-16">
            {domains.length === 0 ? 'Henüz müsait domain bulunamadı' : 'Filtreye uyan domain yok'}
          </Text>
        }
      />
    </SafeAreaView>
  );
}
```

- [ ] **Step 2: app/(tabs)/favorites.tsx**

```tsx
// app/(tabs)/favorites.tsx
import React from 'react';
import { View, Text, SafeAreaView, TouchableOpacity, Linking } from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { useAvailable } from '../../lib/useAvailable';
import { ScoreBar } from '../../components/ScoreBar';
import { scoreDomain } from '../../lib/scoring';
import { AvailableDomain } from '../../types';

function FavoriteCard({
  item,
  onUnfavorite,
  onPress,
}: {
  item: AvailableDomain;
  onUnfavorite: () => void;
  onPress: () => void;
}) {
  const score = scoreDomain(item.domain);
  return (
    <TouchableOpacity
      onPress={onPress}
      className="bg-zinc-900 mx-4 mb-3 rounded-xl p-4"
      activeOpacity={0.8}
    >
      <View className="flex-row items-center justify-between mb-2">
        <Text className="text-lg font-bold text-white">{item.domain}</Text>
        <TouchableOpacity onPress={onUnfavorite}>
          <Text className="text-xl">⭐</Text>
        </TouchableOpacity>
      </View>

      <ScoreBar score={score} />

      {item.note ? (
        <View className="mt-2 bg-zinc-800 rounded-lg p-2">
          <Text className="text-xs text-zinc-300">{item.note}</Text>
        </View>
      ) : null}

      <View className="flex-row gap-2 mt-3">
        <TouchableOpacity
          onPress={() => Clipboard.setStringAsync(item.domain)}
          className="flex-1 bg-zinc-800 rounded-lg py-2 items-center"
        >
          <Text className="text-xs text-zinc-300">📋 Kopyala</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => Linking.openURL(`https://www.namecheap.com/domains/registration/results/?domain=${item.domain}`)}
          className="flex-1 bg-zinc-800 rounded-lg py-2 items-center"
        >
          <Text className="text-xs text-zinc-300">🔗 Namecheap</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => Linking.openURL(`https://www.godaddy.com/domainsearch/find?domainToCheck=${item.domain}`)}
          className="flex-1 bg-zinc-800 rounded-lg py-2 items-center"
        >
          <Text className="text-xs text-zinc-300">🔗 GoDaddy</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

export default function FavoritesScreen() {
  const { domains, toggleFavorite } = useAvailable();
  const router = useRouter();
  const favorites = domains.filter(d => d.favorited);

  return (
    <SafeAreaView className="flex-1 bg-black">
      <View className="px-4 pt-4 pb-3">
        <Text className="text-xl font-bold text-white">
          ⭐ Favoriler
          <Text className="text-sm font-normal text-zinc-500"> ({favorites.length})</Text>
        </Text>
      </View>

      <FlashList
        data={favorites}
        estimatedItemSize={160}
        keyExtractor={item => item.id}
        renderItem={({ item }) => (
          <FavoriteCard
            item={item}
            onUnfavorite={() => toggleFavorite(item.id, false)}
            onPress={() => router.push(`/domain/${item.id}`)}
          />
        )}
        ListEmptyComponent={
          <Text className="text-zinc-600 text-center mt-16">
            Henüz favori domain yok.{'\n'}Available ekranında → sağa kaydır
          </Text>
        }
      />
    </SafeAreaView>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add app/\(tabs\)/available.tsx app/\(tabs\)/favorites.tsx
git commit -m "feat: available domains and favorites screens"
```

---

### Task 14: Stats ve Control Ekranları

**Files:**
- Create: `app/(tabs)/stats.tsx`
- Create: `app/(tabs)/control.tsx`

- [ ] **Step 1: app/(tabs)/stats.tsx**

```tsx
// app/(tabs)/stats.tsx
import React from 'react';
import { View, Text, SafeAreaView, ScrollView, Dimensions } from 'react-native';
import { BarChart } from 'react-native-chart-kit';
import { useStats } from '../../lib/useStats';
import { useAvailable } from '../../lib/useAvailable';

const SCREEN_W = Dimensions.get('window').width;

export default function StatsScreen() {
  const stats = useStats();
  const { domains } = useAvailable();

  const breakdown = { 3: 0, 4: 0, 5: 0 };
  domains.forEach(d => { if (d.length in breakdown) (breakdown as any)[d.length]++; });

  const history = stats?.history?.slice(-14) ?? [];
  const chartData = {
    labels: history.map(h => h.date.slice(5)),
    datasets: [{ data: history.map(h => h.count) }],
  };

  return (
    <SafeAreaView className="flex-1 bg-black">
      <ScrollView>
        <View className="px-4 pt-4 pb-3">
          <Text className="text-xl font-bold text-white">📊 İstatistikler</Text>
        </View>

        {/* Counters */}
        <View className="flex-row gap-3 px-4 mb-6">
          {[
            { label: 'Toplam', value: stats?.total_found ?? 0, color: '#10b981' },
            { label: 'Bugün', value: stats?.today_found ?? 0, color: '#f59e0b' },
            { label: 'Toplam Taranan', value: '—', color: '#6366f1' },
          ].map(s => (
            <View key={s.label} className="flex-1 bg-zinc-900 rounded-xl p-3 items-center">
              <Text className="text-2xl font-bold" style={{ color: s.color }}>{s.value}</Text>
              <Text className="text-xs text-zinc-500 mt-1">{s.label}</Text>
            </View>
          ))}
        </View>

        {/* Breakdown */}
        <View className="px-4 mb-6">
          <Text className="text-sm text-zinc-400 mb-2">Karakter bazlı dağılım</Text>
          {([3, 4, 5] as const).map(len => (
            <View key={len} className="flex-row items-center gap-3 mb-2">
              <Text className="text-zinc-400 w-10 text-sm">{len} harf</Text>
              <View className="flex-1 h-3 bg-zinc-800 rounded-full overflow-hidden">
                <View
                  className="h-full bg-emerald-600 rounded-full"
                  style={{
                    width: `${domains.length > 0 ? (breakdown[len] / domains.length) * 100 : 0}%`,
                  }}
                />
              </View>
              <Text className="text-zinc-500 text-xs w-6">{breakdown[len]}</Text>
            </View>
          ))}
        </View>

        {/* Chart */}
        {history.length > 0 && (
          <View className="px-4">
            <Text className="text-sm text-zinc-400 mb-2">Son 14 gün</Text>
            <BarChart
              data={chartData}
              width={SCREEN_W - 32}
              height={180}
              yAxisLabel=""
              yAxisSuffix=""
              chartConfig={{
                backgroundColor: '#09090b',
                backgroundGradientFrom: '#09090b',
                backgroundGradientTo: '#09090b',
                color: () => '#10b981',
                labelColor: () => '#71717a',
                barPercentage: 0.6,
              }}
              style={{ borderRadius: 12 }}
            />
          </View>
        )}

        {stats?.last_run && (
          <Text className="text-xs text-zinc-700 text-center mt-4 pb-8">
            Son tarama: {new Date(stats.last_run).toLocaleString('tr-TR')}
          </Text>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
```

- [ ] **Step 2: react-native-chart-kit yükle**

```bash
npm install react-native-chart-kit
```

- [ ] **Step 3: app/(tabs)/control.tsx**

```tsx
// app/(tabs)/control.tsx
import React, { useState, useEffect } from 'react';
import { View, Text, SafeAreaView, TouchableOpacity, ScrollView } from 'react-native';
import Slider from '@react-native-community/slider';
import { ref, set, onValue } from 'firebase/database';
import { db } from '../../lib/firebase';
import { ControlSettings } from '../../types';

export default function ControlScreen() {
  const [settings, setSettings] = useState<ControlSettings>({
    command: 'run',
    slice: 50000,
    concurrency: 100,
  });
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const unsub = onValue(ref(db, '/control'), snap => {
      const val = snap.val();
      if (val) setSettings({
        command: val.command ?? 'run',
        slice: val.slice ?? 50000,
        concurrency: val.concurrency ?? 100,
      });
    });
    return unsub;
  }, []);

  const save = async () => {
    await set(ref(db, '/control'), settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const toggleCommand = () => {
    setSettings(s => ({ ...s, command: s.command === 'run' ? 'stop' : 'run' }));
  };

  return (
    <SafeAreaView className="flex-1 bg-black">
      <ScrollView>
        <View className="px-4 pt-4 pb-3">
          <Text className="text-xl font-bold text-white">⚙️ Kontrol Paneli</Text>
        </View>

        {/* Scanner toggle */}
        <View className="bg-zinc-900 mx-4 rounded-xl p-4 mb-4">
          <View className="flex-row items-center justify-between">
            <View>
              <Text className="text-white font-semibold">Scanner Durumu</Text>
              <Text className="text-xs text-zinc-500 mt-0.5">
                {settings.command === 'run' ? 'Çalışıyor' : 'Durduruldu'}
              </Text>
            </View>
            <TouchableOpacity
              onPress={toggleCommand}
              className={`px-5 py-2.5 rounded-full ${settings.command === 'run' ? 'bg-red-900' : 'bg-emerald-900'}`}
            >
              <Text className={`font-semibold ${settings.command === 'run' ? 'text-red-300' : 'text-emerald-300'}`}>
                {settings.command === 'run' ? '⏹ Durdur' : '▶ Başlat'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* Slice size */}
        <View className="bg-zinc-900 mx-4 rounded-xl p-4 mb-4">
          <View className="flex-row justify-between mb-2">
            <Text className="text-white font-semibold">Günlük 5-Char Dilim</Text>
            <Text className="text-emerald-400 font-bold">{settings.slice.toLocaleString()}</Text>
          </View>
          <Slider
            minimumValue={10000}
            maximumValue={200000}
            step={5000}
            value={settings.slice}
            onValueChange={v => setSettings(s => ({ ...s, slice: v }))}
            minimumTrackTintColor="#10b981"
            maximumTrackTintColor="#27272a"
            thumbTintColor="#10b981"
          />
          <View className="flex-row justify-between">
            <Text className="text-xs text-zinc-600">10k</Text>
            <Text className="text-xs text-zinc-600">200k</Text>
          </View>
        </View>

        {/* Concurrency */}
        <View className="bg-zinc-900 mx-4 rounded-xl p-4 mb-6">
          <View className="flex-row justify-between mb-2">
            <Text className="text-white font-semibold">DNS Concurrency</Text>
            <Text className="text-emerald-400 font-bold">{settings.concurrency}</Text>
          </View>
          <Slider
            minimumValue={50}
            maximumValue={500}
            step={25}
            value={settings.concurrency}
            onValueChange={v => setSettings(s => ({ ...s, concurrency: v }))}
            minimumTrackTintColor="#10b981"
            maximumTrackTintColor="#27272a"
            thumbTintColor="#10b981"
          />
          <View className="flex-row justify-between">
            <Text className="text-xs text-zinc-600">50</Text>
            <Text className="text-xs text-zinc-600">500</Text>
          </View>
        </View>

        {/* Save */}
        <TouchableOpacity
          onPress={save}
          className={`mx-4 py-4 rounded-xl items-center ${saved ? 'bg-emerald-700' : 'bg-emerald-600'}`}
        >
          <Text className="text-white font-bold">{saved ? '✓ Kaydedildi' : 'Kaydet'}</Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}
```

- [ ] **Step 4: Slider yükle**

```bash
npx expo install @react-native-community/slider
```

- [ ] **Step 5: Commit**

```bash
git add app/\(tabs\)/stats.tsx app/\(tabs\)/control.tsx
git commit -m "feat: stats and control panel screens"
```

---

### Task 15: Domain Detay Sheet

**Files:**
- Create: `app/domain/[id].tsx`

- [ ] **Step 1: app/domain/[id].tsx**

```tsx
// app/domain/[id].tsx
import React, { useState } from 'react';
import {
  View, Text, SafeAreaView, TouchableOpacity,
  TextInput, Linking, ScrollView,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import * as Clipboard from 'expo-clipboard';
import { useAvailable } from '../../lib/useAvailable';
import { ScoreBar } from '../../components/ScoreBar';
import { scoreDomain } from '../../lib/scoring';

export default function DomainDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { domains, toggleFavorite, setNote } = useAvailable();
  const item = domains.find(d => d.id === id);
  const [editingNote, setEditingNote] = useState(false);
  const [noteText, setNoteText] = useState(item?.note ?? '');

  if (!item) {
    return (
      <SafeAreaView className="flex-1 bg-black items-center justify-center">
        <Text className="text-zinc-500">Domain bulunamadı</Text>
        <TouchableOpacity onPress={() => router.back()} className="mt-4">
          <Text className="text-emerald-400">← Geri</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const score = scoreDomain(item.domain);

  const saveNote = () => {
    setNote(item.id, noteText);
    setEditingNote(false);
  };

  return (
    <SafeAreaView className="flex-1 bg-black">
      <ScrollView className="px-4 pt-4">
        {/* Domain name */}
        <View className="items-center mb-6">
          <Text className="text-3xl font-bold text-white mb-1">{item.domain}</Text>
          <Text className="text-zinc-500 text-sm">
            {item.length}-karakter · Bulundu: {new Date(item.found_at).toLocaleString('tr-TR')}
          </Text>
        </View>

        {/* Score */}
        <View className="bg-zinc-900 rounded-xl p-4 mb-4">
          <Text className="text-sm text-zinc-400 mb-3">Domain Skoru</Text>
          <ScoreBar score={score} />
        </View>

        {/* Favorite */}
        <TouchableOpacity
          onPress={() => toggleFavorite(item.id, !item.favorited)}
          className={`flex-row items-center justify-center gap-2 rounded-xl py-3 mb-4 ${item.favorited ? 'bg-yellow-900' : 'bg-zinc-900'}`}
        >
          <Text className="text-xl">{item.favorited ? '⭐' : '☆'}</Text>
          <Text className={`font-semibold ${item.favorited ? 'text-yellow-300' : 'text-zinc-400'}`}>
            {item.favorited ? 'Favorilerden çıkar' : 'Favorilere ekle'}
          </Text>
        </TouchableOpacity>

        {/* Note */}
        <View className="bg-zinc-900 rounded-xl p-4 mb-4">
          <View className="flex-row justify-between items-center mb-2">
            <Text className="text-sm text-zinc-400">Not</Text>
            {!editingNote && (
              <TouchableOpacity onPress={() => setEditingNote(true)}>
                <Text className="text-xs text-emerald-400">Düzenle</Text>
              </TouchableOpacity>
            )}
          </View>
          {editingNote ? (
            <>
              <TextInput
                className="text-white text-sm bg-zinc-800 rounded-lg p-3 mb-2"
                value={noteText}
                onChangeText={setNoteText}
                placeholder="Bu domain hakkında not..."
                placeholderTextColor="#52525b"
                multiline
                autoFocus
              />
              <View className="flex-row gap-2">
                <TouchableOpacity onPress={saveNote} className="flex-1 bg-emerald-700 rounded-lg py-2 items-center">
                  <Text className="text-white text-sm font-semibold">Kaydet</Text>
                </TouchableOpacity>
                <TouchableOpacity onPress={() => setEditingNote(false)} className="flex-1 bg-zinc-800 rounded-lg py-2 items-center">
                  <Text className="text-zinc-400 text-sm">İptal</Text>
                </TouchableOpacity>
              </View>
            </>
          ) : (
            <Text className="text-zinc-300 text-sm">{item.note || 'Not yok'}</Text>
          )}
        </View>

        {/* Actions */}
        <View className="gap-3 pb-8">
          <TouchableOpacity
            onPress={() => Clipboard.setStringAsync(item.domain)}
            className="flex-row items-center justify-center gap-2 bg-zinc-900 rounded-xl py-3"
          >
            <Text className="text-zinc-300">📋 Kopyala</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => Linking.openURL(`https://www.namecheap.com/domains/registration/results/?domain=${item.domain}`)}
            className="flex-row items-center justify-center gap-2 bg-zinc-900 rounded-xl py-3"
          >
            <Text className="text-zinc-300">🛒 Namecheap'te Aç</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => Linking.openURL(`https://www.godaddy.com/domainsearch/find?domainToCheck=${item.domain}`)}
            className="flex-row items-center justify-center gap-2 bg-zinc-900 rounded-xl py-3"
          >
            <Text className="text-zinc-300">🛒 GoDaddy'de Aç</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => Linking.openURL(`https://whois.domaintools.com/${item.domain}`)}
            className="flex-row items-center justify-center gap-2 bg-zinc-900 rounded-xl py-3"
          >
            <Text className="text-zinc-300">🔍 WHOIS Sorgula</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add app/domain/
git commit -m "feat: domain detail sheet with scoring, notes, and quick actions"
```

---

### Task 16: Son Test ve Deployment

- [ ] **Step 1: Jest config ekle (package.json'a)**

```json
"jest": {
  "preset": "jest-expo",
  "transformIgnorePatterns": [
    "node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@unimodules/.*|unimodules|sentry-expo|native-base|react-native-svg)"
  ]
}
```

```bash
npm install --save-dev jest-expo @types/jest
```

- [ ] **Step 2: Tüm testleri çalıştır**

```bash
npx jest
```
Beklenen: `scoring.test.ts` 4 PASSED

- [ ] **Step 3: TypeScript kontrolü**

```bash
npx tsc --noEmit
```
Beklenen: 0 hata

- [ ] **Step 4: Expo Go ile test et**

```bash
npx expo start
```
Telefonda Expo Go açık, QR kodu tara, 5 tab göründüğünü ve Firebase bağlantısının "Bağlı" olduğunu doğrula.

- [ ] **Step 5: EAS Build (opsiyonel — production için)**

```bash
npm install -g eas-cli
eas login
eas build:configure
eas build --platform android --profile preview
```

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: complete domaino mobile app with firebase integration"
```
