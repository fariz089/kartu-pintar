"""
Kartu Pintar - Database Models
SQLAlchemy ORM Models for MySQL
"""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
import json

db = SQLAlchemy()


# Export all models at module level
__all__ = ['db', 'User', 'Anggota', 'Transaksi', 'TransaksiItem', 
           'LokasiHistory', 'MenuKantin', 'KategoriProduk', 'Produk', 'FindMyTracker']


def generate_id(prefix='KP'):
    """Generate unique ID with prefix"""
    year = datetime.now().strftime('%Y')
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{year}-{short_uuid}"


class User(db.Model):
    """User accounts for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'user', 'operator_kantin'), default='user', nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    anggota_id = db.Column(db.Integer, db.ForeignKey('anggota.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationship
    anggota = db.relationship('Anggota', backref=db.backref('user_account', uselist=False), foreign_keys=[anggota_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'nama': self.nama,
            'email': self.email,
            'is_active': self.is_active,
            'anggota_id': self.anggota_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }


class Anggota(db.Model):
    """Data anggota TNI - Kartu Pintar holder"""
    __tablename__ = 'anggota'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kartu_id = db.Column(db.String(20), unique=True, nullable=False, index=True)  # e.g. KP-2025-001
    nrp = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nama = db.Column(db.String(100), nullable=False)
    pangkat = db.Column(db.String(50), nullable=False)
    satuan = db.Column(db.String(100), default='Poltekad', nullable=False)
    jabatan = db.Column(db.String(100), nullable=True)
    jurusan = db.Column(db.String(100), nullable=True)
    tempat_lahir = db.Column(db.String(100), nullable=True)
    tanggal_lahir = db.Column(db.Date, nullable=True)
    golongan_darah = db.Column(db.Enum('A', 'B', 'AB', 'O'), nullable=True)
    agama = db.Column(db.String(20), nullable=True)
    alamat = db.Column(db.Text, nullable=True)
    no_telepon = db.Column(db.String(20), nullable=True)
    foto = db.Column(db.String(255), default='/static/img/avatar-default.svg')

    # NFC & QR
    nfc_uid = db.Column(db.String(50), unique=True, nullable=True, index=True)
    qr_data = db.Column(db.String(50), unique=True, nullable=True, index=True)

    # MiLi Card ID (extracted from https://micard.mymili.com/info/{mili_id})
    mili_id = db.Column(db.String(100), unique=True, nullable=True, index=True)

    # Saldo (e-wallet)
    saldo = db.Column(db.BigInteger, default=0, nullable=False)

    # Kartu status & tracking
    status_kartu = db.Column(db.Enum('Aktif', 'Nonaktif', 'Hilang', 'Diblokir'), default='Aktif', nullable=False)
    lokasi_lat = db.Column(db.Float, nullable=True)
    lokasi_lng = db.Column(db.Float, nullable=True)
    lokasi_nama = db.Column(db.String(200), nullable=True)
    lokasi_waktu = db.Column(db.DateTime, nullable=True)

    # ============================================================
    # RIWAYAT HIDUP FIELDS
    # ============================================================
    korp = db.Column(db.String(20), nullable=True)         # INF, CAV, ARH, dll
    suku_bangsa = db.Column(db.String(50), nullable=True)
    sumber_ba = db.Column(db.String(50), nullable=True)    # SECABA PK, AKMIL, dll
    tmt_tni = db.Column(db.Date, nullable=True)            # Tanggal Mulai Tugas TNI
    tmt_jabatan = db.Column(db.Date, nullable=True)        # TMT jabatan saat ini

    # Keluarga
    status_pernikahan = db.Column(db.String(20), nullable=True)
    nama_pasangan = db.Column(db.String(100), nullable=True)
    jml_anak = db.Column(db.Integer, default=0)
    alamat_tinggal = db.Column(db.Text, nullable=True)
    nama_ayah = db.Column(db.String(100), nullable=True)
    nama_ibu = db.Column(db.String(100), nullable=True)
    alamat_orang_tua = db.Column(db.Text, nullable=True)

    # Riwayat dalam format JSON (TEXT di MySQL)
    riwayat_pendidikan_umum = db.Column(db.Text, nullable=True)    # [{no, jenis, tahun, nama, prestasi}]
    riwayat_pendidikan_militer = db.Column(db.Text, nullable=True)  # [{no, jenis, tahun, prestasi}]
    riwayat_penugasan = db.Column(db.Text, nullable=True)           # [{no, nama_operasi, tahun, prestasi}]
    riwayat_kepangkatan = db.Column(db.Text, nullable=True)         # [{no, pangkat, tmt, nomor_kep}]
    riwayat_jabatan = db.Column(db.Text, nullable=True)             # [{no, jabatan, tmt}]
    riwayat_anak = db.Column(db.Text, nullable=True)                # [{nama, tgl_lahir}]
    kemampuan_bahasa = db.Column(db.Text, nullable=True)            # [{bahasa, tingkat}]
    tanda_jasa = db.Column(db.Text, nullable=True)                  # [{nama}]
    penugasan_luar_negeri = db.Column(db.Text, nullable=True)       # [{macam_tugas, tahun, negara, prestasi}]
    riwayat_prestasi = db.Column(db.Text, nullable=True)            # [{kegiatan, tahun, tempat, deskripsi, kep}]

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    transaksi = db.relationship('Transaksi', backref='anggota', lazy='dynamic', order_by='Transaksi.created_at.desc()')
    lokasi_history = db.relationship('LokasiHistory', backref='anggota', lazy='dynamic', order_by='LokasiHistory.waktu.desc()')

    def _get_json(self, field):
        """Helper to safely parse JSON text field"""
        val = getattr(self, field)
        if not val:
            return []
        try:
            return json.loads(val)
        except Exception:
            return []

    def _set_json(self, field, value):
        """Helper to safely set JSON text field"""
        setattr(self, field, json.dumps(value, ensure_ascii=False) if value else None)

    def get_riwayat_hidup(self):
        """Returns complete riwayat hidup dict"""
        return {
            'korp': self.korp,
            'suku_bangsa': self.suku_bangsa,
            'sumber_ba': self.sumber_ba,
            'tmt_tni': self.tmt_tni.strftime('%Y-%m-%d') if self.tmt_tni else None,
            'tmt_jabatan': self.tmt_jabatan.strftime('%Y-%m-%d') if self.tmt_jabatan else None,
            'status_pernikahan': self.status_pernikahan,
            'nama_pasangan': self.nama_pasangan,
            'jml_anak': self.jml_anak or 0,
            'alamat_tinggal': self.alamat_tinggal,
            'nama_ayah': self.nama_ayah,
            'nama_ibu': self.nama_ibu,
            'alamat_orang_tua': self.alamat_orang_tua,
            'riwayat_pendidikan_umum': self._get_json('riwayat_pendidikan_umum'),
            'riwayat_pendidikan_militer': self._get_json('riwayat_pendidikan_militer'),
            'riwayat_penugasan': self._get_json('riwayat_penugasan'),
            'riwayat_kepangkatan': self._get_json('riwayat_kepangkatan'),
            'riwayat_jabatan': self._get_json('riwayat_jabatan'),
            'riwayat_anak': self._get_json('riwayat_anak'),
            'kemampuan_bahasa': self._get_json('kemampuan_bahasa'),
            'tanda_jasa': self._get_json('tanda_jasa'),
            'penugasan_luar_negeri': self._get_json('penugasan_luar_negeri'),
            'riwayat_prestasi': self._get_json('riwayat_prestasi'),
        }

    def to_dict(self, include_saldo=True):
        data = {
            'id': self.id,
            'kartu_id': self.kartu_id,
            'nrp': self.nrp,
            'nama': self.nama,
            'pangkat': self.pangkat,
            'satuan': self.satuan,
            'jabatan': self.jabatan,
            'jurusan': self.jurusan,
            'tempat_lahir': self.tempat_lahir,
            'tanggal_lahir': self.tanggal_lahir.strftime('%Y-%m-%d') if self.tanggal_lahir else None,
            'golongan_darah': self.golongan_darah,
            'agama': self.agama,
            'alamat': self.alamat,
            'no_telepon': self.no_telepon,
            'foto': self.foto,
            'nfc_uid': self.nfc_uid,
            'qr_data': self.qr_data,
            'mili_id': self.mili_id,
            'status_kartu': self.status_kartu,
            'lokasi_terakhir': {
                'lat': self.lokasi_lat,
                'lng': self.lokasi_lng,
                'lokasi': self.lokasi_nama,
                'waktu': self.lokasi_waktu.strftime('%Y-%m-%d %H:%M:%S') if self.lokasi_waktu else None,
            },
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        if include_saldo:
            data['saldo'] = self.saldo
        return data

    def to_identitas_dict(self):
        """Reduced dict for identity view (public scan) - no saldo"""
        return {
            'kartu_id': self.kartu_id,
            'nrp': self.nrp,
            'nama': self.nama,
            'pangkat': self.pangkat,
            'satuan': self.satuan,
            'jabatan': self.jabatan,
            'jurusan': self.jurusan,
            'tempat_lahir': self.tempat_lahir,
            'tanggal_lahir': self.tanggal_lahir.strftime('%Y-%m-%d') if self.tanggal_lahir else None,
            'golongan_darah': self.golongan_darah,
            'agama': self.agama,
            'foto': self.foto,
            'status_kartu': self.status_kartu,
        }


class Transaksi(db.Model):
    """Transaction records: payments and top-ups"""
    __tablename__ = 'transaksi'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trx_id = db.Column(db.String(30), unique=True, nullable=False, index=True)
    anggota_id = db.Column(db.Integer, db.ForeignKey('anggota.id'), nullable=False, index=True)
    jenis = db.Column(db.Enum('Pembelian', 'Top Up'), nullable=False)
    keterangan = db.Column(db.String(200), nullable=True)
    nominal = db.Column(db.BigInteger, nullable=False)
    saldo_sebelum = db.Column(db.BigInteger, nullable=False)
    saldo_sesudah = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.Enum('Berhasil', 'Gagal', 'Pending'), default='Pending', nullable=False)
    metode = db.Column(db.String(20), default='NFC')  # NFC, QR, Manual
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relationships
    operator = db.relationship('User', backref='transaksi_processed', foreign_keys=[operator_id])
    items = db.relationship('TransaksiItem', backref='transaksi', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self, include_items=False):
        data = {
            'id': self.id,
            'trx_id': self.trx_id,
            'anggota_id': self.anggota_id,
            'anggota_nama': self.anggota.nama if self.anggota else None,
            'anggota_kartu_id': self.anggota.kartu_id if self.anggota else None,
            'jenis': self.jenis,
            'keterangan': self.keterangan,
            'nominal': self.nominal,
            'saldo_sebelum': self.saldo_sebelum,
            'saldo_sesudah': self.saldo_sesudah,
            'status': self.status,
            'metode': self.metode,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        if include_items:
            data['items'] = [item.to_dict() for item in self.items.all()]
        return data


class LokasiHistory(db.Model):
    """Location tracking history for card tracking"""
    __tablename__ = 'lokasi_history'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    anggota_id = db.Column(db.Integer, db.ForeignKey('anggota.id'), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    lokasi_nama = db.Column(db.String(200), nullable=True)
    sumber = db.Column(db.String(20), default='NFC')  # NFC scan, GPS, Manual
    scanned_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    waktu = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relationship
    scanned_by = db.relationship('User', backref='scan_logs', foreign_keys=[scanned_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'anggota_id': self.anggota_id,
            'anggota_nama': self.anggota.nama if self.anggota else None,
            'anggota_kartu_id': self.anggota.kartu_id if self.anggota else None,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'lokasi_nama': self.lokasi_nama,
            'sumber': self.sumber,
            'scanned_by_user_id': self.scanned_by_user_id,
            'scanned_by_nama': self.scanned_by.nama if self.scanned_by else None,
            'waktu': self.waktu.strftime('%Y-%m-%d %H:%M:%S'),
        }


class KategoriProduk(db.Model):
    """Product categories for supermarket-style system"""
    __tablename__ = 'kategori_produk'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama = db.Column(db.String(50), unique=True, nullable=False)
    icon = db.Column(db.String(50), default='bi-box')  # Bootstrap icon class
    urutan = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relationship
    produk = db.relationship('Produk', backref='kategori_ref', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'nama': self.nama,
            'icon': self.icon,
            'urutan': self.urutan,
            'is_active': self.is_active,
            'produk_count': self.produk.filter_by(is_available=True).count(),
        }


class Produk(db.Model):
    """Products for supermarket-style canteen"""
    __tablename__ = 'produk'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kode = db.Column(db.String(20), unique=True, nullable=False)  # Barcode or product code
    nama = db.Column(db.String(100), nullable=False)
    kategori_id = db.Column(db.Integer, db.ForeignKey('kategori_produk.id'), nullable=False)
    harga = db.Column(db.BigInteger, nullable=False)
    stok = db.Column(db.Integer, default=0, nullable=False)
    stok_minimum = db.Column(db.Integer, default=5)  # Alert when below this
    satuan = db.Column(db.String(20), default='pcs')  # pcs, botol, bungkus, etc
    gambar = db.Column(db.String(255), default='/static/img/product-default.svg')
    deskripsi = db.Column(db.Text, nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'kode': self.kode,
            'nama': self.nama,
            'kategori_id': self.kategori_id,
            'kategori': self.kategori_ref.nama if self.kategori_ref else None,
            'harga': self.harga,
            'stok': self.stok,
            'stok_minimum': self.stok_minimum,
            'stok_rendah': self.stok <= self.stok_minimum,
            'satuan': self.satuan,
            'gambar': self.gambar,
            'deskripsi': self.deskripsi,
            'is_available': self.is_available and self.stok > 0,
        }


class TransaksiItem(db.Model):
    """Individual items in a transaction (cart items)"""
    __tablename__ = 'transaksi_item'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transaksi_id = db.Column(db.Integer, db.ForeignKey('transaksi.id'), nullable=False)
    produk_id = db.Column(db.Integer, db.ForeignKey('produk.id'), nullable=False)
    nama_produk = db.Column(db.String(100), nullable=False)  # Snapshot of product name
    harga_satuan = db.Column(db.BigInteger, nullable=False)  # Snapshot of price at time of sale
    jumlah = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.BigInteger, nullable=False)

    # Relationships
    produk = db.relationship('Produk', backref='transaksi_items')

    def to_dict(self):
        return {
            'id': self.id,
            'produk_id': self.produk_id,
            'nama_produk': self.nama_produk,
            'harga_satuan': self.harga_satuan,
            'jumlah': self.jumlah,
            'subtotal': self.subtotal,
        }


class MenuKantin(db.Model):
    """Canteen menu items - LEGACY, kept for backward compatibility"""
    __tablename__ = 'menu_kantin'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama = db.Column(db.String(100), nullable=False)
    kategori = db.Column(db.Enum('Makanan', 'Minuman', 'Snack'), nullable=False)
    harga = db.Column(db.BigInteger, nullable=False)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'nama': self.nama,
            'kategori': self.kategori,
            'harga': self.harga,
            'is_available': self.is_available,
        }


class FindMyTracker(db.Model):
    """Google Find Hub Tracker mapping to Anggota"""
    __tablename__ = 'findmy_tracker'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    canonical_id = db.Column(db.String(100), unique=True, nullable=False, index=True)  # Google Find Hub canonic_device_id
    anggota_id = db.Column(db.Integer, db.ForeignKey('anggota.id'), nullable=False, index=True)
    nama_tracker = db.Column(db.String(100), nullable=True)  # Friendly name, e.g. "MiCard Pro - Budi"
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_seen = db.Column(db.DateTime, nullable=True)
    last_latitude = db.Column(db.Float, nullable=True)
    last_longitude = db.Column(db.Float, nullable=True)
    last_address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationship
    anggota = db.relationship('Anggota', backref=db.backref('findmy_trackers', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'canonical_id': self.canonical_id,
            'anggota_id': self.anggota_id,
            'anggota_nama': self.anggota.nama if self.anggota else None,
            'anggota_kartu_id': self.anggota.kartu_id if self.anggota else None,
            'nama_tracker': self.nama_tracker,
            'is_active': self.is_active,
            'last_seen': self.last_seen.strftime('%Y-%m-%d %H:%M:%S') if self.last_seen else None,
            'last_latitude': self.last_latitude,
            'last_longitude': self.last_longitude,
            'last_address': self.last_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
