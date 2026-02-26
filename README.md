# 🛡️ KARTU PINTAR — Poltekkad

**Sistem Kartu Tanda Anggota Digital TNI Angkatan Darat Poltekkad**

Frontend web menggunakan **Python Flask + Jinja2** dengan desain bertema militer (olive/gold).

---

## 🚀 Cara Menjalankan

```bash
# Install dependency
pip install flask

# Jalankan aplikasi
python app.py

# Buka di browser
http://localhost:5000
```

## 🔐 Demo Login

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |
| User  | user1    | user123   |

## 📁 Struktur Project

```
kartu-pintar/
├── app.py                          # Main Flask application
├── static/
│   ├── css/style.css               # Stylesheet utama
│   ├── js/main.js                  # JavaScript utama
│   └── img/avatar-default.svg      # Default avatar
├── templates/
│   ├── base.html                   # Base template (sidebar, topbar)
│   ├── dashboard.html              # Halaman dashboard
│   ├── anggota_list.html           # Daftar anggota
│   ├── anggota_detail.html         # Detail anggota + kartu identitas
│   ├── scan.html                   # Halaman scan NFC / QR
│   ├── scan_result.html            # Hasil scan kartu
│   ├── pembayaran.html             # Pembayaran kantin (numpad)
│   ├── transaksi.html              # Riwayat transaksi
│   ├── lacak_kartu.html            # Lacak kartu hilang
│   ├── auth/
│   │   └── login.html              # Halaman login
│   └── admin/
│       ├── anggota_form.html       # Form tambah/edit anggota
│       └── topup.html              # Top up saldo (admin only)
└── README.md
```

## 📋 Fitur

| Fitur | Deskripsi |
|-------|-----------|
| **Dashboard** | Statistik anggota, kartu aktif/hilang, total saldo, transaksi terbaru |
| **Data Anggota** | CRUD data anggota dengan pencarian dan filter |
| **Scan NFC** | Simulasi scan kartu NFC untuk identifikasi anggota |
| **Scan QR Code** | Simulasi scan QR Code untuk melihat identitas pemegang kartu |
| **Pembayaran Kantin** | Form pembayaran dengan numpad dan quick amount |
| **Top Up Saldo** | Isi ulang saldo kartu (khusus admin) |
| **Riwayat Transaksi** | Daftar semua transaksi dengan filter |
| **Lacak Kartu** | Lokasi terakhir kartu, peringatan kartu hilang |
| **Kartu Identitas Digital** | Preview kartu dengan NFC UID dan QR Code |
| **Role-based Access** | Admin dan User memiliki akses berbeda |

## 🔒 Hak Akses

- **Admin**: Akses penuh (CRUD anggota, top up saldo, semua fitur)
- **User**: Lihat data, scan, pembayaran, lacak kartu
- **Sipil (tidak login)**: Tidak bisa mengakses sistem

## 🎨 Design

- Tema militer olive-green + brass/gold
- Font: Bebas Neue (heading) + DM Sans (body)
- Dark mode dengan aksen emas
- Responsive (mobile-friendly)
- Preview kartu identitas digital (ID Card)

## 📝 Catatan

- Data saat ini menggunakan **dummy data** (hardcoded di `app.py`)
- Untuk production, ganti dengan **database** (SQLite/PostgreSQL/MySQL)
- Scan NFC/QR di web adalah **simulasi** — implementasi nyata memerlukan hardware NFC reader dan library kamera
- Integrasi peta untuk lacak kartu memerlukan **Google Maps API** atau **Leaflet.js**
- Backend API sudah tersedia di `/api/` untuk integrasi dengan **React Native** mobile app
