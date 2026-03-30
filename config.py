"""
Kartu Pintar - Configuration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'kartu-pintar-secret-key-poltekkad-2025-change-in-production')

    # MySQL Database
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
    DB_NAME = os.environ.get('DB_NAME', 'kartu_pintar')

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_size': 10,
        'max_overflow': 20,
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # Upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max

    # Pagination
    ITEMS_PER_PAGE = 20

    # ============================================================
    # Google Find Hub - Tracker Mapping
    # ============================================================
    # Format: { 'canonic_device_id': 'kartu_id_anggota' }
    #
    # canonic_device_id  = ID dari GoogleFindMyTools (lihat output main.py)
    # kartu_id_anggota   = kartu_id di tabel anggota (misal 'KP-2025-001')
    #
    # Tracker yang terdeteksi dari akun Google kamu:
    #   1. Google Pixel 6 Pro: 66d9ba4b-0000-22a0-a17a-582429ccdab0
    #   2. Micard Pro:         69bf1cb3-0000-202d-b6b0-14223bb2d81a
    #
    # Sesuaikan mapping di bawah dengan kartu_id anggota yang benar:
    FINDMY_TRACKER_MAP = {
        '69bf1cb3-0000-202d-b6b0-14223bb2d81a': 'KP-2025-001',  # Micard Pro → Anggota pertama
        # Tambahkan tracker lain di sini:
        # 'canonic_id_tracker_lain': 'KP-2025-002',
    }

    # Interval update lokasi otomatis (dalam detik, default 5 menit)
    FINDMY_UPDATE_INTERVAL = int(os.environ.get('FINDMY_UPDATE_INTERVAL', 300))


class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}