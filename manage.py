"""
Kartu Pintar - Management CLI
Usage:
    python manage.py init-db       # Create all tables
    python manage.py seed          # Seed with dummy data
    python manage.py drop-db       # Drop all tables (WARNING!)
    python manage.py reset-db      # Drop + Create + Seed
    python manage.py create-user   # Create a new user
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


def show_help():
    print(__doc__)


if __name__ == '__main__':
    commands = {
        'init-db': init_db,
        'drop-db': drop_db,
        'seed': seed,
        'reset-db': reset_db,
        'create-user': create_user,
        'help': show_help,
    }

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        show_help()
        if len(sys.argv) >= 2:
            print(f"\n❌ Unknown command: {sys.argv[1]}")
        sys.exit(1)

    commands[sys.argv[1]]()
