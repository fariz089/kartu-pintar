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
from models import db, User, Anggota, Transaksi, LokasiHistory, MenuKantin


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
        anggota_raw = Anggota.query.filter_by(status_kartu='Aktif').all()
        anggota_data = [{
            'id': a.kartu_id, 'nrp': a.nrp, 'nama': a.nama,
            'pangkat': a.pangkat, 'saldo': a.saldo,
            'nfc_uid': a.nfc_uid, 'qr_data': a.qr_data, 'foto': a.foto,
            'status_kartu': a.status_kartu,
        } for a in anggota_raw]
        # Recent payment transactions for sidebar
        trx_raw = Transaksi.query.filter_by(jenis='Pembelian').order_by(Transaksi.created_at.desc()).limit(5).all()
        transaksi_terbaru = [trx_to_dict(t) for t in trx_raw]
        return render_template('pembayaran.html', anggota_data=anggota_data, transaksi_terbaru=transaksi_terbaru)

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

    # --- LACAK KARTU ---

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

    # --- TRANSAKSI (role-based) ---

    @app.route('/transaksi')
    @login_required
    def transaksi():
        role = session.get('role')
        if role == 'user':
            # User: only own transactions (linked through anggota)
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
            # Operator: only Pembelian (sales)
            all_trx = Transaksi.query.filter_by(jenis='Pembelian').order_by(Transaksi.created_at.desc()).all()
            return render_template('transaksi.html',
                transaksi_data=[trx_to_dict(t) for t in all_trx],
                page_title='Riwayat Penjualan Kantin')
        else:
            # Admin: all transactions
            all_trx = Transaksi.query.order_by(Transaksi.created_at.desc()).all()
            return render_template('transaksi.html',
                transaksi_data=[trx_to_dict(t) for t in all_trx],
                page_title='Riwayat Transaksi')


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
        """Get current user info from token"""
        user = User.query.get(request.current_user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        user_data = user.to_dict()
        if user.anggota:
            user_data['anggota'] = user.anggota.to_dict()
        return jsonify({'success': True, 'data': user_data})

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

    @app.route('/api/scan/nfc/<nfc_uid>', methods=['GET'])
    @jwt_required
    def api_scan_nfc(nfc_uid):
        a = Anggota.query.filter_by(nfc_uid=nfc_uid).first()
        if a:
            a.lokasi_waktu = datetime.now()
            db.session.add(LokasiHistory(
                anggota_id=a.id, latitude=a.lokasi_lat or -6.8927,
                longitude=a.lokasi_lng or 107.6100,
                lokasi_nama='NFC Scan', sumber='NFC',
                scanned_by_user_id=request.current_user_id,
            ))
            db.session.commit()
            # User role: limited info (no saldo)
            if getattr(request, 'current_role', None) == 'user':
                return jsonify({'success': True, 'data': a.to_identitas_dict()})
            return jsonify({'success': True, 'data': a.to_dict()})
        return jsonify({'success': False, 'message': 'Kartu NFC tidak terdaftar'}), 404

    @app.route('/api/scan/qr/<qr_data>', methods=['GET'])
    @jwt_required
    def api_scan_qr(qr_data):
        a = Anggota.query.filter(
            db.or_(Anggota.qr_data == qr_data, Anggota.kartu_id == qr_data)
        ).first()
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
        query = Transaksi.query
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

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
