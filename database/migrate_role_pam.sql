-- ============================================================
-- MIGRATION: Tambah role 'pam' (Pembina) di tabel users
-- ============================================================
-- Pam = Pembina, role baru yang fokus monitoring anggota
-- TANPA akses ke: Manajemen Produk, Kategori, Kasir, Top Up,
-- Riwayat Penjualan, Riwayat Saldo, Semua Transaksi
-- DENGAN akses ke: Dashboard, Data Anggota, Scan, Lacak Kartu,
-- Riwayat Lokasi, Cetak Kartu
-- ============================================================

USE `kartu_pintar`;

-- 1. Ubah enum kolom role: tambah 'pam'
ALTER TABLE `users`
  MODIFY COLUMN `role` ENUM('admin','user','operator_kantin','pam')
  CHARACTER SET latin1 COLLATE latin1_swedish_ci NOT NULL;

-- 2. (Opsional) Buat user pam contoh — password: pam123
-- Hapus baris di bawah ini jika tidak diperlukan.
-- Password hash di bawah = pbkdf2:sha256 dari 'pam123'
INSERT INTO `users`
  (`username`, `password_hash`, `role`, `nama`, `email`, `is_active`, `anggota_id`, `created_at`, `updated_at`)
VALUES
  ('pam1',
   'pbkdf2:sha256:1000000$vMt7pRGd0hvlaSBQ$ebe41ef28551aa01a5fc36726299f6bfc0cc00afdc7144f299faf800861b7d62',
   'pam',
   'Pembina Poltekkad',
   'pam@poltekkad.ac.id',
   1,
   NULL,
   NOW(),
   NOW())
ON DUPLICATE KEY UPDATE `role` = 'pam';

-- Catatan: hash di atas adalah hash dari password yang sama dengan user
-- admin/user1/kantin1 di SQL dump. Setelah login, ganti password
-- via menu Profil atau API change-password.

-- ============================================================
-- VERIFIKASI
-- ============================================================
-- Cek struktur:
--   SHOW COLUMNS FROM `users` LIKE 'role';
-- Cek data pam:
--   SELECT id, username, role, nama, is_active FROM `users` WHERE role = 'pam';
