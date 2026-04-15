"""
Kartu Pintar - Sistem Kartu Tanda Anggota Digital
TNI Angkatan Darat - Poltekkad
Flask Application with MySQL Backend
"""

from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from functools import wraps
from datetime import datetime, timedelta
import os
import uuid
import jwt as pyjwt

from config import config_map
from models import db, User, Anggota, Transaksi, TransaksiItem, LokasiHistory, MenuKantin, KategoriProduk, Produk, FindMyTracker


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map['default']))
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'static/uploads'), exist_ok=True)
    db.init_app(app)
    register_filters(app)
    register_context_processors(app)
    register_routes(app)
    register_api_routes(app)
    register_error_handlers(app)
    return app


def register_filters(app):
    @app.template_filter('rupiah')
    def rupiah_format(value):
        try:
            return f"Rp {int(value):,.0f}".replace(",", ".")
        except (ValueError, TypeError):
            return "Rp 0"

    @app.template_filter('datetime_format')
    def datetime_format_filter(value, fmt='%d %b %Y, %H:%M'):
        if isinstance(value, datetime):
            return value.strftime(fmt)
        if isinstance(value, str):
            try:
                return datetime.strptime(value, '%Y-%m-%d %H:%M:%S').strftime(fmt)
            except ValueError:
                return value
        return value


def register_context_processors(app):
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}


