-- ============================================================
-- MIGRASI: Tambah kolom mili_id untuk MiLi Card integration
-- Jalankan SQL ini di MySQL setelah update kode
-- ============================================================

ALTER TABLE anggota ADD COLUMN mili_id VARCHAR(100) UNIQUE NULL AFTER qr_data;
CREATE INDEX idx_anggota_mili_id ON anggota(mili_id);

-- Untuk mendaftarkan MiLi Card kamu:
-- UPDATE anggota SET mili_id = 'FZDc3ImYoVWNm5kNwUTT5IjM' WHERE kartu_id = 'KP-2025-001';
