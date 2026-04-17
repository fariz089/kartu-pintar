# 🔧 FINDMY TRACKER FIX — Kartu Pintar

> Fix kenapa UI FindMy Tracker selalu nunjukin **"Belum ada data"** padahal
> harusnya update tiap 1 menit.

---

## 🎯 Ringkasan Bug yang Diperbaiki

| # | Bug | Lokasi | Efek |
|---|-----|--------|------|
| 1 | Worker FindMy diaktifkan di dalam `if __name__ == '__main__'` | `app.py:1921` | **Gunicorn skip blok ini** → worker TIDAK PERNAH jalan di production |
| 2 | Dependencies `findmy_tools/requirements.txt` tidak di-install di Docker | `Dockerfile` | `_load_tools()` gagal ImportError |
| 3 | `secrets.json` tidak persisten antar rebuild | `docker-compose.yml` | Harus login Google ulang tiap `docker compose down` |
| 4 | Tidak ada pengaman multi-worker | `findmy_service.py` | 4 gunicorn worker → 4x spam Google API → ban |
| 5 | Tidak ada indikator status worker & tombol refresh manual | UI | Ga bisa tahu worker hidup/mati tanpa lihat log |

Semua 5 bug ini sudah diperbaiki di file-file di folder ini.

---

## 📂 Struktur Folder (Sama Persis dengan Project Kamu)

```
kartu-pintar-findmy-fix/
├── app.py                              ← REPLACE (aktivasi FindMy dipindah keluar __main__)
├── findmy_service.py                   ← REPLACE (+ file-lock election, status, logging)
├── findmy_worker.py                    ← NEW (worker standalone opsional)
├── Dockerfile                          ← REPLACE (install findmy_tools deps)
├── docker-compose.yml                  ← REPLACE (volume mount secrets.json + service worker opsional)
└── templates/
    └── admin/
        └── findmy_trackers.html        ← REPLACE (+ status indicator, tombol refresh manual)
```

Tinggal **copy-replace** file-file di atas ke directory yang sama di project kamu.

---

## 🚀 Cara Apply (5 langkah)

### 1. Backup project lama (jaga-jaga)

```bash
cd /path/ke/kartu-pintar
tar -czf backup-before-findmy-fix.tgz app.py findmy_service.py Dockerfile docker-compose.yml templates/admin/findmy_trackers.html
```

### 2. Replace semua file dari zip

Extract isi zip ini, lalu copy-overwrite ke root project kamu (struktur sama persis).

### 3. Pastikan `findmy_tools/Auth/secrets.json` ada

Kalau belum pernah generate, jalankan **di mesin lokal yang ada Chrome** (bukan di container):

```bash
cd kartu-pintar
python findmy_tools/main.py
# Ikuti flow login Google. File secrets.json akan dibuat di findmy_tools/Auth/
```

### 4. Rebuild & restart Docker

```bash
docker compose down
docker compose build --no-cache   # penting: ada dep baru di Dockerfile
docker compose up -d
```

### 5. Verifikasi

```bash
# Cek log — harusnya muncul:
docker compose logs -f web | grep FindMy

# Output yang diharapkan:
# [FindMy] FindMy service initialized (reading trackers from database)
# [FindMy] Acquired leader lock (pid=..., file=/var/run/kartu-pintar/findmy_leader.lock)
# [FindMy] ⚡ Background worker started (interval=60s, pid=...)
# [FindMy] GoogleFindMyTools loaded successfully
# [FindMy] Requesting location for MiLi Card - Andi...
# [FindMy] Updated Praka Andi Wijaya: -7.983908, 112.621391
# [FindMy] ✅ Integration aktif. Worker leader pid=..., interval=60s
```

Lalu buka **Admin Panel → FindMy Trackers**. Sekarang ada:
- 🟢 **Status card** di atas (harusnya "Worker aktif (leader)" dengan dot hijau berdenyut)
- Tombol **"Update Lokasi Sekarang"** untuk force-update manual (pakai ini buat test cepat)
- Data di kolom "Lokasi Terakhir" akan terisi setelah cycle pertama (max 1 menit)

---

## 🔍 Kalau Masih "Belum Ada Data" Setelah Fix

Urutan cek:

### Cek 1: Klik "Cek Status" di UI

Baca error yang muncul di bawah status card. 3 kemungkinan umum:

- **`ImportError: No module named ...`** → Dockerfile build pakai cache lama. Jalankan `docker compose build --no-cache`.
- **`FileNotFoundError: secrets.json`** → Belum generate auth. Jalankan `python findmy_tools/main.py` di lokal, lalu copy `findmy_tools/Auth/secrets.json` ke container (via volume mount `findmy_auth`).
- **`Timeout waiting for location response`** → Tracker sedang tidak dekat Android aktif. Bawa tracker ke tempat ramai / reboot perangkat tracker.

### Cek 2: Klik "Update Lokasi Sekarang"

Tombol ini trigger `update_all_locations()` langsung. Kalau sukses → worker logic OK, tinggal tunggu cycle berikutnya.

### Cek 3: Log worker

```bash
docker compose logs --tail=200 web | grep -i findmy
```

### Cek 4: Apakah leader lock di-hold oleh proses yang sudah mati?

```bash
docker compose exec web cat /var/run/kartu-pintar/findmy_leader.lock
# Kalau pid di sana beda dengan proses gunicorn yg hidup, hapus lalu restart:
docker compose exec web rm /var/run/kartu-pintar/findmy_leader.lock
docker compose restart web
```

---

## 🏗️ (Opsional) Arsitektur Bersih: Worker Service Terpisah

Kalau mau lebih clean (direkomendasikan untuk production jangka panjang):

1. Di `docker-compose.yml`, **uncomment** block service `findmy-worker`.
2. Di service `web`, ubah `FINDMY_AUTO_START=1` → `FINDMY_AUTO_START=0`.
3. `docker compose up -d --build`.

Hasilnya:
- `kartu-pintar-web` (gunicorn) → cuma handle HTTP request. Ringan, stateless.
- `kartu-pintar-findmy-worker` → proses terpisah yang loop update tracker.
- Bisa restart satu service tanpa ganggu yang lain.

---

## 📌 File yang Diubah vs Tidak Diubah

**Diubah (replace):**
- `app.py` — pindah aktivasi FindMy keluar `__main__`, tambah `FINDMY_AUTO_START` env var
- `findmy_service.py` — leader election, status tracking, endpoint `/api/findmy/worker-status`
- `Dockerfile` — install findmy_tools runtime deps
- `docker-compose.yml` — volume mount `findmy_auth`, service worker opsional
- `templates/admin/findmy_trackers.html` — status card + tombol refresh manual

**TIDAK diubah:**
- `models.py` — skema database sama (tidak perlu migrasi)
- `config.py` — tetap, cuma baca `FINDMY_UPDATE_INTERVAL` dari env
- `findmy_tools/*` — library pihak ketiga, biarkan
- Semua route/template lain

**DB migration:** ❌ tidak perlu. Skema `findmy_tracker` sudah OK, cuma kolom-kolomnya yang selama ini ga pernah keisi karena worker mati.

---

Kalau ada yang aneh, kirim output `docker compose logs --tail=300 web | grep -i findmy` dan saya bantu debug.
