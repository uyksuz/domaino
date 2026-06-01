# Domaino Mobile App — Design Spec
Date: 2026-05-28

## Overview

Mevcut Python domain tarayıcısına Firebase Realtime DB entegrasyonu eklenerek Expo tabanlı bir mobil uygulama ile canlı tarama takibi sağlanacak. Uygulama kişisel kullanım içindir, tek kullanıcı, auth yok.

---

## Architecture

```
Python Scanner (VPS, domain.diyesto.com)
  └─ firebase-admin SDK
       └─ Firebase Realtime DB
            └─ Expo App (iOS/Android)
                  ├─ onValue listeners (real-time)
                  └─ Expo Push Notifications
```

---

## Python Backend Changes

### New Files
- `firebase_writer.py` — Firebase write helpers (scan status, current domain, available domain, stats)

### Modified Files
- `requirements.txt` — add `firebase-admin`
- `checker.py` — call `firebase_writer.update_current(domain)` in `_check_one`, call `firebase_writer.add_available(domain)` when available
- `main.py` — call `firebase_writer.set_scan_status()` at start/end of each length scan, update stats after run
- `.env` / `.env.example` — add `FIREBASE_CREDENTIALS_PATH`

### Firebase Write Operations
| Operation | When | Path |
|-----------|------|------|
| `set_scan_status(scanning, length, offset, total)` | Start/end of each length scan | `/scan/status` |
| `update_current(domain)` | Every DNS check | `/scan/current` |
| `add_available(domain, length)` | Domain confirmed available | `/available/{push_id}` |
| `update_stats()` | End of full scan | `/stats` |
| `send_push_notification(domain)` | Domain confirmed available | Expo Push API |

---

## Firebase Realtime DB Schema

```json
{
  "scan": {
    "status": {
      "scanning": true,
      "length": 5,
      "offset": 123400,
      "total": 11881376,
      "started_at": "2026-05-28T10:00:00Z"
    },
    "current": "xkqbz.com"
  },
  "available": {
    "-Nabc123": {
      "domain": "xkq.com",
      "found_at": "2026-05-28T10:23:00Z",
      "length": 3,
      "favorited": false,
      "note": ""
    }
  },
  "stats": {
    "total_found": 142,
    "today_found": 7,
    "last_run": "2026-05-28T10:00:00Z",
    "history": [
      { "date": "2026-05-28", "count": 7 },
      { "date": "2026-05-27", "count": 12 }
    ]
  },
  "push_token": "ExponentPushToken[xxxxxx]"
}
```

---

## Expo App

### Tech Stack
- Expo SDK 53 (latest)
- Firebase JS SDK v10 (Realtime DB)
- Expo Router (file-based, tabs)
- NativeWind v4 (Tailwind)
- Zustand (state management)
- FlashList (performant lists)
- Expo Notifications (push)
- React Native Reanimated (swipe gesture)

### Screen Structure
```
app/
  _layout.tsx              → Root layout, Firebase init, notification setup
  (tabs)/
    _layout.tsx            → Tab bar config
    index.tsx              → Live Feed
    available.tsx          → Available Domains
    favorites.tsx          → Favorites
    stats.tsx              → Statistics
    control.tsx            → Control Panel
  domain/[id].tsx          → Domain detail sheet

lib/
  firebase.ts              → Firebase app init + Realtime DB ref
  useScanner.ts            → Live scan status hook (onValue)
  useAvailable.ts          → Available domains hook (onValue)
  scoring.ts               → Domain score calculator
  notifications.ts         → Push token registration + Expo API

components/
  DomainCard.tsx           → Swipeable domain card (favorite/copy)
  ScanProgress.tsx         → Progress bar + current domain ticker
  ScoreBar.tsx             → Visual domain score indicator
  FilterBar.tsx            → Length + pattern filter controls
```

### Screens

#### 1. Live Feed (`index.tsx`)
- Gerçek zamanlı ticker: şu an taranan domain (hızlı güncellenir)
- Progress bar: offset/total, yüzde, tahmini bitiş süresi
- Son 50 kontrol edilen domain listesi (FlashList, en yeni üstte)
- Yeşil highlight: müsait bulunanlar feed'de anında beliriyor
- Tarama aktif değilse "Scanner idle" state

#### 2. Available Domains (`available.tsx`)
- Tüm müsait domainler, en yeni üstte
- FilterBar: 3 / 4 / 5 karakter toggle
- Pattern arama: "başlar", "içerir", "biter" (regex olmadan, basit string)
- Her kart: domain adı, skor bar, bulunma tarihi, favori butonu
- Swipe right → favori, swipe left → kopyala
- Tıkla → domain detail sheet

#### 3. Favorites (`favorites.tsx`)
- Favorilenen domainler
- Not ekleme/düzenleme (inline text input)
- Hızlı aksiyonlar: Namecheap'te aç, GoDaddy'de aç, kopyala
- Sıralama: tarihe göre, skora göre

#### 4. Statistics (`stats.tsx`)
- Günlük bar chart (son 14 gün, React Native SVG veya Victory Native)
- Sayaçlar: toplam bulunan, bugün bulunan, toplam taranan
- 3/4/5 karakter breakdown (pie veya bar)
- Son tarama zamanı

#### 5. Control Panel (`control.tsx`)
- Scanner durumu (aktif/pasif badge)
- Scanner'ı başlat / durdur (Firebase üzerinden sinyal: `/control/command`)
- DAILY_SLICE_5CHAR ayarı (slider: 10k–200k)
- DNS_CONCURRENCY ayarı (slider: 50–500)
- Bu ayarlar Firebase'e yazılır, Python başlangıçta okur

### Domain Scoring (`scoring.ts`)
0–100 arası skor, 3 bileşen:

| Bileşen | Ağırlık | Açıklama |
|---------|---------|----------|
| Length | 50% | 3 char=100, 4 char=75, 5 char=50 |
| Pronounceability | 35% | Ünlü oranı + CV/CVC pattern bonus |
| Memorability | 15% | Tekrar eden harf yok, ardışık ünsüz yok bonus |

### Push Notifications
1. Uygulama açılınca Expo push token alınır, `/push_token` Firebase'e yazılır
2. Python: domain müsait bulununca `/push_token` okur, Expo Push API'ye HTTP POST
3. Bildirim: "🟢 xkq.com müsait! Skor: 94"
4. Bildirime tıklayınca domain detail sheet açılır

---

## Control Loop (Python)

`main.py`'e `/control/command` dinleyicisi eklenecek. Değer `"stop"` olursa tarama durur, `"start"` olursa devam eder. Slice ve concurrency değerleri her run başında Firebase'den okunur.

---

## Out of Scope
- Kullanıcı authentication
- Çoklu TLD (.net, .io) — altyapı hazır kalacak ama eklenmeyecek
- Domain fiyat sorgulama (registrar API)
- Web dashboard

---

## Success Criteria
- Telefonda domain.diyesto.com'dan bağımsız olarak, scanner çalışırken canlı feed akıyor
- Yeni domain bulununca 5 saniye içinde push notification geliyor
- Favoriler Firebase'de kalıcı (uygulama silinse bile)
- Skor hesabı tutarlı ve anlamlı (kısa + okunabilir = yüksek skor)
