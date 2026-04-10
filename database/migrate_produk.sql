-- ============================================================
-- MIGRATION: Add product management tables
-- Run: mysql -u root -p kartu_pintar < database/migrate_produk.sql
-- ============================================================

USE kartu_pintar;

-- ============================================================
-- TABLE: kategori_produk (product categories)
-- ============================================================
CREATE TABLE IF NOT EXISTS kategori_produk (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama VARCHAR(50) NOT NULL UNIQUE,
    icon VARCHAR(50) DEFAULT 'bi-box',
    urutan INT DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_urutan (urutan),
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: produk (products for supermarket-style canteen)
-- ============================================================
CREATE TABLE IF NOT EXISTS produk (
    id INT AUTO_INCREMENT PRIMARY KEY,
    kode VARCHAR(20) NOT NULL UNIQUE,
    nama VARCHAR(100) NOT NULL,
    kategori_id INT NOT NULL,
    harga BIGINT NOT NULL,
    stok INT NOT NULL DEFAULT 0,
    stok_minimum INT DEFAULT 5,
    satuan VARCHAR(20) DEFAULT 'pcs',
    gambar VARCHAR(255) DEFAULT '/static/img/product-default.svg',
    deskripsi TEXT,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_kode (kode),
    INDEX idx_kategori (kategori_id),
    INDEX idx_available (is_available),
    INDEX idx_stok (stok),

    CONSTRAINT fk_produk_kategori FOREIGN KEY (kategori_id)
        REFERENCES kategori_produk(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- TABLE: transaksi_item (cart items in a transaction)
-- ============================================================
CREATE TABLE IF NOT EXISTS transaksi_item (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaksi_id INT NOT NULL,
    produk_id INT NOT NULL,
    nama_produk VARCHAR(100) NOT NULL,
    harga_satuan BIGINT NOT NULL,
    jumlah INT NOT NULL DEFAULT 1,
    subtotal BIGINT NOT NULL,

    INDEX idx_transaksi (transaksi_id),
    INDEX idx_produk (produk_id),

    CONSTRAINT fk_item_transaksi FOREIGN KEY (transaksi_id)
        REFERENCES transaksi(id) ON DELETE CASCADE,
    CONSTRAINT fk_item_produk FOREIGN KEY (produk_id)
        REFERENCES produk(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- INSERT DEFAULT CATEGORIES
-- ============================================================
INSERT IGNORE INTO kategori_produk (nama, icon, urutan) VALUES
    ('Makanan', 'bi-egg-fried', 1),
    ('Minuman', 'bi-cup-straw', 2),
    ('Snack', 'bi-cookie', 3),
    ('Sembako', 'bi-basket', 4),
    ('Alat Tulis', 'bi-pencil', 5),
    ('Lainnya', 'bi-box', 99);

-- ============================================================
-- INSERT SAMPLE PRODUCTS
-- ============================================================
INSERT IGNORE INTO produk (kode, nama, kategori_id, harga, stok, satuan) VALUES
    ('MKN001', 'Nasi Goreng', 1, 15000, 50, 'porsi'),
    ('MKN002', 'Mie Goreng', 1, 12000, 50, 'porsi'),
    ('MKN003', 'Nasi Ayam Geprek', 1, 18000, 30, 'porsi'),
    ('MKN004', 'Nasi Rendang', 1, 20000, 25, 'porsi'),
    ('MKN005', 'Bakso', 1, 15000, 40, 'mangkok'),
    ('MNM001', 'Es Teh Manis', 2, 5000, 100, 'gelas'),
    ('MNM002', 'Es Jeruk', 2, 7000, 80, 'gelas'),
    ('MNM003', 'Kopi Hitam', 2, 5000, 60, 'gelas'),
    ('MNM004', 'Air Mineral', 2, 4000, 100, 'botol'),
    ('MNM005', 'Teh Botol', 2, 6000, 50, 'botol'),
    ('SNK001', 'Gorengan', 3, 2000, 100, 'pcs'),
    ('SNK002', 'Keripik', 3, 5000, 50, 'bungkus'),
    ('SNK003', 'Roti Bakar', 3, 8000, 30, 'pcs'),
    ('SNK004', 'Pisang Goreng', 3, 3000, 50, 'pcs'),
    ('SMB001', 'Indomie Goreng', 4, 4000, 100, 'bungkus'),
    ('SMB002', 'Indomie Kuah', 4, 4000, 100, 'bungkus'),
    ('ATK001', 'Pulpen', 5, 3000, 50, 'pcs'),
    ('ATK002', 'Buku Tulis', 5, 5000, 30, 'pcs');

SELECT 'Migration completed! Products and categories created.' AS status;
