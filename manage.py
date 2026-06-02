"""
Kartu Pintar - Management CLI
Usage:
    python manage.py init-db       # Create all tables
    python manage.py seed          # Seed with dummy data
    python manage.py drop-db       # Drop all tables (WARNING!)
    python manage.py reset-db      # Drop + Create + Seed
    python manage.py create-user   # Create a new user
    python manage.py migrate-totp  # Add 2FA columns to existing users table
    python manage.py migrate-hutang # Add hutang columns (anggota + transaksi)
    python manage.py reset-totp    # Reset 2FA for a specific user
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, User


def init_db():
    """Create all database tables"""
    app = create_app()
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")
        print("   Tables: users, anggota, transaksi, lokasi_history, menu_kantin")


def drop_db():
    """Drop all database tables"""
    app = create_app()
    with app.app_context():
        confirm = input("⚠️  This will DELETE ALL DATA. Type 'yes' to confirm: ")
        if confirm.lower() == 'yes':
            db.drop_all()
            print("✅ All tables dropped.")
        else:
            print("❌ Cancelled.")


def seed():
    """Seed database with dummy data"""
    app = create_app()
    with app.app_context():
        from seed import seed_database
        seed_database()


def reset_db():
    """Drop + Create + Seed"""
    app = create_app()
    with app.app_context():
        print("🔄 Resetting database...")
        db.drop_all()
        print("  ✅ Tables dropped")
        db.create_all()
        print("  ✅ Tables created")
        from seed import seed_database
        seed_database()


def create_user():
    """Create a new user interactively"""
    app = create_app()
    with app.app_context():
        print("\n📝 Create New User")
        print("=" * 30)
        username = input("Username: ").strip()
        if not username:
            print("❌ Username is required")
            return

        if User.query.filter_by(username=username).first():
            print(f"❌ Username '{username}' already exists")
            return

        nama = input("Nama lengkap: ").strip()
        password = input("Password: ").strip()
        email = input("Email (optional): ").strip() or None
        role = input("Role (admin/user/operator_kantin) [user]: ").strip() or 'user'

        if role not in ('admin', 'user', 'operator_kantin'):
            print(f"❌ Invalid role: {role}")
            return

        user = User(username=username, nama=nama, email=email, role=role, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        print(f"\n✅ User created!")
        print(f"   Username : {username}")
        print(f"   Nama     : {nama}")
        print(f"   Role     : {role}")


def migrate_totp():
    """Add TOTP columns to existing users table (idempotent)."""
    app = create_app()
    with app.app_context():
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        cols = {c['name'] for c in insp.get_columns('users')}
        statements = []
        if 'totp_secret' not in cols:
            statements.append("ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64) NULL")
        if 'totp_enabled' not in cols:
            statements.append("ALTER TABLE users ADD COLUMN totp_enabled TINYINT(1) NOT NULL DEFAULT 0")
        if 'totp_backup_codes' not in cols:
            statements.append("ALTER TABLE users ADD COLUMN totp_backup_codes TEXT NULL")
        if not statements:
            print("✅ Kolom TOTP sudah ada. Tidak ada perubahan.")
            return
        with db.engine.begin() as conn:
            for s in statements:
                print("   →", s)
                conn.execute(text(s))
        print("✅ Migrasi TOTP selesai.")


def migrate_hutang():
    """Add hutang columns + update Transaksi.jenis enum (idempotent)."""
    app = create_app()
    with app.app_context():
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        statements = []

        anggota_cols = {c['name'] for c in insp.get_columns('anggota')}
        if 'hutang' not in anggota_cols:
            statements.append("ALTER TABLE anggota ADD COLUMN hutang BIGINT NOT NULL DEFAULT 0")

        trx_cols = {c['name'] for c in insp.get_columns('transaksi')}
        if 'hutang_ditambah' not in trx_cols:
            statements.append("ALTER TABLE transaksi ADD COLUMN hutang_ditambah BIGINT NOT NULL DEFAULT 0")

        # Perlebar enum jenis agar menerima 'Bayar Hutang'
        statements.append(
            "ALTER TABLE transaksi MODIFY COLUMN jenis "
            "ENUM('Pembelian','Top Up','Bayar Hutang') NOT NULL"
        )

        with db.engine.begin() as conn:
            for s in statements:
                print("   →", s)
                try:
                    conn.execute(text(s))
                except Exception as e:
                    print(f"   ⚠️  Lewati (mungkin sudah diterapkan): {e}")
        print("✅ Migrasi hutang selesai.")


def reset_totp():
    """Reset 2FA for a specific user (so they re-enroll on next login)."""
    app = create_app()
    with app.app_context():
        username = input("Username yang 2FA-nya direset: ").strip()
        if not username:
            print("❌ Username wajib")
            return
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"❌ User '{username}' tidak ditemukan")
            return
        user.totp_secret = None
        user.totp_enabled = False
        user.totp_backup_codes = None
        db.session.commit()
        print(f"✅ 2FA untuk '{username}' di-reset. User akan setup ulang saat login berikutnya.")


def show_help():
    print(__doc__)


if __name__ == '__main__':
    commands = {
        'init-db': init_db,
        'drop-db': drop_db,
        'seed': seed,
        'reset-db': reset_db,
        'create-user': create_user,
        'migrate-totp': migrate_totp,
        'migrate-hutang': migrate_hutang,
        'reset-totp': reset_totp,
        'help': show_help,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        show_help()
        if len(sys.argv) >= 2:
            print(f"\n❌ Unknown command: {sys.argv[1]}")
        sys.exit(1)

    commands[sys.argv[1]]()
