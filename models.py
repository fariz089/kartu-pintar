"""
Kartu Pintar - Database Models
SQLAlchemy ORM Models for MySQL
"""
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid

db = SQLAlchemy()


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
    satuan = db.Column(db.String(100), default='Poltekkad', nullable=False)
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

    # Saldo (e-wallet)
    saldo = db.Column(db.BigInteger, default=0, nullable=False)

    # Kartu status & tracking
    status_kartu = db.Column(db.Enum('Aktif', 'Nonaktif', 'Hilang', 'Diblokir'), default='Aktif', nullable=False)
    lokasi_lat = db.Column(db.Float, nullable=True)
    lokasi_lng = db.Column(db.Float, nullable=True)
    lokasi_nama = db.Column(db.String(200), nullable=True)
    lokasi_waktu = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    transaksi = db.relationship('Transaksi', backref='anggota', lazy='dynamic', order_by='Transaksi.created_at.desc()')
    lokasi_history = db.relationship('LokasiHistory', backref='anggota', lazy='dynamic', order_by='LokasiHistory.waktu.desc()')

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

    # Relationship
    operator = db.relationship('User', backref='transaksi_processed', foreign_keys=[operator_id])

    def to_dict(self):
        return {
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


class MenuKantin(db.Model):
    """Canteen menu items"""
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
