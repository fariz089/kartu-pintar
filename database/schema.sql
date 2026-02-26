-- ============================================================
-- Kartu Pintar - MySQL Database Schema
-- TNI Angkatan Darat - Poltekkad
-- ============================================================
-- Run this FIRST before starting the app:
--   mysql -u root -p < database/schema.sql
-- OR use: python manage.py init-db (recommended)
-- ============================================================

-- Create database
CREATE DATABASE IF NOT EXISTS kartu_pintar
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE kartu_pintar;

-- ============================================================
-- TABLE: users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'user', 'operator_kantin') NOT NULL DEFAULT 'user',
    nama VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    anggota_id INT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_anggota_id (anggota_id)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: anggota (TNI members / card holders)
-- ============================================================
CREATE TABLE IF NOT EXISTS anggota (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kartu_id VARCHAR(20) NOT NULL UNIQUE,
    nrp VARCHAR(20) NOT NULL UNIQUE,
    nama VARCHAR(100) NOT NULL,
    pangkat VARCHAR(50) NOT NULL,
    satuan VARCHAR(100) NOT NULL DEFAULT 'Poltekkad',
    jabatan VARCHAR(100),
    jurusan VARCHAR(100),
    tempat_lahir VARCHAR(100),
    tanggal_lahir DATE,
    golongan_darah ENUM('A', 'B', 'AB', 'O'),
    agama VARCHAR(20),
    alamat TEXT,
    no_telepon VARCHAR(20),
    foto VARCHAR(255) DEFAULT '/static/img/avatar-default.svg',

    -- NFC & QR
    nfc_uid VARCHAR(50) UNIQUE,
    qr_data VARCHAR(50) UNIQUE,

    -- E-Wallet
    saldo BIGINT NOT NULL DEFAULT 0,

    -- Card status & tracking
    status_kartu ENUM('Aktif', 'Nonaktif', 'Hilang', 'Diblokir') NOT NULL DEFAULT 'Aktif',
    lokasi_lat FLOAT,
    lokasi_lng FLOAT,
    lokasi_nama VARCHAR(200),
    lokasi_waktu DATETIME,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_kartu_id (kartu_id),
    INDEX idx_nrp (nrp),
    INDEX idx_nfc_uid (nfc_uid),
    INDEX idx_qr_data (qr_data),
    INDEX idx_status (status_kartu)
) ENGINE=InnoDB;

-- Foreign key for users -> anggota
ALTER TABLE users ADD CONSTRAINT fk_users_anggota
    FOREIGN KEY (anggota_id) REFERENCES anggota(id) ON DELETE SET NULL;

-- ============================================================
-- TABLE: transaksi (payment & topup transactions)
-- ============================================================
CREATE TABLE IF NOT EXISTS transaksi (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trx_id VARCHAR(30) NOT NULL UNIQUE,
    anggota_id INT NOT NULL,
    jenis ENUM('Pembelian', 'Top Up') NOT NULL,
    keterangan VARCHAR(200),
    nominal BIGINT NOT NULL,
    saldo_sebelum BIGINT NOT NULL,
    saldo_sesudah BIGINT NOT NULL,
    status ENUM('Berhasil', 'Gagal', 'Pending') NOT NULL DEFAULT 'Pending',
    metode VARCHAR(20) DEFAULT 'NFC',
    operator_id INT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_trx_id (trx_id),
    INDEX idx_anggota_id (anggota_id),
    INDEX idx_created_at (created_at),
    INDEX idx_jenis (jenis),

    CONSTRAINT fk_transaksi_anggota FOREIGN KEY (anggota_id)
        REFERENCES anggota(id) ON DELETE CASCADE,
    CONSTRAINT fk_transaksi_operator FOREIGN KEY (operator_id)
        REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: lokasi_history (card location tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS lokasi_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    anggota_id INT NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    lokasi_nama VARCHAR(200),
    sumber VARCHAR(20) DEFAULT 'NFC',
    waktu DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_anggota_id (anggota_id),
    INDEX idx_waktu (waktu),

    CONSTRAINT fk_lokasi_anggota FOREIGN KEY (anggota_id)
        REFERENCES anggota(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: menu_kantin (canteen menu items)
-- ============================================================
CREATE TABLE IF NOT EXISTS menu_kantin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama VARCHAR(100) NOT NULL,
    kategori ENUM('Makanan', 'Minuman', 'Snack') NOT NULL,
    harga BIGINT NOT NULL,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_kategori (kategori),
    INDEX idx_available (is_available)
) ENGINE=InnoDB;
