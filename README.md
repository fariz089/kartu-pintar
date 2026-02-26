# 🪖 KARTU PINTAR — Poltekkad

**Sistem Kartu Tanda Anggota Digital**
TNI Angkatan Darat — Politeknik Angkatan Darat

## 📋 Deskripsi

Kartu Pintar adalah sistem manajemen kartu anggota digital berbasis NFC dan QR Code untuk TNI AD Poltekkad. Fitur utama:

- 🪪 **Identitas Digital** — Scan NFC/QR untuk melihat identitas pemegang kartu
- 💳 **Pembayaran Kantin** — Tap kartu NFC untuk bayar di kantin Poltekkad
- 💰 **E-Wallet** — Cek saldo dan top up
- 📍 **Lacak Kartu** — Tracking lokasi terakhir kartu (jika hilang/terjatuh)
- 📊 **Dashboard** — Monitoring seluruh data anggota dan transaksi

## 🛠️ Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python Flask |
| Frontend Web | Jinja2 Templates + Custom CSS |
| Database | MySQL (PyMySQL + SQLAlchemy) |
| Mobile (planned) | React Native |
| Auth | Session-based + Password Hashing (pbkdf2) |

## 📁 Struktur Project

```
kartu-pintar/
├── app.py              # Flask application (routes + API)
├── config.py           # Configuration (DB, session, etc)
├── models.py           # SQLAlchemy ORM models
├── seed.py             # Database seeder (dummy data)
├── manage.py           # CLI management tool
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
├── database/
│   └── schema.sql      # MySQL schema (manual setup)
├── static/
│   ├── css/style.css   # Custom stylesheet
│   ├── js/main.js      # JavaScript
│   └── img/            # Images
└── templates/
    ├── base.html        # Base layout (sidebar + topbar)
    ├── auth/login.html  # Login page
    ├── dashboard.html   # Dashboard
    ├── anggota_*.html   # Data anggota pages
    ├── scan.html        # Scan NFC/QR
    ├── scan_result.html # Scan result (identity)
    ├── pembayaran.html  # Payment (numpad)
    ├── transaksi.html   # Transaction history
    ├── lacak_kartu.html # Track card location
    └── admin/
        ├── anggota_form.html  # Add/Edit anggota
        └── topup.html         # Top up saldo
```

## 🚀 Setup & Instalasi

### 1. Prerequisites

- Python 3.10+
- MySQL 8.0+
- pip

### 2. Clone & Install

```bash
git clone https://github.com/fariz089/kartu-pintar.git
cd kartu-pintar

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Database

```bash
# Buat database MySQL dulu
mysql -u root -p -e "CREATE DATABASE kartu_pintar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Copy dan edit konfigurasi
cp .env.example .env
# Edit .env — isi DB_PASSWORD dengan password MySQL kamu
```

### 4. Initialize & Seed

```bash
# Buat tabel
python manage.py init-db

# Isi data dummy
python manage.py seed
```

### 5. Jalankan

```bash
python app.py
# Buka http://localhost:5000
```

### Login Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin (full access) |
| `user1` | `user123` | User (limited) |
| `kantin1` | `kantin123` | Operator Kantin |

## 📡 API Endpoints

Base URL: `http://localhost:5000/api`

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login (JSON body: username, password) |

### Anggota
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/anggota` | List semua anggota (?search=keyword) |
| GET | `/api/anggota/{kartu_id}` | Detail anggota |

### Scan
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scan/nfc/{nfc_uid}` | Scan NFC — identitas + update lokasi |
| GET | `/api/scan/qr/{qr_data}` | Scan QR — identitas + update lokasi |

### Keuangan
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/pembayaran` | Proses pembayaran (JSON: kartu_id, nominal, keterangan, metode) |
| POST | `/api/topup` | Top up saldo (JSON: kartu_id, nominal) |
| GET | `/api/transaksi` | Riwayat transaksi (?kartu_id=, ?jenis=, ?limit=) |

### Lainnya
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/lacak/{kartu_id}` | Lokasi terakhir + history |
| GET | `/api/menu` | Menu kantin |
| GET | `/api/dashboard/stats` | Statistik dashboard |

### Contoh Request

```bash
# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Scan NFC
curl http://localhost:5000/api/scan/nfc/A1B2C3D4

# Pembayaran
curl -X POST http://localhost:5000/api/pembayaran \
  -H "Content-Type: application/json" \
  -d '{"kartu_id": "KP-2025-001", "nominal": 15000, "keterangan": "Nasi Goreng"}'
```

## 📝 Management Commands

```bash
python manage.py init-db       # Buat tabel
python manage.py seed          # Isi data dummy
python manage.py drop-db       # Hapus semua tabel
python manage.py reset-db      # Reset (drop + create + seed)
python manage.py create-user   # Buat user baru (interactive)
```

## 🔒 Security Features

- Password di-hash dengan **PBKDF2 + SHA256** (bukan plain text)
- Session-based authentication dengan timeout
- Role-based access control (Admin, User, Operator Kantin)
- Input validation & SQL injection protection (SQLAlchemy ORM)
- CSRF protection via Flask session

## 📱 Next Steps

- [ ] React Native mobile app
- [ ] JWT authentication untuk mobile API
- [ ] Real NFC hardware integration
- [ ] QR Code generation pada kartu
- [ ] Real-time GPS tracking
- [ ] Export laporan ke Excel/PDF

---

**Politeknik Angkatan Darat** © 2025