# ============================================================
# AUTH DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Login required'}), 401
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Login required'}), 401
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            flash('Anda tidak memiliki akses.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def kantin_or_admin_required(f):
    """Allow admin and operator_kantin only"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'operator_kantin'):
            flash('Anda tidak memiliki akses.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ============================================================
# JWT HELPERS (for React Native mobile app)
# ============================================================

def generate_jwt_token(user):
    """Generate JWT token for mobile API"""
    from flask import current_app
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'nama': user.nama,
        'anggota_id': user.anggota_id,
        'exp': datetime.utcnow() + timedelta(days=7),
        'iat': datetime.utcnow(),
    }
    return pyjwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def jwt_required(f):
    """Decorator for JWT-protected API endpoints (mobile)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        if not token:
            # Fallback to session auth (for web)
            if 'user_id' in session:
                request.current_user_id = session['user_id']
                request.current_role = session.get('role')
                return f(*args, **kwargs)
            return jsonify({'success': False, 'message': 'Token required'}), 401

        try:
            from flask import current_app
            payload = pyjwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            request.current_user_id = payload['user_id']
            request.current_role = payload.get('role')
        except pyjwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Token invalid'}), 401

        return f(*args, **kwargs)
    return decorated


def jwt_admin_required(f):
    """JWT decorator requiring admin role"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        if not token:
            if 'user_id' in session and session.get('role') == 'admin':
                request.current_user_id = session['user_id']
                request.current_role = 'admin'
                return f(*args, **kwargs)
            return jsonify({'success': False, 'message': 'Admin token required'}), 401

        try:
            from flask import current_app
            payload = pyjwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            if payload.get('role') != 'admin':
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            request.current_user_id = payload['user_id']
            request.current_role = 'admin'
        except pyjwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token expired'}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Token invalid'}), 401

        return f(*args, **kwargs)
    return decorated


def generate_trx_id():
    return f"TRX-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def anggota_to_dict(a, include_lokasi=True):
    """Helper to convert Anggota ORM object to template-compatible dict"""
    d = {
        'id': a.kartu_id, 'nrp': a.nrp, 'nama': a.nama,
        'pangkat': a.pangkat, 'satuan': a.satuan, 'jabatan': a.jabatan,
        'jurusan': a.jurusan, 'foto': a.foto, 'saldo': a.saldo,
        'status_kartu': a.status_kartu, 'nfc_uid': a.nfc_uid,
        'qr_data': a.qr_data, 'tempat_lahir': a.tempat_lahir,
        'tanggal_lahir': a.tanggal_lahir.strftime('%d %B %Y') if a.tanggal_lahir else '',
        'golongan_darah': a.golongan_darah, 'agama': a.agama,
        'alamat': a.alamat, 'no_telepon': a.no_telepon,
    }
    if include_lokasi:
        d['lokasi_terakhir'] = {
            'lat': a.lokasi_lat, 'lng': a.lokasi_lng,
            'lokasi': a.lokasi_nama,
            'waktu': a.lokasi_waktu.strftime('%Y-%m-%d %H:%M:%S') if a.lokasi_waktu else '',
        }
    return d


def trx_to_dict(t):
    """Helper to convert Transaksi ORM object to template-compatible dict"""
    return {
        'id': t.trx_id,
        'anggota_id': t.anggota.kartu_id if t.anggota else '',
        'nama': t.anggota.nama if t.anggota else '',
        'jenis': t.jenis, 'keterangan': t.keterangan,
        'nominal': t.nominal,
        'waktu': t.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'status': t.status,
    }


# ============================================================
# WEB ROUTES
# ============================================================

def register_routes(app):

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if not user.is_active:
                    flash('Akun dinonaktifkan. Hubungi administrator.', 'danger')
                    return render_template('auth/login.html')
                session.permanent = True
                session['user_id'] = user.id
                session['user'] = user.username
                session['role'] = user.role
                session['nama'] = user.nama
                session['anggota_id'] = user.anggota_id
                flash(f'Selamat datang, {user.nama}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau password salah.', 'danger')
        return render_template('auth/login.html')

    @app.route('/logout')
    def logout():
        session.clear()
        flash('Anda telah berhasil logout.', 'info')
        return redirect(url_for('login'))

    # --- DASHBOARD ---

    @app.route('/dashboard')
    @login_required
    def dashboard():
        role = session.get('role')
        # User → redirect to scan page (their main function)
        if role == 'user':
            return redirect(url_for('scan_page'))
        # Operator kantin → redirect to pembayaran
        if role == 'operator_kantin':
            return redirect(url_for('pembayaran'))
        # Admin → full dashboard
        total_anggota = Anggota.query.count()
        kartu_aktif = Anggota.query.filter_by(status_kartu='Aktif').count()
        kartu_hilang = Anggota.query.filter_by(status_kartu='Hilang').count()
        total_saldo = db.session.query(db.func.coalesce(db.func.sum(Anggota.saldo), 0)).scalar()
        total_transaksi = Transaksi.query.count()
        transaksi_terbaru = Transaksi.query.order_by(Transaksi.created_at.desc()).limit(5).all()
        anggota_raw = Anggota.query.limit(5).all()

        return render_template('dashboard.html',
            total_anggota=total_anggota, kartu_aktif=kartu_aktif,
            kartu_hilang=kartu_hilang, total_saldo=total_saldo,
            total_transaksi=total_transaksi,
            transaksi_terbaru=[trx_to_dict(t) for t in transaksi_terbaru],
            anggota_data=[anggota_to_dict(a) for a in anggota_raw],
        )

    # --- ANGGOTA (Admin only) ---

    @app.route('/anggota')
    @admin_required
    def anggota_list():
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        query = Anggota.query
        if search:
            query = query.filter(db.or_(
                Anggota.nama.ilike(f'%{search}%'),
                Anggota.nrp.ilike(f'%{search}%'),
                Anggota.kartu_id.ilike(f'%{search}%'),
                Anggota.pangkat.ilike(f'%{search}%'),
            ))
        if status:
            query = query.filter_by(status_kartu=status)
        all_anggota = query.order_by(Anggota.nama).all()
        return render_template('anggota_list.html',
            anggota_data=[anggota_to_dict(a, include_lokasi=False) for a in all_anggota])

    @app.route('/anggota/<anggota_id>')
    @admin_required
    def anggota_detail(anggota_id):
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            flash('Data anggota tidak ditemukan.', 'danger')
            return redirect(url_for('anggota_list'))
        trx_raw = Transaksi.query.filter_by(anggota_id=a.id).order_by(Transaksi.created_at.desc()).limit(20).all()
        return render_template('anggota_detail.html',
            anggota=anggota_to_dict(a),
            transaksi=[trx_to_dict(t) for t in trx_raw])

    @app.route('/anggota/tambah', methods=['GET', 'POST'])
    @admin_required
    def anggota_tambah():
        if request.method == 'POST':
            try:
                tgl = request.form.get('tanggal_lahir', '')
                tgl_lahir = datetime.strptime(tgl, '%Y-%m-%d').date() if tgl else None

                nrp = request.form.get('nrp', '').strip()
                if Anggota.query.filter_by(nrp=nrp).first():
                    flash('NRP sudah terdaftar!', 'danger')
                    return render_template('admin/anggota_form.html', mode='tambah')

                count = Anggota.query.count() + 1
                year = datetime.now().strftime('%Y')
                kartu_id = f"KP-{year}-{count:03d}"
                while Anggota.query.filter_by(kartu_id=kartu_id).first():
                    count += 1
                    kartu_id = f"KP-{year}-{count:03d}"

                anggota = Anggota(
                    kartu_id=kartu_id, nrp=nrp,
                    nama=request.form.get('nama', '').strip(),
                    pangkat=request.form.get('pangkat', '').strip(),
                    satuan=request.form.get('satuan', 'Poltekkad').strip(),
                    jabatan=request.form.get('jabatan', '').strip(),
                    jurusan=request.form.get('jurusan', '').strip(),
                    tempat_lahir=request.form.get('tempat_lahir', '').strip(),
                    tanggal_lahir=tgl_lahir,
                    golongan_darah=request.form.get('golongan_darah') or None,
                    agama=request.form.get('agama', '').strip(),
                    alamat=request.form.get('alamat', '').strip(),
                    no_telepon=request.form.get('no_telepon', '').strip(),
                    nfc_uid=request.form.get('nfc_uid', '').strip() or None,
                    qr_data=kartu_id, saldo=0, status_kartu='Aktif',
                )
                db.session.add(anggota)
                db.session.commit()
                flash(f'Anggota {anggota.nama} berhasil ditambahkan (ID: {kartu_id})!', 'success')
                return redirect(url_for('anggota_detail', anggota_id=kartu_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Gagal: {str(e)}', 'danger')
        return render_template('admin/anggota_form.html', mode='tambah')

    @app.route('/anggota/edit/<anggota_id>', methods=['GET', 'POST'])
    @admin_required
    def anggota_edit(anggota_id):
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            flash('Data anggota tidak ditemukan.', 'danger')
            return redirect(url_for('anggota_list'))
        if request.method == 'POST':
            try:
                tgl = request.form.get('tanggal_lahir', '')
                if tgl:
                    a.tanggal_lahir = datetime.strptime(tgl, '%Y-%m-%d').date()
                a.nama = request.form.get('nama', a.nama).strip()
                a.pangkat = request.form.get('pangkat', a.pangkat).strip()
                a.satuan = request.form.get('satuan', a.satuan).strip()
                a.jabatan = request.form.get('jabatan', a.jabatan).strip()
                a.jurusan = request.form.get('jurusan', a.jurusan).strip()
                a.tempat_lahir = request.form.get('tempat_lahir', a.tempat_lahir).strip()
                a.golongan_darah = request.form.get('golongan_darah', a.golongan_darah)
                a.agama = request.form.get('agama', a.agama).strip()
                a.alamat = request.form.get('alamat', a.alamat).strip()
                a.no_telepon = request.form.get('no_telepon', a.no_telepon or '').strip()
                a.nfc_uid = request.form.get('nfc_uid', a.nfc_uid or '').strip() or a.nfc_uid
                a.status_kartu = request.form.get('status_kartu', a.status_kartu)
                db.session.commit()
                flash('Data anggota berhasil diperbarui!', 'success')
                return redirect(url_for('anggota_detail', anggota_id=anggota_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Gagal: {str(e)}', 'danger')

        anggota = anggota_to_dict(a)
        # Override tanggal_lahir format for form input
        anggota['tanggal_lahir'] = a.tanggal_lahir.strftime('%Y-%m-%d') if a.tanggal_lahir else ''
        return render_template('admin/anggota_form.html', mode='edit', anggota=anggota)

    @app.route('/anggota/delete/<anggota_id>', methods=['POST'])
    @admin_required
    def anggota_delete(anggota_id):
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            flash('Data anggota tidak ditemukan.', 'danger')
            return redirect(url_for('anggota_list'))
        try:
            Transaksi.query.filter_by(anggota_id=a.id).delete()
            LokasiHistory.query.filter_by(anggota_id=a.id).delete()
            User.query.filter_by(anggota_id=a.id).update({'anggota_id': None})
            db.session.delete(a)
            db.session.commit()
            flash(f'Anggota {a.nama} berhasil dihapus.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('anggota_list'))

    # --- SCAN NFC & QR ---

    @app.route('/scan')
    @login_required
    def scan_page():
        return render_template('scan.html')

    @app.route('/scan/result/<card_id>')
    @login_required
    def scan_result(card_id):
        a = Anggota.query.filter(db.or_(
            Anggota.qr_data == card_id,
            Anggota.nfc_uid == card_id,
            Anggota.kartu_id == card_id,
        )).first()
        if not a:
            flash('Kartu tidak terdaftar dalam sistem.', 'danger')
            return redirect(url_for('scan_page'))

        # Log scan with who scanned it
        a.lokasi_waktu = datetime.now()
        db.session.add(LokasiHistory(
            anggota_id=a.id,
            latitude=a.lokasi_lat or -6.8927,
            longitude=a.lokasi_lng or 107.6100,
            lokasi_nama='Scan Point',
            sumber='QR' if card_id == a.qr_data else 'NFC',
            scanned_by_user_id=session.get('user_id'),
        ))
        db.session.commit()

        role = session.get('role')
        anggota_data = anggota_to_dict(a)
        # For user role: hide saldo and sensitive info
        if role == 'user':
            anggota_data['saldo'] = None
            anggota_data['show_saldo'] = False
        else:
            anggota_data['show_saldo'] = True

        return render_template('scan_result.html', anggota=anggota_data, user_role=role)

    # --- PEMBAYARAN (Admin + Operator Kantin) ---

    @app.route('/pembayaran')
    @kantin_or_admin_required
    def pembayaran():
        anggota_raw = Anggota.query.filter_by(status_kartu='Aktif').order_by(Anggota.nama).all()
        anggota_data = [{
            'id': a.kartu_id, 'kartu_id': a.kartu_id, 'nrp': a.nrp, 'nama': a.nama,
            'pangkat': a.pangkat, 'saldo': a.saldo,
            'nfc_uid': a.nfc_uid, 'qr_data': a.qr_data, 'foto': a.foto,
            'status_kartu': a.status_kartu,
        } for a in anggota_raw]
        
        # Get products and categories for POS
        produk_raw = Produk.query.filter_by(is_available=True).filter(Produk.stok > 0).order_by(Produk.kategori_id, Produk.nama).all()
        produk_data = [p.to_dict() for p in produk_raw]
        
        kategori_raw = KategoriProduk.query.filter_by(is_active=True).order_by(KategoriProduk.urutan).all()
        kategori_data = [k.to_dict() for k in kategori_raw]
        
        # Recent payment transactions for sidebar
        trx_raw = Transaksi.query.filter_by(jenis='Pembelian').order_by(Transaksi.created_at.desc()).limit(5).all()
        transaksi_terbaru = [trx_to_dict(t) for t in trx_raw]
        
        return render_template('pembayaran.html', 
            anggota_data=anggota_data, 
            produk_data=produk_data,
            kategori_data=kategori_data,
            transaksi_terbaru=transaksi_terbaru)

    @app.route('/pembayaran/proses', methods=['POST'])
    @kantin_or_admin_required
    def pembayaran_proses():
        try:
            kartu_id = request.form.get('anggota_id', '').strip()
            nominal = int(request.form.get('nominal', 0))
            keterangan = request.form.get('keterangan', 'Pembelian di Kantin').strip()
            metode = request.form.get('metode', 'NFC')

            if nominal <= 0:
                flash('Nominal harus lebih dari 0.', 'danger')
                return redirect(url_for('pembayaran'))

            anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
            if not anggota:
                flash('Anggota tidak ditemukan.', 'danger')
                return redirect(url_for('pembayaran'))
            if anggota.status_kartu != 'Aktif':
                flash(f'Kartu {anggota.nama} tidak aktif.', 'danger')
                return redirect(url_for('pembayaran'))

            saldo_sebelum = anggota.saldo

            if anggota.saldo < nominal:
                db.session.add(Transaksi(
                    trx_id=generate_trx_id(), anggota_id=anggota.id,
                    jenis='Pembelian', keterangan=keterangan, nominal=nominal,
                    saldo_sebelum=saldo_sebelum, saldo_sesudah=saldo_sebelum,
                    status='Gagal', metode=metode, operator_id=session.get('user_id'),
                ))
                db.session.commit()
                flash(f'Saldo tidak cukup! Saldo: Rp {saldo_sebelum:,.0f}'.replace(',', '.'), 'danger')
                return redirect(url_for('pembayaran'))

            anggota.saldo -= nominal
            db.session.add(Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Pembelian', keterangan=keterangan, nominal=nominal,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode=metode, operator_id=session.get('user_id'),
            ))
            anggota.lokasi_nama = 'Kantin Poltekkad'
            anggota.lokasi_lat = -6.8927
            anggota.lokasi_lng = 107.6100
            anggota.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=anggota.id, latitude=-6.8927, longitude=107.6100,
                lokasi_nama='Kantin Poltekkad', sumber=metode,
            ))
            db.session.commit()
            flash(f'Pembayaran berhasil! {anggota.nama} - Rp {nominal:,.0f} | Sisa: Rp {anggota.saldo:,.0f}'.replace(',', '.'), 'success')
        except ValueError:
            flash('Nominal tidak valid.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('pembayaran'))

    # --- TOP UP ---

    @app.route('/topup')
    @admin_required
    def topup():
        anggota_raw = Anggota.query.order_by(Anggota.nama).all()
        anggota_data = [{
            'id': a.kartu_id, 'nrp': a.nrp, 'nama': a.nama,
            'pangkat': a.pangkat, 'saldo': a.saldo, 'status_kartu': a.status_kartu,
        } for a in anggota_raw]
        return render_template('admin/topup.html', anggota_data=anggota_data)

    @app.route('/topup/proses', methods=['POST'])
    @admin_required
    def topup_proses():
        try:
            kartu_id = request.form.get('anggota_id', '').strip()
            nominal = int(request.form.get('nominal', 0))
            if nominal <= 0:
                flash('Nominal harus lebih dari 0.', 'danger')
                return redirect(url_for('topup'))
            if nominal > 5000000:
                flash('Maksimal Rp 5.000.000.', 'danger')
                return redirect(url_for('topup'))

            anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
            if not anggota:
                flash('Anggota tidak ditemukan.', 'danger')
                return redirect(url_for('topup'))

            saldo_sebelum = anggota.saldo
            anggota.saldo += nominal
            db.session.add(Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Top Up', keterangan='Pengisian Saldo', nominal=nominal,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode='Manual', operator_id=session.get('user_id'),
            ))
            db.session.commit()
            flash(f'Top up berhasil! {anggota.nama} + Rp {nominal:,.0f} | Saldo: Rp {anggota.saldo:,.0f}'.replace(',', '.'), 'success')
        except ValueError:
            flash('Nominal tidak valid.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('topup'))

    # --- LACAK KARTU (Admin only) ---

    @app.route('/lacak')
    @admin_required
    def lacak_kartu():
        anggota_raw = Anggota.query.all()
        anggota_data = [{
            'id': a.kartu_id, 'nama': a.nama, 'pangkat': a.pangkat,
            'status_kartu': a.status_kartu, 'nfc_uid': a.nfc_uid,
            'lokasi_terakhir': {
                'lat': a.lokasi_lat, 'lng': a.lokasi_lng,
                'lokasi': a.lokasi_nama,
                'waktu': a.lokasi_waktu.strftime('%Y-%m-%d %H:%M:%S') if a.lokasi_waktu else '',
            },
        } for a in anggota_raw]
        return render_template('lacak_kartu.html', anggota_data=anggota_data)

    # --- SCAN LOG (Admin only) ---

    @app.route('/scan-log')
    @admin_required
    def scan_log():
        logs = LokasiHistory.query.order_by(LokasiHistory.waktu.desc()).limit(100).all()
        scan_data = [l.to_dict() for l in logs]
        return render_template('admin/scan_log.html', scan_data=scan_data)

    # --- FINDMY TRACKER MANAGEMENT (Admin only) ---

    @app.route('/findmy-trackers')
    @admin_required
    def findmy_tracker_list():
        trackers = FindMyTracker.query.order_by(FindMyTracker.created_at.desc()).all()
        anggota_list = Anggota.query.filter_by(status_kartu='Aktif').order_by(Anggota.nama).all()
        return render_template('admin/findmy_trackers.html', 
                               trackers=[t.to_dict() for t in trackers],
                               anggota_list=[{'id': a.id, 'nama': a.nama, 'kartu_id': a.kartu_id, 'pangkat': a.pangkat} for a in anggota_list])

    @app.route('/findmy-trackers/add', methods=['POST'])
    @admin_required
    def findmy_tracker_add():
        canonical_id = request.form.get('canonical_id', '').strip()
        anggota_id = request.form.get('anggota_id', type=int)
        nama_tracker = request.form.get('nama_tracker', '').strip()

        if not canonical_id or not anggota_id:
            flash('Canonical ID dan Anggota wajib diisi!', 'danger')
            return redirect(url_for('findmy_tracker_list'))

        # Check if canonical_id already exists
        existing = FindMyTracker.query.filter_by(canonical_id=canonical_id).first()
        if existing:
            flash(f'Tracker dengan Canonical ID tersebut sudah terdaftar untuk {existing.anggota.nama}!', 'danger')
            return redirect(url_for('findmy_tracker_list'))

        anggota = Anggota.query.get(anggota_id)
        if not anggota:
            flash('Anggota tidak ditemukan!', 'danger')
            return redirect(url_for('findmy_tracker_list'))

        tracker = FindMyTracker(
            canonical_id=canonical_id,
            anggota_id=anggota_id,
            nama_tracker=nama_tracker or f'Tracker - {anggota.nama}',
            is_active=True
        )
        db.session.add(tracker)
        db.session.commit()

        flash(f'Tracker berhasil ditambahkan untuk {anggota.nama}!', 'success')
        return redirect(url_for('findmy_tracker_list'))

    @app.route('/findmy-trackers/edit/<int:tracker_id>', methods=['POST'])
    @admin_required
    def findmy_tracker_edit(tracker_id):
        tracker = FindMyTracker.query.get_or_404(tracker_id)
        
        canonical_id = request.form.get('canonical_id', '').strip()
        anggota_id = request.form.get('anggota_id', type=int)
        nama_tracker = request.form.get('nama_tracker', '').strip()
        is_active = request.form.get('is_active') == 'on'

        if not canonical_id or not anggota_id:
            flash('Canonical ID dan Anggota wajib diisi!', 'danger')
            return redirect(url_for('findmy_tracker_list'))

        # Check if canonical_id already exists (excluding current)
        existing = FindMyTracker.query.filter(
            FindMyTracker.canonical_id == canonical_id,
            FindMyTracker.id != tracker_id
        ).first()
        if existing:
            flash(f'Canonical ID tersebut sudah digunakan oleh tracker lain!', 'danger')
            return redirect(url_for('findmy_tracker_list'))

        tracker.canonical_id = canonical_id
        tracker.anggota_id = anggota_id
        tracker.nama_tracker = nama_tracker
        tracker.is_active = is_active
        db.session.commit()

        flash('Tracker berhasil diperbarui!', 'success')
        return redirect(url_for('findmy_tracker_list'))

    @app.route('/findmy-trackers/delete/<int:tracker_id>', methods=['POST'])
    @admin_required
    def findmy_tracker_delete(tracker_id):
        tracker = FindMyTracker.query.get_or_404(tracker_id)
        nama = tracker.nama_tracker
        db.session.delete(tracker)
        db.session.commit()
        flash(f'Tracker "{nama}" berhasil dihapus!', 'success')
        return redirect(url_for('findmy_tracker_list'))

    @app.route('/api/findmy/trackers', methods=['GET'])
    @admin_required
    def api_findmy_trackers():
        """API to get all trackers as mapping dict for FindMy integration"""
        trackers = FindMyTracker.query.filter_by(is_active=True).all()
        # Return as mapping: { canonical_id: kartu_id }
        mapping = {t.canonical_id: t.anggota.kartu_id for t in trackers if t.anggota}
        return jsonify({'success': True, 'data': mapping, 'count': len(mapping)})

    @app.route('/api/findmy/update-location', methods=['POST'])
    @admin_required
    def api_findmy_update_location():
        """API to update tracker location from FindMy tools"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400

        canonical_id = data.get('canonical_id', '').strip()
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        address = data.get('address', '')

        if not canonical_id:
            return jsonify({'success': False, 'message': 'canonical_id required'}), 400

        tracker = FindMyTracker.query.filter_by(canonical_id=canonical_id, is_active=True).first()
        if not tracker:
            return jsonify({'success': False, 'message': 'Tracker not found or inactive'}), 404

        # Update tracker
        tracker.last_seen = datetime.now()
        if latitude is not None:
            tracker.last_latitude = latitude
        if longitude is not None:
            tracker.last_longitude = longitude
        if address:
            tracker.last_address = address

        # Also update the anggota location
        if tracker.anggota and latitude is not None and longitude is not None:
            tracker.anggota.lokasi_lat = latitude
            tracker.anggota.lokasi_lng = longitude
            tracker.anggota.lokasi_nama = address or 'FindMy Location'
            tracker.anggota.lokasi_waktu = datetime.now()

            # Log to history
            db.session.add(LokasiHistory(
                anggota_id=tracker.anggota.id,
                latitude=latitude,
                longitude=longitude,
                lokasi_nama=address or 'FindMy Location',
                sumber='FindMy',
                scanned_by_user_id=session.get('user_id'),
            ))

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Location updated for {tracker.anggota.nama if tracker.anggota else "unknown"}',
            'data': tracker.to_dict()
        })

    # --- TRANSAKSI (role-based) ---

    @app.route('/transaksi')
    @login_required
    def transaksi():
        role = session.get('role')
        jenis_filter = request.args.get('jenis', '').strip()

        if role == 'user':
            user = User.query.get(session['user_id'])
            if user and user.anggota_id:
                anggota = Anggota.query.get(user.anggota_id)
                if anggota:
                    all_trx = Transaksi.query.filter_by(anggota_id=anggota.id).order_by(Transaksi.created_at.desc()).all()
                    return render_template('transaksi.html',
                        transaksi_data=[trx_to_dict(t) for t in all_trx],
                        page_title='Riwayat Transaksi Saya')
            return render_template('transaksi.html', transaksi_data=[], page_title='Riwayat Transaksi Saya')
        elif role == 'operator_kantin':
            all_trx = Transaksi.query.filter_by(jenis='Pembelian').order_by(Transaksi.created_at.desc()).all()
            return render_template('transaksi.html',
                transaksi_data=[trx_to_dict(t) for t in all_trx],
                page_title='Riwayat Penjualan Kantin')
        else:
            query = Transaksi.query
            if jenis_filter:
                query = query.filter_by(jenis=jenis_filter)
            page_titles = {
                'Pembelian': 'Riwayat Penjualan',
                'Top Up': 'Riwayat Pengisian Saldo',
            }
            title = page_titles.get(jenis_filter, 'Semua Transaksi')
            all_trx = query.order_by(Transaksi.created_at.desc()).all()
            return render_template('transaksi.html',
                transaksi_data=[trx_to_dict(t) for t in all_trx],
                page_title=title)

    # --- PROFILE (User) ---

    @app.route('/profile')
    @login_required
    def profile():
        user = User.query.get(session['user_id'])
        anggota = None
        if user and user.anggota_id:
            anggota_obj = Anggota.query.get(user.anggota_id)
            if anggota_obj:
                anggota = anggota_to_dict(anggota_obj)
        return render_template('profile.html', user=user, anggota=anggota)

    # --- PRODUK MANAGEMENT (Admin only) ---

    @app.route('/produk')
    @admin_required
    def produk_list():
        kategori_id = request.args.get('kategori', type=int)
        search = request.args.get('search', '').strip()
        
        query = Produk.query
        if kategori_id:
            query = query.filter_by(kategori_id=kategori_id)
        if search:
            query = query.filter(db.or_(
                Produk.nama.ilike(f'%{search}%'),
                Produk.kode.ilike(f'%{search}%'),
            ))
        
        produk_data = query.order_by(Produk.kategori_id, Produk.nama).all()
        kategori_data = KategoriProduk.query.filter_by(is_active=True).order_by(KategoriProduk.urutan).all()
        
        # Stats
        stok_rendah = Produk.query.filter(Produk.stok <= Produk.stok_minimum, Produk.is_available == True).count()
        
        return render_template('admin/produk_list.html',
            produk_data=[p.to_dict() for p in produk_data],
            kategori_data=[k.to_dict() for k in kategori_data],
            selected_kategori=kategori_id,
            stok_rendah=stok_rendah)

    @app.route('/produk/tambah', methods=['GET', 'POST'])
    @admin_required
    def produk_tambah():
        kategori_data = KategoriProduk.query.filter_by(is_active=True).order_by(KategoriProduk.urutan).all()
        
        if request.method == 'POST':
            try:
                kode = request.form.get('kode', '').strip().upper()
                if Produk.query.filter_by(kode=kode).first():
                    flash('Kode produk sudah digunakan!', 'danger')
                    return render_template('admin/produk_form.html', mode='tambah', kategori_data=kategori_data)
                
                produk = Produk(
                    kode=kode,
                    nama=request.form.get('nama', '').strip(),
                    kategori_id=int(request.form.get('kategori_id')),
                    harga=int(request.form.get('harga', 0)),
                    stok=int(request.form.get('stok', 0)),
                    stok_minimum=int(request.form.get('stok_minimum', 5)),
                    satuan=request.form.get('satuan', 'pcs'),
                    deskripsi=request.form.get('deskripsi', ''),
                )
                db.session.add(produk)
                db.session.commit()
                flash(f'Produk {produk.nama} berhasil ditambahkan!', 'success')
                return redirect(url_for('produk_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Gagal: {str(e)}', 'danger')
        
        return render_template('admin/produk_form.html', mode='tambah', kategori_data=kategori_data)

    @app.route('/produk/edit/<int:produk_id>', methods=['GET', 'POST'])
    @admin_required
    def produk_edit(produk_id):
        produk = Produk.query.get_or_404(produk_id)
        kategori_data = KategoriProduk.query.filter_by(is_active=True).order_by(KategoriProduk.urutan).all()
        
        if request.method == 'POST':
            try:
                produk.nama = request.form.get('nama', produk.nama).strip()
                produk.kategori_id = int(request.form.get('kategori_id', produk.kategori_id))
                produk.harga = int(request.form.get('harga', produk.harga))
                produk.stok = int(request.form.get('stok', produk.stok))
                produk.stok_minimum = int(request.form.get('stok_minimum', produk.stok_minimum))
                produk.satuan = request.form.get('satuan', produk.satuan)
                produk.deskripsi = request.form.get('deskripsi', '')
                produk.is_available = request.form.get('is_available') == 'on'
                db.session.commit()
                flash('Produk berhasil diperbarui!', 'success')
                return redirect(url_for('produk_list'))
            except Exception as e:
                db.session.rollback()
                flash(f'Gagal: {str(e)}', 'danger')
        
        return render_template('admin/produk_form.html', mode='edit', produk=produk.to_dict(), kategori_data=kategori_data)

    @app.route('/produk/delete/<int:produk_id>', methods=['POST'])
    @admin_required
    def produk_delete(produk_id):
        produk = Produk.query.get_or_404(produk_id)
        try:
            nama = produk.nama
            db.session.delete(produk)
            db.session.commit()
            flash(f'Produk {nama} berhasil dihapus.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('produk_list'))

    @app.route('/produk/stok/<int:produk_id>', methods=['POST'])
    @admin_required
    def produk_update_stok(produk_id):
        produk = Produk.query.get_or_404(produk_id)
        try:
            mode = request.form.get('mode', 'set')
            if mode == 'add':
                produk.stok += int(request.form.get('jumlah', 0))
            else:
                produk.stok = int(request.form.get('stok', produk.stok))
            db.session.commit()
            flash(f'Stok {produk.nama} diperbarui: {produk.stok} {produk.satuan}', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('produk_list'))

    # --- KATEGORI MANAGEMENT ---

    @app.route('/kategori')
    @admin_required
    def kategori_list():
        kategori_data = KategoriProduk.query.order_by(KategoriProduk.urutan).all()
        return render_template('admin/kategori_list.html', kategori_data=[k.to_dict() for k in kategori_data])

    @app.route('/kategori/tambah', methods=['POST'])
    @admin_required
    def kategori_tambah():
        try:
            kategori = KategoriProduk(
                nama=request.form.get('nama', '').strip(),
                icon=request.form.get('icon', 'bi-box'),
                urutan=int(request.form.get('urutan', 0)),
            )
            db.session.add(kategori)
            db.session.commit()
            flash(f'Kategori {kategori.nama} berhasil ditambahkan!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('kategori_list'))

    @app.route('/kategori/edit/<int:kategori_id>', methods=['POST'])
    @admin_required
    def kategori_edit(kategori_id):
        kategori = KategoriProduk.query.get_or_404(kategori_id)
        try:
            kategori.nama = request.form.get('nama', kategori.nama).strip()
            kategori.icon = request.form.get('icon', kategori.icon)
            kategori.urutan = int(request.form.get('urutan', kategori.urutan))
            kategori.is_active = request.form.get('is_active') == 'on'
            db.session.commit()
            flash('Kategori berhasil diperbarui!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('kategori_list'))

    @app.route('/kategori/delete/<int:kategori_id>', methods=['POST'])
    @admin_required
    def kategori_delete(kategori_id):
        kategori = KategoriProduk.query.get_or_404(kategori_id)
        if kategori.produk.count() > 0:
            flash('Kategori masih memiliki produk!', 'danger')
            return redirect(url_for('kategori_list'))
        try:
            db.session.delete(kategori)
            db.session.commit()
            flash('Kategori berhasil dihapus.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Gagal: {str(e)}', 'danger')
        return redirect(url_for('kategori_list'))


# ============================================================
# REST API ROUTES (for React Native / AJAX)
# ============================================================

def register_api_routes(app):

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        user = User.query.filter_by(username=data.get('username', '').strip()).first()
        if user and user.check_password(data.get('password', '')):
            if not user.is_active:
                return jsonify({'success': False, 'message': 'Akun dinonaktifkan'}), 403
            token = generate_jwt_token(user)
            user_data = user.to_dict()
            if user.anggota:
                user_data['anggota'] = user.anggota.to_dict()
            return jsonify({
                'success': True,
                'token': token,
                'data': user_data,
            })
        return jsonify({'success': False, 'message': 'Username atau password salah'}), 401

    @app.route('/api/auth/me', methods=['GET'])
    @jwt_required
    def api_me():
        user = User.query.get(request.current_user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        user_data = user.to_dict()
        if user.anggota:
            user_data['anggota'] = user.anggota.to_dict()
        return jsonify({'success': True, 'data': user_data})

    @app.route('/api/auth/change-password', methods=['POST'])
    @jwt_required
    def api_change_password():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        if not old_password or not new_password:
            return jsonify({'success': False, 'message': 'Password lama dan baru harus diisi'}), 400
        if len(new_password) < 4:
            return jsonify({'success': False, 'message': 'Password baru minimal 4 karakter'}), 400
        user = User.query.get(request.current_user_id)
        if not user or not user.check_password(old_password):
            return jsonify({'success': False, 'message': 'Password lama salah'}), 400
        user.set_password(new_password)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Password berhasil diubah'})

    @app.route('/api/anggota', methods=['GET'])
    @jwt_required
    def api_anggota_list():
        search = request.args.get('search', '').strip()
        query = Anggota.query
        if search:
            query = query.filter(db.or_(
                Anggota.nama.ilike(f'%{search}%'),
                Anggota.nrp.ilike(f'%{search}%'),
                Anggota.kartu_id.ilike(f'%{search}%'),
            ))
        result = query.order_by(Anggota.nama).all()
        return jsonify({'success': True, 'data': [a.to_dict() for a in result]})

    @app.route('/api/anggota/<anggota_id>', methods=['GET'])
    @jwt_required
    def api_anggota_detail(anggota_id):
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if a:
            return jsonify({'success': True, 'data': a.to_dict()})
        return jsonify({'success': False, 'message': 'Tidak ditemukan'}), 404

    # --- HELPER: Extract MiLi Card ID from URL ---
    def extract_mili_id(raw_data):
        if not raw_data:
            return raw_data
        data = raw_data.strip()
        if '/info/' in data:
            parts = data.split('/info/')
            if len(parts) > 1:
                return parts[1].split('?')[0].split('#')[0].strip()
        return data

    def find_anggota_by_scan(scan_data, scan_type='NFC'):
        cleaned = extract_mili_id(scan_data)
        raw = scan_data.strip()
        a = Anggota.query.filter(db.or_(
            Anggota.nfc_uid == raw,
            Anggota.nfc_uid == cleaned,
            Anggota.qr_data == raw,
            Anggota.qr_data == cleaned,
            Anggota.kartu_id == raw,
            Anggota.kartu_id == cleaned,
            Anggota.mili_id == cleaned,
        )).first()
        return a

    @app.route('/api/scan/nfc/<path:nfc_uid>', methods=['GET'])
    @jwt_required
    def api_scan_nfc(nfc_uid):
        a = find_anggota_by_scan(nfc_uid, 'NFC')
        if a:
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id, latitude=a.lokasi_lat or -6.8927,
                longitude=a.lokasi_lng or 107.6100,
                lokasi_nama='NFC Scan', sumber='NFC',
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            if getattr(request, 'current_role', None) == 'user':
                return jsonify({'success': True, 'data': a.to_identitas_dict()})
            return jsonify({'success': True, 'data': a.to_dict()})
        return jsonify({'success': False, 'message': 'Kartu NFC tidak terdaftar'}), 404

    @app.route('/api/scan/qr', methods=['POST'])
    @jwt_required
    def api_scan_qr_post():
        data = request.get_json()
        if not data or not data.get('qr_data'):
            return jsonify({'success': False, 'message': 'qr_data required'}), 400
        qr_data = data['qr_data']
        a = find_anggota_by_scan(qr_data, 'QR')
        if a:
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id, latitude=a.lokasi_lat or -6.8927,
                longitude=a.lokasi_lng or 107.6100,
                lokasi_nama='QR Scan', sumber='QR',
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            if getattr(request, 'current_role', None) == 'user':
                return jsonify({'success': True, 'data': a.to_identitas_dict()})
            return jsonify({'success': True, 'data': a.to_dict()})
        return jsonify({'success': False, 'message': 'QR Code tidak valid'}), 404

    @app.route('/api/scan/qr/<path:qr_data>', methods=['GET'])
    @jwt_required
    def api_scan_qr(qr_data):
        a = find_anggota_by_scan(qr_data, 'QR')
        if a:
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id, latitude=a.lokasi_lat or -6.8927,
                longitude=a.lokasi_lng or 107.6100,
                lokasi_nama='QR Scan', sumber='QR',
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            if getattr(request, 'current_role', None) == 'user':
                return jsonify({'success': True, 'data': a.to_identitas_dict()})
            return jsonify({'success': True, 'data': a.to_dict()})
        return jsonify({'success': False, 'message': 'QR Code tidak valid'}), 404

    @app.route('/api/scan/search', methods=['POST'])
    @login_required
    def api_scan_search():
        """Search anggota by scan data (NFC UID, QR Data, or Kartu ID) - for web scanner"""
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        
        scan_data = data.get('scan_data', '').strip()
        metode = data.get('metode', 'Manual')
        
        if not scan_data:
            return jsonify({'success': False, 'message': 'scan_data required'}), 400
        
        a = find_anggota_by_scan(scan_data, metode)
        if a:
            # Log the scan
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id,
                latitude=a.lokasi_lat or -6.8927,
                longitude=a.lokasi_lng or 107.6100,
                lokasi_nama=f'{metode} Scan (Web)',
                sumber=metode,
                scanned_by_user_id=session.get('user_id'),
            ))
            db.session.commit()
            
            # Return appropriate data based on user role
            role = session.get('role', 'user')
            if role == 'user':
                return jsonify({'success': True, 'data': a.to_identitas_dict()})
            return jsonify({'success': True, 'data': a.to_dict()})
        
        return jsonify({'success': False, 'message': 'Data tidak ditemukan. Pastikan NFC UID atau QR Code valid.'}), 404

    @app.route('/api/pembayaran', methods=['POST'])
    @jwt_required
    def api_pembayaran():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        kartu_id = data.get('kartu_id', '').strip()
        nominal = int(data.get('nominal', 0))
        keterangan = data.get('keterangan', 'Pembelian di Kantin')
        metode = data.get('metode', 'NFC')
        if nominal <= 0:
            return jsonify({'success': False, 'message': 'Nominal harus > 0'}), 400
        anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
        if not anggota:
            return jsonify({'success': False, 'message': 'Anggota tidak ditemukan'}), 404
        if anggota.status_kartu != 'Aktif':
            return jsonify({'success': False, 'message': 'Kartu tidak aktif'}), 400
        if anggota.saldo < nominal:
            return jsonify({'success': False, 'message': 'Saldo tidak cukup', 'saldo': anggota.saldo}), 400
        try:
            saldo_sebelum = anggota.saldo
            anggota.saldo -= nominal
            trx = Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Pembelian', keterangan=keterangan, nominal=nominal,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode=metode, operator_id=request.current_user_id,
            )
            db.session.add(trx)
            anggota.lokasi_nama = 'Kantin Poltekkad'
            anggota.lokasi_waktu = datetime.now()
            db.session.commit()
            return jsonify({'success': True, 'data': {
                'trx_id': trx.trx_id, 'nominal': nominal,
                'saldo_sebelum': saldo_sebelum, 'saldo_sesudah': anggota.saldo,
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/topup', methods=['POST'])
    @jwt_admin_required
    def api_topup():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        kartu_id = data.get('kartu_id', '').strip()
        nominal = int(data.get('nominal', 0))
        if nominal <= 0 or nominal > 5000000:
            return jsonify({'success': False, 'message': 'Nominal: 1 - 5.000.000'}), 400
        anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
        if not anggota:
            return jsonify({'success': False, 'message': 'Anggota tidak ditemukan'}), 404
        try:
            saldo_sebelum = anggota.saldo
            anggota.saldo += nominal
            trx = Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Top Up', keterangan='Pengisian Saldo', nominal=nominal,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode='Manual', operator_id=request.current_user_id,
            )
            db.session.add(trx)
            db.session.commit()
            return jsonify({'success': True, 'data': {
                'trx_id': trx.trx_id, 'nominal': nominal,
                'saldo_sebelum': saldo_sebelum, 'saldo_sesudah': anggota.saldo,
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/transaksi', methods=['GET'])
    @jwt_required
    def api_transaksi_list():
        kartu_id = request.args.get('kartu_id', '').strip()
        jenis = request.args.get('jenis', '').strip()
        limit = request.args.get('limit', 50, type=int)
        role = getattr(request, 'current_role', None)
        query = Transaksi.query
        if role == 'user':
            user = User.query.get(request.current_user_id)
            if user and user.anggota_id:
                anggota = Anggota.query.get(user.anggota_id)
                if anggota:
                    query = query.filter_by(anggota_id=anggota.id)
                else:
                    return jsonify({'success': True, 'data': []})
            else:
                return jsonify({'success': True, 'data': []})
        elif role == 'operator_kantin':
            query = query.filter_by(jenis='Pembelian')
        else:
            if kartu_id:
                anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
                if anggota:
                    query = query.filter_by(anggota_id=anggota.id)
            if jenis:
                query = query.filter_by(jenis=jenis)
        result = query.order_by(Transaksi.created_at.desc()).limit(limit).all()
        return jsonify({'success': True, 'data': [t.to_dict() for t in result]})

    @app.route('/api/lacak/<anggota_id>', methods=['GET'])
    @jwt_required
    def api_lacak(anggota_id):
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            return jsonify({'success': False, 'message': 'Tidak ditemukan'}), 404
        history = LokasiHistory.query.filter_by(anggota_id=a.id).order_by(LokasiHistory.waktu.desc()).limit(50).all()
        return jsonify({'success': True, 'data': {
            'anggota': {'kartu_id': a.kartu_id, 'nama': a.nama, 'status_kartu': a.status_kartu},
            'lokasi_terakhir': {
                'lat': a.lokasi_lat, 'lng': a.lokasi_lng, 'lokasi': a.lokasi_nama,
                'waktu': a.lokasi_waktu.strftime('%Y-%m-%d %H:%M:%S') if a.lokasi_waktu else None,
            },
            'history': [h.to_dict() for h in history],
        }})

    @app.route('/api/menu', methods=['GET'])
    @jwt_required
    def api_menu_list():
        menu = MenuKantin.query.filter_by(is_available=True).order_by(MenuKantin.kategori, MenuKantin.nama).all()
        return jsonify({'success': True, 'data': [m.to_dict() for m in menu]})

    @app.route('/api/dashboard/stats', methods=['GET'])
    @jwt_required
    def api_dashboard_stats():
        return jsonify({'success': True, 'data': {
            'total_anggota': Anggota.query.count(),
            'kartu_aktif': Anggota.query.filter_by(status_kartu='Aktif').count(),
            'kartu_hilang': Anggota.query.filter_by(status_kartu='Hilang').count(),
            'total_saldo': db.session.query(db.func.coalesce(db.func.sum(Anggota.saldo), 0)).scalar(),
            'total_transaksi': Transaksi.query.count(),
        }})

    # ============================================================
    # MILI CARD INTEGRATION APIs
    # ============================================================

    @app.route('/api/anggota/<anggota_id>/update-card', methods=['PUT'])
    @jwt_admin_required
    def api_update_card_identifiers(anggota_id):
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            return jsonify({'success': False, 'message': 'Anggota tidak ditemukan'}), 404
        nfc_uid = data.get('nfc_uid', '').strip()
        qr_data = data.get('qr_data', '').strip()
        mili_id = data.get('mili_id', '').strip()
        if nfc_uid:
            existing = Anggota.query.filter(Anggota.nfc_uid == nfc_uid, Anggota.id != a.id).first()
            if existing:
                return jsonify({'success': False, 'message': f'NFC UID sudah dipakai oleh {existing.nama}'}), 400
            a.nfc_uid = nfc_uid
        if qr_data:
            existing = Anggota.query.filter(Anggota.qr_data == qr_data, Anggota.id != a.id).first()
            if existing:
                return jsonify({'success': False, 'message': f'QR data sudah dipakai oleh {existing.nama}'}), 400
            a.qr_data = qr_data
        if mili_id:
            existing = Anggota.query.filter(Anggota.mili_id == mili_id, Anggota.id != a.id).first()
            if existing:
                return jsonify({'success': False, 'message': f'MiLi ID sudah dipakai oleh {existing.nama}'}), 400
            a.mili_id = mili_id
        try:
            db.session.commit()
            return jsonify({'success': True, 'message': 'MiLi Card berhasil didaftarkan', 'data': {
                'kartu_id': a.kartu_id, 'nama': a.nama,
                'nfc_uid': a.nfc_uid, 'qr_data': a.qr_data, 'mili_id': a.mili_id,
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/anggota/<anggota_id>/update-location', methods=['POST'])
    @jwt_required
    def api_update_anggota_location(anggota_id):
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        a = Anggota.query.filter_by(kartu_id=anggota_id).first()
        if not a:
            return jsonify({'success': False, 'message': 'Anggota tidak ditemukan'}), 404
        lat = data.get('latitude')
        lng = data.get('longitude')
        lokasi_nama = data.get('lokasi_nama', 'GPS Update')
        sumber = data.get('sumber', 'GPS')
        if lat is None or lng is None:
            return jsonify({'success': False, 'message': 'latitude dan longitude required'}), 400
        try:
            a.lokasi_lat = float(lat)
            a.lokasi_lng = float(lng)
            a.lokasi_nama = lokasi_nama
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id,
                latitude=float(lat), longitude=float(lng),
                lokasi_nama=lokasi_nama, sumber=sumber,
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            return jsonify({'success': True, 'message': 'Location updated', 'data': {
                'kartu_id': a.kartu_id, 'nama': a.nama,
                'lokasi': {'lat': a.lokasi_lat, 'lng': a.lokasi_lng, 'nama': a.lokasi_nama},
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    # ============================================================
    # PRODUK & KATEGORI APIs
    # ============================================================

    @app.route('/api/kategori', methods=['GET'])
    @jwt_required
    def api_kategori_list():
        kategori = KategoriProduk.query.filter_by(is_active=True).order_by(KategoriProduk.urutan).all()
        return jsonify({'success': True, 'data': [k.to_dict() for k in kategori]})

    @app.route('/api/kategori', methods=['POST'])
    @jwt_admin_required
    def api_kategori_create():
        data = request.get_json()
        if not data or not data.get('nama'):
            return jsonify({'success': False, 'message': 'Nama kategori required'}), 400
        try:
            kategori = KategoriProduk(
                nama=data['nama'].strip(),
                icon=data.get('icon', 'bi-box'),
                urutan=data.get('urutan', 0),
            )
            db.session.add(kategori)
            db.session.commit()
            return jsonify({'success': True, 'data': kategori.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/kategori/<int:kategori_id>', methods=['PUT'])
    @jwt_admin_required
    def api_kategori_update(kategori_id):
        data = request.get_json()
        kategori = KategoriProduk.query.get(kategori_id)
        if not kategori:
            return jsonify({'success': False, 'message': 'Kategori tidak ditemukan'}), 404
        try:
            if data.get('nama'):
                kategori.nama = data['nama'].strip()
            if data.get('icon'):
                kategori.icon = data['icon']
            if 'urutan' in data:
                kategori.urutan = data['urutan']
            if 'is_active' in data:
                kategori.is_active = data['is_active']
            db.session.commit()
            return jsonify({'success': True, 'data': kategori.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/kategori/<int:kategori_id>', methods=['DELETE'])
    @jwt_admin_required
    def api_kategori_delete(kategori_id):
        kategori = KategoriProduk.query.get(kategori_id)
        if not kategori:
            return jsonify({'success': False, 'message': 'Kategori tidak ditemukan'}), 404
        if kategori.produk.count() > 0:
            return jsonify({'success': False, 'message': 'Kategori masih memiliki produk'}), 400
        try:
            db.session.delete(kategori)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Kategori berhasil dihapus'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/produk', methods=['GET'])
    @jwt_required
    def api_produk_list():
        kategori_id = request.args.get('kategori_id', type=int)
        search = request.args.get('search', '').strip()
        available_only = request.args.get('available', 'true').lower() == 'true'
        
        query = Produk.query
        if kategori_id:
            query = query.filter_by(kategori_id=kategori_id)
        if search:
            query = query.filter(db.or_(
                Produk.nama.ilike(f'%{search}%'),
                Produk.kode.ilike(f'%{search}%'),
            ))
        if available_only:
            query = query.filter_by(is_available=True).filter(Produk.stok > 0)
        
        produk = query.order_by(Produk.kategori_id, Produk.nama).all()
        return jsonify({'success': True, 'data': [p.to_dict() for p in produk]})

    @app.route('/api/produk/<int:produk_id>', methods=['GET'])
    @jwt_required
    def api_produk_detail(produk_id):
        produk = Produk.query.get(produk_id)
        if produk:
            return jsonify({'success': True, 'data': produk.to_dict()})
        return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404

    @app.route('/api/produk/kode/<kode>', methods=['GET'])
    @jwt_required
    def api_produk_by_kode(kode):
        produk = Produk.query.filter_by(kode=kode).first()
        if produk:
            return jsonify({'success': True, 'data': produk.to_dict()})
        return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404

    @app.route('/api/produk', methods=['POST'])
    @jwt_admin_required
    def api_produk_create():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        required = ['kode', 'nama', 'kategori_id', 'harga']
        for field in required:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'{field} required'}), 400
        
        if Produk.query.filter_by(kode=data['kode']).first():
            return jsonify({'success': False, 'message': 'Kode produk sudah digunakan'}), 400
        
        try:
            produk = Produk(
                kode=data['kode'].strip().upper(),
                nama=data['nama'].strip(),
                kategori_id=int(data['kategori_id']),
                harga=int(data['harga']),
                stok=int(data.get('stok', 0)),
                stok_minimum=int(data.get('stok_minimum', 5)),
                satuan=data.get('satuan', 'pcs'),
                deskripsi=data.get('deskripsi', ''),
            )
            db.session.add(produk)
            db.session.commit()
            return jsonify({'success': True, 'data': produk.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/produk/<int:produk_id>', methods=['PUT'])
    @jwt_admin_required
    def api_produk_update(produk_id):
        data = request.get_json()
        produk = Produk.query.get(produk_id)
        if not produk:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        try:
            if data.get('nama'):
                produk.nama = data['nama'].strip()
            if data.get('kategori_id'):
                produk.kategori_id = int(data['kategori_id'])
            if 'harga' in data:
                produk.harga = int(data['harga'])
            if 'stok' in data:
                produk.stok = int(data['stok'])
            if 'stok_minimum' in data:
                produk.stok_minimum = int(data['stok_minimum'])
            if data.get('satuan'):
                produk.satuan = data['satuan']
            if 'deskripsi' in data:
                produk.deskripsi = data['deskripsi']
            if 'is_available' in data:
                produk.is_available = data['is_available']
            db.session.commit()
            return jsonify({'success': True, 'data': produk.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/produk/<int:produk_id>/stok', methods=['PUT'])
    @jwt_admin_required
    def api_produk_update_stok(produk_id):
        """Quick stock update (add or set)"""
        data = request.get_json()
        produk = Produk.query.get(produk_id)
        if not produk:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        try:
            if data.get('mode') == 'add':
                produk.stok += int(data.get('jumlah', 0))
            else:
                produk.stok = int(data.get('stok', produk.stok))
            db.session.commit()
            return jsonify({'success': True, 'data': produk.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/produk/<int:produk_id>', methods=['DELETE'])
    @jwt_admin_required
    def api_produk_delete(produk_id):
        produk = Produk.query.get(produk_id)
        if not produk:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        try:
            db.session.delete(produk)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Produk berhasil dihapus'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    # ============================================================
    # PEMBAYARAN DENGAN CART (Supermarket Style)
    # ============================================================

    @app.route('/api/pembayaran/cart', methods=['POST'])
    @jwt_required
    def api_pembayaran_cart():
        """
        Pembayaran dengan cart items (produk)
        Body: { kartu_id, items: [{produk_id, jumlah}], metode }
        """
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        
        kartu_id = data.get('kartu_id', '').strip()
        items = data.get('items', [])
        metode = data.get('metode', 'Manual')
        
        if not kartu_id or not items:
            return jsonify({'success': False, 'message': 'kartu_id dan items required'}), 400
        
        anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
        if not anggota:
            return jsonify({'success': False, 'message': 'Anggota tidak ditemukan'}), 404
        if anggota.status_kartu != 'Aktif':
            return jsonify({'success': False, 'message': 'Kartu tidak aktif'}), 400
        
        # Calculate total and validate stock
        total = 0
        cart_items = []
        for item in items:
            produk = Produk.query.get(item.get('produk_id'))
            if not produk:
                return jsonify({'success': False, 'message': f'Produk ID {item.get("produk_id")} tidak ditemukan'}), 400
            jumlah = int(item.get('jumlah', 1))
            if produk.stok < jumlah:
                return jsonify({'success': False, 'message': f'Stok {produk.nama} tidak cukup (tersedia: {produk.stok})'}), 400
            subtotal = produk.harga * jumlah
            total += subtotal
            cart_items.append({
                'produk': produk,
                'jumlah': jumlah,
                'subtotal': subtotal,
            })
        
        if anggota.saldo < total:
            return jsonify({'success': False, 'message': f'Saldo tidak cukup. Total: Rp {total:,}, Saldo: Rp {anggota.saldo:,}'.replace(',', '.')}), 400
        
        try:
            saldo_sebelum = anggota.saldo
            anggota.saldo -= total
            
            # Create transaction
            keterangan = ', '.join([f"{c['produk'].nama} x{c['jumlah']}" for c in cart_items[:3]])
            if len(cart_items) > 3:
                keterangan += f' (+{len(cart_items) - 3} lainnya)'
            
            trx = Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Pembelian', keterangan=keterangan, nominal=total,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode=metode, operator_id=request.current_user_id,
            )
            db.session.add(trx)
            db.session.flush()  # Get trx.id
            
            # Create transaction items & reduce stock
            for c in cart_items:
                ti = TransaksiItem(
                    transaksi_id=trx.id,
                    produk_id=c['produk'].id,
                    nama_produk=c['produk'].nama,
                    harga_satuan=c['produk'].harga,
                    jumlah=c['jumlah'],
                    subtotal=c['subtotal'],
                )
                db.session.add(ti)
                c['produk'].stok -= c['jumlah']
            
            anggota.lokasi_nama = 'Kantin Poltekkad'
            anggota.lokasi_waktu = datetime.now()
            db.session.commit()
            
            return jsonify({'success': True, 'data': {
                'trx_id': trx.trx_id,
                'total': total,
                'item_count': len(cart_items),
                'saldo_sebelum': saldo_sebelum,
                'saldo_sesudah': anggota.saldo,
                'items': [{'nama': c['produk'].nama, 'jumlah': c['jumlah'], 'subtotal': c['subtotal']} for c in cart_items],
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    # ============================================================
    # AUTO PAY VIA NFC/QR TAP (Instant Payment)
    # ============================================================

    @app.route('/api/pembayaran/tap', methods=['POST'])
    @jwt_required
    def api_pembayaran_tap():
        """
        Pembayaran instant via NFC/QR tap
        Body: { scan_data, items: [{produk_id, jumlah}], metode: 'NFC'|'QR' }
        Langsung proses pembayaran tanpa perlu pilih anggota manual
        """
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        
        scan_data = data.get('scan_data', '').strip()
        items = data.get('items', [])
        metode = data.get('metode', 'NFC')
        
        if not scan_data:
            return jsonify({'success': False, 'message': 'scan_data required'}), 400
        
        # Find anggota by NFC/QR
        anggota = find_anggota_by_scan(scan_data, metode)
        if not anggota:
            return jsonify({'success': False, 'message': 'Kartu tidak terdaftar'}), 404
        if anggota.status_kartu != 'Aktif':
            return jsonify({'success': False, 'message': 'Kartu tidak aktif'}), 400
        
        # If no items, return anggota info (for pre-check)
        if not items:
            return jsonify({'success': True, 'data': {
                'anggota': {
                    'kartu_id': anggota.kartu_id,
                    'nama': anggota.nama,
                    'pangkat': anggota.pangkat,
                    'saldo': anggota.saldo,
                    'foto': anggota.foto,
                },
                'ready_to_pay': True,
            }})
        
        # Process payment with items
        total = 0
        cart_items = []
        for item in items:
            produk = Produk.query.get(item.get('produk_id'))
            if not produk:
                return jsonify({'success': False, 'message': f'Produk tidak ditemukan'}), 400
            jumlah = int(item.get('jumlah', 1))
            if produk.stok < jumlah:
                return jsonify({'success': False, 'message': f'Stok {produk.nama} tidak cukup'}), 400
            subtotal = produk.harga * jumlah
            total += subtotal
            cart_items.append({'produk': produk, 'jumlah': jumlah, 'subtotal': subtotal})
        
        if anggota.saldo < total:
            return jsonify({'success': False, 'message': f'Saldo tidak cukup', 'saldo': anggota.saldo, 'total': total}), 400
        
        try:
            saldo_sebelum = anggota.saldo
            anggota.saldo -= total
            
            keterangan = ', '.join([f"{c['produk'].nama} x{c['jumlah']}" for c in cart_items[:3]])
            if len(cart_items) > 3:
                keterangan += f' (+{len(cart_items) - 3} lainnya)'
            
            trx = Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Pembelian', keterangan=keterangan, nominal=total,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode=metode, operator_id=request.current_user_id,
            )
            db.session.add(trx)
            db.session.flush()
            
            for c in cart_items:
                db.session.add(TransaksiItem(
                    transaksi_id=trx.id, produk_id=c['produk'].id,
                    nama_produk=c['produk'].nama, harga_satuan=c['produk'].harga,
                    jumlah=c['jumlah'], subtotal=c['subtotal'],
                ))
                c['produk'].stok -= c['jumlah']
            
            anggota.lokasi_nama = 'Kantin Poltekkad'
            anggota.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=anggota.id, latitude=-6.8927, longitude=107.6100,
                lokasi_nama='Kantin Poltekkad', sumber=metode,
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            
            return jsonify({'success': True, 'data': {
                'trx_id': trx.trx_id,
                'anggota': {'kartu_id': anggota.kartu_id, 'nama': anggota.nama},
                'total': total,
                'saldo_sebelum': saldo_sebelum,
                'saldo_sesudah': anggota.saldo,
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    # ============================================================
    # AUTO TOPUP VIA NFC/QR TAP
    # ============================================================

    @app.route('/api/topup/tap', methods=['POST'])
    @jwt_admin_required
    def api_topup_tap():
        """
        Top up instant via NFC/QR tap
        Body: { scan_data, nominal, metode: 'NFC'|'QR' }
        """
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Request body required'}), 400
        
        scan_data = data.get('scan_data', '').strip()
        nominal = int(data.get('nominal', 0))
        metode = data.get('metode', 'NFC')
        
        if not scan_data:
            return jsonify({'success': False, 'message': 'scan_data required'}), 400
        
        # Find anggota by NFC/QR
        anggota = find_anggota_by_scan(scan_data, metode)
        if not anggota:
            return jsonify({'success': False, 'message': 'Kartu tidak terdaftar'}), 404
        
        # If no nominal, return anggota info (for pre-check)
        if nominal <= 0:
            return jsonify({'success': True, 'data': {
                'anggota': {
                    'kartu_id': anggota.kartu_id,
                    'nama': anggota.nama,
                    'pangkat': anggota.pangkat,
                    'saldo': anggota.saldo,
                    'foto': anggota.foto,
                },
                'ready_to_topup': True,
            }})
        
        if nominal > 5000000:
            return jsonify({'success': False, 'message': 'Maksimal Rp 5.000.000'}), 400
        
        try:
            saldo_sebelum = anggota.saldo
            anggota.saldo += nominal
            
            trx = Transaksi(
                trx_id=generate_trx_id(), anggota_id=anggota.id,
                jenis='Top Up', keterangan=f'Pengisian Saldo via {metode}', nominal=nominal,
                saldo_sebelum=saldo_sebelum, saldo_sesudah=anggota.saldo,
                status='Berhasil', metode=metode, operator_id=request.current_user_id,
            )
            db.session.add(trx)
            db.session.commit()
            
            return jsonify({'success': True, 'data': {
                'trx_id': trx.trx_id,
                'anggota': {'kartu_id': anggota.kartu_id, 'nama': anggota.nama},
                'nominal': nominal,
                'saldo_sebelum': saldo_sebelum,
                'saldo_sesudah': anggota.saldo,
            }})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/transaksi/<trx_id>/detail', methods=['GET'])
    @jwt_required
    def api_transaksi_detail(trx_id):
        """Get transaction with items detail"""
        trx = Transaksi.query.filter_by(trx_id=trx_id).first()
        if not trx:
            return jsonify({'success': False, 'message': 'Transaksi tidak ditemukan'}), 404
        return jsonify({'success': True, 'data': trx.to_dict(include_items=True)})


# ============================================================
# ERROR HANDLERS
# ============================================================

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Not found'}), 404
        flash('Halaman tidak ditemukan.', 'danger')
        return redirect(url_for('dashboard'))

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            return jsonify({'success': False, 'message': 'Server error'}), 500
        flash('Terjadi kesalahan server.', 'danger')
        return redirect(url_for('dashboard'))


# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app = create_app()

    # --- Aktifkan Google Find Hub Integration ---
    try:
        from findmy_service import FindMyLocationService, register_findmy_routes

        findmy = FindMyLocationService()
        findmy.init_app(app)
        register_findmy_routes(app, findmy)

        # Auto-update lokasi setiap 1 menit
        findmy.start_worker(interval=app.config.get('FINDMY_UPDATE_INTERVAL', 60))

        print("[FindMy] Google Find Hub integration aktif!")
        print(f"[FindMy] Tracker mapping: {len(app.config.get('FINDMY_TRACKER_MAP', {}))} device(s)")
        print("[FindMy] Auto-update lokasi setiap 1 menit.")
    except Exception as e:
        print(f"[FindMy] Integration tidak aktif: {e}")

    app.run(debug=True, host='0.0.0.0', port=5000)