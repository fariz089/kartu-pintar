"""
Kartu Pintar - Database Seeder
Creates initial data for development/testing
"""
from models import db, User, Anggota, Transaksi, LokasiHistory, MenuKantin
from datetime import datetime, date, timedelta
import random


def seed_database():
    """Seed all tables with initial data"""
    print("🌱 Seeding database...")

    # ========================
    # MENU KANTIN
    # ========================
    menu_items = [
        MenuKantin(nama='Nasi Goreng', kategori='Makanan', harga=15000),
        MenuKantin(nama='Mie Goreng', kategori='Makanan', harga=13000),
        MenuKantin(nama='Nasi Padang', kategori='Makanan', harga=20000),
        MenuKantin(nama='Soto Ayam', kategori='Makanan', harga=15000),
        MenuKantin(nama='Ayam Geprek', kategori='Makanan', harga=18000),
        MenuKantin(nama='Bakso', kategori='Makanan', harga=12000),
        MenuKantin(nama='Nasi Uduk', kategori='Makanan', harga=10000),
        MenuKantin(nama='Gado-gado', kategori='Makanan', harga=12000),
        MenuKantin(nama='Es Teh Manis', kategori='Minuman', harga=5000),
        MenuKantin(nama='Es Jeruk', kategori='Minuman', harga=7000),
        MenuKantin(nama='Kopi', kategori='Minuman', harga=8000),
        MenuKantin(nama='Air Mineral', kategori='Minuman', harga=3000),
        MenuKantin(nama='Jus Alpukat', kategori='Minuman', harga=12000),
        MenuKantin(nama='Susu Coklat', kategori='Minuman', harga=8000),
        MenuKantin(nama='Gorengan', kategori='Snack', harga=5000),
        MenuKantin(nama='Roti Bakar', kategori='Snack', harga=10000),
        MenuKantin(nama='Pisang Goreng', kategori='Snack', harga=6000),
        MenuKantin(nama='Kerupuk', kategori='Snack', harga=3000),
    ]
    db.session.add_all(menu_items)
    db.session.flush()
    print(f"  ✅ {len(menu_items)} menu kantin")

    # ========================
    # ANGGOTA
    # ========================
    anggota_list = [
        Anggota(
            kartu_id='KP-2025-001', nrp='21250001',
            nama='Serda Budi Santoso', pangkat='Sersan Dua',
            satuan='Poltekkad', jabatan='Taruna Tingkat III',
            jurusan='Teknik Elektronika',
            tempat_lahir='Bandung', tanggal_lahir=date(2002, 3, 15),
            golongan_darah='O', agama='Islam',
            alamat='Jl. Gatot Subroto No.96, Bandung',
            no_telepon='081234567890',
            nfc_uid='A1B2C3D4', qr_data='KP-2025-001',
            saldo=750000, status_kartu='Aktif',
            lokasi_lat=-6.8927, lokasi_lng=107.6100,
            lokasi_nama='Kantin Poltekkad',
            lokasi_waktu=datetime(2025, 2, 26, 8, 30, 0),
        ),
        Anggota(
            kartu_id='KP-2025-002', nrp='21250002',
            nama='Praka Andi Wijaya', pangkat='Prajurit Kepala',
            satuan='Poltekkad', jabatan='Taruna Tingkat II',
            jurusan='Teknik Mesin',
            tempat_lahir='Surabaya', tanggal_lahir=date(2003, 7, 22),
            golongan_darah='A', agama='Islam',
            alamat='Jl. Pahlawan No.12, Surabaya',
            no_telepon='081234567891',
            nfc_uid='E5F6G7H8', qr_data='KP-2025-002',
            saldo=520000, status_kartu='Aktif',
            lokasi_lat=-6.8930, lokasi_lng=107.6105,
            lokasi_nama='Gedung Utama Poltekkad',
            lokasi_waktu=datetime(2025, 2, 26, 9, 15, 0),
        ),
        Anggota(
            kartu_id='KP-2025-003', nrp='21250003',
            nama='Pratu Rizki Firmansyah', pangkat='Prajurit Satu',
            satuan='Poltekkad', jabatan='Taruna Tingkat I',
            jurusan='Teknik Informatika',
            tempat_lahir='Jakarta', tanggal_lahir=date(2004, 1, 10),
            golongan_darah='B', agama='Kristen',
            alamat='Jl. Merdeka No.45, Jakarta Selatan',
            no_telepon='081234567892',
            nfc_uid='I9J0K1L2', qr_data='KP-2025-003',
            saldo=310000, status_kartu='Aktif',
            lokasi_lat=-6.8925, lokasi_lng=107.6098,
            lokasi_nama='Asrama Poltekkad',
            lokasi_waktu=datetime(2025, 2, 26, 7, 45, 0),
        ),
        Anggota(
            kartu_id='KP-2025-004', nrp='21250004',
            nama='Sertu Dewi Kartika', pangkat='Sersan Satu',
            satuan='Poltekkad', jabatan='Staff Pengajar',
            jurusan='Teknik Elektronika',
            tempat_lahir='Yogyakarta', tanggal_lahir=date(2000, 9, 5),
            golongan_darah='AB', agama='Islam',
            alamat='Jl. Malioboro No.78, Yogyakarta',
            no_telepon='081234567893',
            nfc_uid='M3N4O5P6', qr_data='KP-2025-004',
            saldo=980000, status_kartu='Aktif',
            lokasi_lat=-6.8935, lokasi_lng=107.6110,
            lokasi_nama='Ruang Kelas Poltekkad',
            lokasi_waktu=datetime(2025, 2, 26, 10, 0, 0),
        ),
        Anggota(
            kartu_id='KP-2025-005', nrp='21250005',
            nama='Kopda Agus Prasetyo', pangkat='Kopral Dua',
            satuan='Poltekkad', jabatan='Taruna Tingkat II',
            jurusan='Teknik Mesin',
            tempat_lahir='Semarang', tanggal_lahir=date(2003, 11, 28),
            golongan_darah='O', agama='Islam',
            alamat='Jl. Pemuda No.33, Semarang',
            no_telepon='081234567894',
            nfc_uid='Q7R8S9T0', qr_data='KP-2025-005',
            saldo=150000, status_kartu='Hilang',
            lokasi_lat=-6.8940, lokasi_lng=107.6095,
            lokasi_nama='Lapangan Upacara Poltekkad',
            lokasi_waktu=datetime(2025, 2, 25, 16, 30, 0),
        ),
    ]
    db.session.add_all(anggota_list)
    db.session.flush()
    print(f"  ✅ {len(anggota_list)} anggota")

    # ========================
    # USERS
    # ========================
    admin = User(
        username='admin', role='admin',
        nama='Administrator Poltekkad',
        email='admin@poltekkad.ac.id', is_active=True,
    )
    admin.set_password('admin123')

    user1 = User(
        username='user1', role='user',
        nama='Serda Budi Santoso',
        email='budi@poltekkad.ac.id', is_active=True,
        anggota_id=anggota_list[0].id,
    )
    user1.set_password('user123')

    operator = User(
        username='kantin1', role='operator_kantin',
        nama='Operator Kantin Poltekkad',
        email='kantin@poltekkad.ac.id', is_active=True,
    )
    operator.set_password('kantin123')

    db.session.add_all([admin, user1, operator])
    db.session.flush()
    print("  ✅ 3 users (admin, user1, kantin1)")

    # ========================
    # TRANSAKSI
    # ========================
    base_time = datetime(2025, 2, 26, 7, 0, 0)
    trx_data = [
        Transaksi(
            trx_id='TRX-20250226-001', anggota_id=anggota_list[0].id,
            jenis='Top Up', keterangan='Pengisian Saldo',
            nominal=500000, saldo_sebelum=250000, saldo_sesudah=750000,
            status='Berhasil', metode='Manual', operator_id=admin.id,
            created_at=base_time - timedelta(days=1),
        ),
        Transaksi(
            trx_id='TRX-20250226-002', anggota_id=anggota_list[0].id,
            jenis='Pembelian', keterangan='Makan Siang - Nasi Goreng',
            nominal=15000, saldo_sebelum=765000, saldo_sesudah=750000,
            status='Berhasil', metode='NFC',
            created_at=base_time + timedelta(hours=5, minutes=30),
        ),
        Transaksi(
            trx_id='TRX-20250226-003', anggota_id=anggota_list[1].id,
            jenis='Pembelian', keterangan='Minuman - Es Teh Manis',
            nominal=5000, saldo_sebelum=525000, saldo_sesudah=520000,
            status='Berhasil', metode='NFC',
            created_at=base_time + timedelta(hours=3, minutes=15),
        ),
        Transaksi(
            trx_id='TRX-20250226-004', anggota_id=anggota_list[2].id,
            jenis='Pembelian', keterangan='Snack - Gorengan',
            nominal=5000, saldo_sebelum=315000, saldo_sesudah=310000,
            status='Berhasil', metode='NFC',
            created_at=base_time + timedelta(hours=2, minutes=45),
        ),
        Transaksi(
            trx_id='TRX-20250226-005', anggota_id=anggota_list[3].id,
            jenis='Top Up', keterangan='Pengisian Saldo',
            nominal=300000, saldo_sebelum=680000, saldo_sesudah=980000,
            status='Berhasil', metode='Manual', operator_id=admin.id,
            created_at=base_time - timedelta(days=2),
        ),
        Transaksi(
            trx_id='TRX-20250226-006', anggota_id=anggota_list[4].id,
            jenis='Pembelian', keterangan='Makan Pagi - Nasi Uduk',
            nominal=10000, saldo_sebelum=160000, saldo_sesudah=150000,
            status='Gagal', metode='NFC',
            created_at=base_time,
        ),
    ]
    db.session.add_all(trx_data)
    db.session.flush()
    print(f"  ✅ {len(trx_data)} transaksi")

    # ========================
    # LOKASI HISTORY
    # ========================
    lokasi_data = []
    lokasi_spots = [
        (-6.8927, 107.6100, 'Kantin Poltekkad'),
        (-6.8930, 107.6105, 'Gedung Utama Poltekkad'),
        (-6.8925, 107.6098, 'Asrama Poltekkad'),
        (-6.8935, 107.6110, 'Ruang Kelas Poltekkad'),
        (-6.8940, 107.6095, 'Lapangan Upacara Poltekkad'),
        (-6.8928, 107.6102, 'Perpustakaan Poltekkad'),
        (-6.8932, 107.6108, 'Lab Komputer Poltekkad'),
    ]

    for i, anggota in enumerate(anggota_list):
        for j in range(3):
            spot = random.choice(lokasi_spots)
            lokasi_data.append(LokasiHistory(
                anggota_id=anggota.id,
                latitude=spot[0],
                longitude=spot[1],
                lokasi_nama=spot[2],
                sumber='NFC',
                waktu=base_time - timedelta(hours=j * 3 + i),
            ))

    db.session.add_all(lokasi_data)
    print(f"  ✅ {len(lokasi_data)} lokasi history")

    # ========================
    # COMMIT
    # ========================
    db.session.commit()
    print("\n✅ Database seeding complete!")
    print("=" * 40)
    print("Login credentials:")
    print("  Admin    : admin / admin123")
    print("  User     : user1 / user123")
    print("  Kantin   : kantin1 / kantin123")
    print("=" * 40)
