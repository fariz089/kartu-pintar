# Perubahan Login & 2FA — Smart Card

Tanggal: 2026-05-20

## Ringkasan perubahan

### Web (`kartu-pintar/`)

1. **Demo credentials dihapus** dari halaman login.
2. **Logo PNG dijadikan transparan** (background putih dihapus dari `static/img/logo.png`).
3. **Toggle show/hide password** ditambahkan di halaman login.
4. **2FA / TOTP wajib untuk semua user** (Google Authenticator, Microsoft Authenticator, Authy, dll).

### Mobile (`kartu-pintar-mobile/`)

1. **Logo PNG dijadikan transparan** (`assets/logo.png`).
2. **Show/hide password sudah ada sebelumnya** — tidak ada perubahan.
3. **2FA / TOTP wajib** — alur login baru: password → setup TOTP (pertama kali) atau verify TOTP (login berikutnya).

## Cara kerja 2FA

1. User pertama kali login dengan username+password yang benar.
2. Karena `totp_enabled = false`, user diarahkan ke halaman **Setup 2FA**:
   - Sebuah QR code ditampilkan + secret manual.
   - User scan dengan aplikasi Authenticator di HP.
   - User masukkan 6 digit kode dari aplikasi.
   - Jika benar: `totp_enabled = true` dan 8 **backup codes** ditampilkan (sekali saja).
3. Login berikutnya: password → langsung halaman **Verify 2FA** → masukkan kode 6 digit (atau backup code) → masuk dashboard.

### Recovery jika user kehilangan HP

- User memakai salah satu **backup code** (8 kode, format `XXXX-XXXX`, sekali pakai).
- Atau admin reset 2FA-nya via CLI:
  ```bash
  python manage.py reset-totp
  ```
  Setelah reset, user akan setup ulang QR + dapat backup codes baru pada login berikutnya.

## Langkah deploy / migrasi

### 1. Update kode (replace folder)

Replace folder `kartu-pintar/` dan `kartu-pintar-mobile/` dengan isi zip yang baru.

### 2. Database migration (web — backend)

Jalankan sekali di server:

```bash
cd kartu-pintar/
pip install -r requirements.txt   # tidak ada library baru, hanya pastikan segno terinstall
python manage.py migrate-totp
```

`migrate-totp` adalah idempotent (aman dijalankan berulang) dan akan menambah 3 kolom ke tabel `users`:

- `totp_secret VARCHAR(64) NULL`
- `totp_enabled TINYINT(1) NOT NULL DEFAULT 0`
- `totp_backup_codes TEXT NULL`

### 3. Restart Flask

```bash
# misal pakai gunicorn/systemd:
systemctl restart kartu-pintar
# atau dev:
python app.py
```

### 4. Mobile (Expo)

Tidak ada library baru ditambahkan, jadi tinggal:

```bash
cd kartu-pintar-mobile/
npx expo start --clear        # atau eas build sesuai biasa
```

Build APK baru lalu distribusi seperti biasa.

## File yang berubah (ringkas)

### Web
- `models.py` — tambah field TOTP + helper
- `app.py` — login flow, TOTP routes (web + API), import totp_utils
- `manage.py` — perintah `migrate-totp` & `reset-totp`
- `totp_utils.py` — **BARU**, modul TOTP/QR/backup-codes
- `templates/auth/login.html` — hapus demo credentials, tambah eye toggle
- `templates/auth/totp_setup.html` — **BARU**
- `templates/auth/totp_verify.html` — **BARU**
- `templates/auth/totp_backup_codes.html` — **BARU**
- `static/css/style.css` — hapus CSS demo, tambah CSS password toggle & TOTP
- `static/img/logo.png` — background putih dihapus

### Mobile
- `src/services/api.js` — `authAPI.login` tidak lagi simpan token; tambah `totpSetup`, `totpVerify`
- `src/screens/LoginScreen.js` — routing ke TotpSetup / TotpVerify
- `src/screens/TotpSetupScreen.js` — **BARU**
- `src/screens/TotpVerifyScreen.js` — **BARU**
- `src/navigation/AppNavigation.js` — register route TotpSetup & TotpVerify
- `assets/logo.png` — background putih dihapus

## Endpoint API baru

- `POST /api/auth/login` — sekarang return `{ success, requires_totp, totp_setup_required, pending_token, username, nama }` (tidak lagi langsung `token`).
- `GET /api/auth/totp/setup` — Header `Authorization: Bearer <pending_token>`. Returns `{ setup_token, secret, otpauth_uri, qr_png }`.
- `POST /api/auth/totp/verify` — Header `Authorization: Bearer <setup_token | pending_token>`. Body `{ code }` atau `{ backup_code }`. Returns full JWT (`{ token, data, backup_codes? }`).

## Catatan keamanan

- Backup codes disimpan **hashed** (pbkdf2-sha256) di DB, plaintext hanya ditampilkan sekali saat setup.
- Secret TOTP disimpan plain di DB (standar TOTP). Bila DB bocor, hashed-password tetap aman tapi TOTP rentan — pertimbangkan enkripsi kolom `totp_secret` di lapis aplikasi bila diperlukan.
- Toleransi clock-skew TOTP = ±30 detik (1 window). Bila user sering gagal verifikasi, mereka perlu sinkronkan jam HP.
- Window TOTP = 30 detik, 6 digit, SHA1 (kompatibel default Google Authenticator).
