-- ============================================================
-- Migration: Tambah kolom Riwayat Hidup ke tabel anggota
-- Run: mysql -u root -p kartu_pintar < database/migrate_riwayat_hidup.sql
-- ============================================================

USE kartu_pintar;

-- Kolom identitas tambahan
ALTER TABLE anggota
    ADD COLUMN IF NOT EXISTS korp VARCHAR(20) NULL AFTER golongan_darah,
    ADD COLUMN IF NOT EXISTS suku_bangsa VARCHAR(50) NULL AFTER korp,
    ADD COLUMN IF NOT EXISTS sumber_ba VARCHAR(50) NULL AFTER suku_bangsa,
    ADD COLUMN IF NOT EXISTS tmt_tni DATE NULL AFTER sumber_ba,
    ADD COLUMN IF NOT EXISTS tmt_jabatan DATE NULL AFTER tmt_tni;

-- Kolom keluarga
ALTER TABLE anggota
    ADD COLUMN IF NOT EXISTS status_pernikahan VARCHAR(20) NULL AFTER no_telepon,
    ADD COLUMN IF NOT EXISTS nama_pasangan VARCHAR(100) NULL AFTER status_pernikahan,
    ADD COLUMN IF NOT EXISTS jml_anak INT DEFAULT 0 AFTER nama_pasangan,
    ADD COLUMN IF NOT EXISTS alamat_tinggal TEXT NULL AFTER jml_anak,
    ADD COLUMN IF NOT EXISTS nama_ayah VARCHAR(100) NULL AFTER alamat_tinggal,
    ADD COLUMN IF NOT EXISTS nama_ibu VARCHAR(100) NULL AFTER nama_ayah,
    ADD COLUMN IF NOT EXISTS alamat_orang_tua TEXT NULL AFTER nama_ibu;

-- Kolom riwayat JSON
ALTER TABLE anggota
    ADD COLUMN IF NOT EXISTS riwayat_pendidikan_umum TEXT NULL AFTER alamat_orang_tua,
    ADD COLUMN IF NOT EXISTS riwayat_pendidikan_militer TEXT NULL AFTER riwayat_pendidikan_umum,
    ADD COLUMN IF NOT EXISTS riwayat_penugasan TEXT NULL AFTER riwayat_pendidikan_militer,
    ADD COLUMN IF NOT EXISTS riwayat_kepangkatan TEXT NULL AFTER riwayat_penugasan,
    ADD COLUMN IF NOT EXISTS riwayat_jabatan TEXT NULL AFTER riwayat_kepangkatan,
    ADD COLUMN IF NOT EXISTS riwayat_anak TEXT NULL AFTER riwayat_jabatan,
    ADD COLUMN IF NOT EXISTS kemampuan_bahasa TEXT NULL AFTER riwayat_anak,
    ADD COLUMN IF NOT EXISTS tanda_jasa TEXT NULL AFTER kemampuan_bahasa,
    ADD COLUMN IF NOT EXISTS penugasan_luar_negeri TEXT NULL AFTER tanda_jasa,
    ADD COLUMN IF NOT EXISTS riwayat_prestasi TEXT NULL AFTER penugasan_luar_negeri;

-- Verifikasi kolom
DESCRIBE anggota;
