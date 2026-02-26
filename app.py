"""
Kartu Pintar - Sistem Kartu Tanda Anggota Digital
TNI Angkatan Darat - Poltekkad
Flask Application
"""

from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from functools import wraps
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'kartu-pintar-secret-key-poltekkad-2025'

# ============================================================
# DUMMY DATA (Replace with database in production)
# ============================================================

USERS = {
    'admin': {
        'password': 'admin123',
        'role': 'admin',
        'nama': 'Administrator Poltekkad',
    },
    'user1': {
        'password': 'user123',
        'role': 'user',
        'nama': 'Serda Budi Santoso',
    }
}

ANGGOTA_DATA = [
    {
        'id': 'KP-2025-001',
        'nrp': '21250001',
        'nama': 'Serda Budi Santoso',
        'pangkat': 'Sersan Dua',
        'satuan': 'Poltekkad',
        'jabatan': 'Taruna Tingkat III',
        'jurusan': 'Teknik Elektronika',
        'tempat_lahir': 'Bandung',
        'tanggal_lahir': '15 Maret 2002',
        'golongan_darah': 'O',
        'agama': 'Islam',
        'alamat': 'Jl. Gatot Subroto No.96, Bandung',
        'foto': '/static/img/avatar-default.svg',
        'nfc_uid': 'A1B2C3D4',
        'qr_data': 'KP-2025-001',
        'saldo': 750000,
        'status_kartu': 'Aktif',
        'lokasi_terakhir': {'lat': -6.8927, 'lng': 107.6100, 'waktu': '2025-02-26 08:30:00', 'lokasi': 'Kantin Poltekkad'},
    },
    {
        'id': 'KP-2025-002',
        'nrp': '21250002',
        'nama': 'Praka Andi Wijaya',
        'pangkat': 'Prajurit Kepala',
        'satuan': 'Poltekkad',
        'jabatan': 'Taruna Tingkat II',
        'jurusan': 'Teknik Mesin',
        'tempat_lahir': 'Surabaya',
        'tanggal_lahir': '22 Juli 2003',
        'golongan_darah': 'A',
        'agama': 'Islam',
        'alamat': 'Jl. Pahlawan No.12, Surabaya',
        'foto': '/static/img/avatar-default.svg',
        'nfc_uid': 'E5F6G7H8',
        'qr_data': 'KP-2025-002',
        'saldo': 520000,
        'status_kartu': 'Aktif',
        'lokasi_terakhir': {'lat': -6.8930, 'lng': 107.6105, 'waktu': '2025-02-26 09:15:00', 'lokasi': 'Gedung Utama Poltekkad'},
    },
    {
        'id': 'KP-2025-003',
        'nrp': '21250003',
        'nama': 'Pratu Rizki Firmansyah',
        'pangkat': 'Prajurit Satu',
        'satuan': 'Poltekkad',
        'jabatan': 'Taruna Tingkat I',
        'jurusan': 'Teknik Informatika',
        'tempat_lahir': 'Jakarta',
        'tanggal_lahir': '10 Januari 2004',
        'golongan_darah': 'B',
        'agama': 'Kristen',
        'alamat': 'Jl. Merdeka No.45, Jakarta Selatan',
        'foto': '/static/img/avatar-default.svg',
        'nfc_uid': 'I9J0K1L2',
        'qr_data': 'KP-2025-003',
        'saldo': 310000,
        'status_kartu': 'Aktif',
        'lokasi_terakhir': {'lat': -6.8925, 'lng': 107.6098, 'waktu': '2025-02-26 07:45:00', 'lokasi': 'Asrama Poltekkad'},
    },
    {
        'id': 'KP-2025-004',
        'nrp': '21250004',
        'nama': 'Sertu Dewi Kartika',
        'pangkat': 'Sersan Satu',
        'satuan': 'Poltekkad',
        'jabatan': 'Staff Pengajar',
        'jurusan': 'Teknik Elektronika',
        'tempat_lahir': 'Yogyakarta',
        'tanggal_lahir': '05 September 2000',
        'golongan_darah': 'AB',
        'agama': 'Islam',
        'alamat': 'Jl. Malioboro No.78, Yogyakarta',
        'foto': '/static/img/avatar-default.svg',
        'nfc_uid': 'M3N4O5P6',
        'qr_data': 'KP-2025-004',
        'saldo': 980000,
        'status_kartu': 'Aktif',
        'lokasi_terakhir': {'lat': -6.8935, 'lng': 107.6110, 'waktu': '2025-02-26 10:00:00', 'lokasi': 'Ruang Kelas Poltekkad'},
    },
    {
        'id': 'KP-2025-005',
        'nrp': '21250005',
        'nama': 'Kopda Agus Prasetyo',
        'pangkat': 'Kopral Dua',
        'satuan': 'Poltekkad',
        'jabatan': 'Taruna Tingkat II',
        'jurusan': 'Teknik Mesin',
        'tempat_lahir': 'Semarang',
        'tanggal_lahir': '28 November 2003',
        'golongan_darah': 'O',
        'agama': 'Islam',
        'alamat': 'Jl. Pemuda No.33, Semarang',
        'foto': '/static/img/avatar-default.svg',
        'nfc_uid': 'Q7R8S9T0',
        'qr_data': 'KP-2025-005',
        'saldo': 150000,
        'status_kartu': 'Hilang',
        'lokasi_terakhir': {'lat': -6.8940, 'lng': 107.6095, 'waktu': '2025-02-25 16:30:00', 'lokasi': 'Lapangan Upacara Poltekkad'},
    },
]

TRANSAKSI_DATA = [
    {'id': 'TRX-001', 'anggota_id': 'KP-2025-001', 'nama': 'Serda Budi Santoso', 'jenis': 'Pembelian', 'keterangan': 'Makan Siang - Kantin', 'nominal': 25000, 'waktu': '2025-02-26 12:30:00', 'status': 'Berhasil'},
    {'id': 'TRX-002', 'anggota_id': 'KP-2025-002', 'nama': 'Praka Andi Wijaya', 'jenis': 'Pembelian', 'keterangan': 'Minuman - Kantin', 'nominal': 8000, 'waktu': '2025-02-26 10:15:00', 'status': 'Berhasil'},
    {'id': 'TRX-003', 'anggota_id': 'KP-2025-001', 'nama': 'Serda Budi Santoso', 'jenis': 'Top Up', 'keterangan': 'Pengisian Saldo', 'nominal': 500000, 'waktu': '2025-02-25 08:00:00', 'status': 'Berhasil'},
    {'id': 'TRX-004', 'anggota_id': 'KP-2025-003', 'nama': 'Pratu Rizki Firmansyah', 'jenis': 'Pembelian', 'keterangan': 'Snack - Kantin', 'nominal': 15000, 'waktu': '2025-02-26 09:45:00', 'status': 'Berhasil'},
    {'id': 'TRX-005', 'anggota_id': 'KP-2025-004', 'nama': 'Sertu Dewi Kartika', 'jenis': 'Top Up', 'keterangan': 'Pengisian Saldo', 'nominal': 300000, 'waktu': '2025-02-24 14:00:00', 'status': 'Berhasil'},
    {'id': 'TRX-006', 'anggota_id': 'KP-2025-005', 'nama': 'Kopda Agus Prasetyo', 'jenis': 'Pembelian', 'keterangan': 'Makan Pagi - Kantin', 'nominal': 20000, 'waktu': '2025-02-26 07:00:00', 'status': 'Gagal'},
]

# ============================================================
# AUTH DECORATOR
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================
# AUTH ROUTES
# ============================================================

@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username in USERS and USERS[username]['password'] == password:
            session['user'] = username
            session['role'] = USERS[username]['role']
            session['nama'] = USERS[username]['nama']
            flash(f'Selamat datang, {USERS[username]["nama"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'info')
    return redirect(url_for('login'))

# ============================================================
# DASHBOARD
# ============================================================

@app.route('/dashboard')
@login_required
def dashboard():
    total_anggota = len(ANGGOTA_DATA)
    kartu_aktif = len([a for a in ANGGOTA_DATA if a['status_kartu'] == 'Aktif'])
    kartu_hilang = len([a for a in ANGGOTA_DATA if a['status_kartu'] == 'Hilang'])
    total_saldo = sum(a['saldo'] for a in ANGGOTA_DATA)
    total_transaksi = len(TRANSAKSI_DATA)
    transaksi_terbaru = sorted(TRANSAKSI_DATA, key=lambda x: x['waktu'], reverse=True)[:5]

    return render_template('dashboard.html',
        total_anggota=total_anggota,
        kartu_aktif=kartu_aktif,
        kartu_hilang=kartu_hilang,
        total_saldo=total_saldo,
        total_transaksi=total_transaksi,
        transaksi_terbaru=transaksi_terbaru,
        anggota_data=ANGGOTA_DATA[:5]
    )

# ============================================================
# ANGGOTA (Member) ROUTES
# ============================================================

@app.route('/anggota')
@login_required
def anggota_list():
    return render_template('anggota_list.html', anggota_data=ANGGOTA_DATA)

@app.route('/anggota/<anggota_id>')
@login_required
def anggota_detail(anggota_id):
    anggota = next((a for a in ANGGOTA_DATA if a['id'] == anggota_id), None)
    if not anggota:
        flash('Data anggota tidak ditemukan.', 'danger')
        return redirect(url_for('anggota_list'))
    transaksi = [t for t in TRANSAKSI_DATA if t['anggota_id'] == anggota_id]
    return render_template('anggota_detail.html', anggota=anggota, transaksi=transaksi)

@app.route('/anggota/tambah', methods=['GET', 'POST'])
@admin_required
def anggota_tambah():
    if request.method == 'POST':
        flash('Data anggota berhasil ditambahkan! (Demo)', 'success')
        return redirect(url_for('anggota_list'))
    return render_template('admin/anggota_form.html', mode='tambah')

@app.route('/anggota/edit/<anggota_id>', methods=['GET', 'POST'])
@admin_required
def anggota_edit(anggota_id):
    anggota = next((a for a in ANGGOTA_DATA if a['id'] == anggota_id), None)
    if not anggota:
        flash('Data anggota tidak ditemukan.', 'danger')
        return redirect(url_for('anggota_list'))
    if request.method == 'POST':
        flash('Data anggota berhasil diperbarui! (Demo)', 'success')
        return redirect(url_for('anggota_detail', anggota_id=anggota_id))
    return render_template('admin/anggota_form.html', mode='edit', anggota=anggota)

# ============================================================
# SCAN NFC & QR
# ============================================================

@app.route('/scan')
@login_required
def scan_page():
    return render_template('scan.html')

@app.route('/scan/result/<card_id>')
@login_required
def scan_result(card_id):
    anggota = next((a for a in ANGGOTA_DATA if a['qr_data'] == card_id or a['nfc_uid'] == card_id), None)
    if not anggota:
        flash('Kartu tidak terdaftar dalam sistem.', 'danger')
        return redirect(url_for('scan_page'))
    return render_template('scan_result.html', anggota=anggota)

# ============================================================
# PEMBAYARAN (Payment)
# ============================================================

@app.route('/pembayaran')
@login_required
def pembayaran():
    return render_template('pembayaran.html', anggota_data=ANGGOTA_DATA)

@app.route('/pembayaran/proses', methods=['POST'])
@login_required
def pembayaran_proses():
    flash('Pembayaran berhasil diproses! (Demo)', 'success')
    return redirect(url_for('pembayaran'))

# ============================================================
# TOP UP SALDO
# ============================================================

@app.route('/topup')
@admin_required
def topup():
    return render_template('admin/topup.html', anggota_data=ANGGOTA_DATA)

@app.route('/topup/proses', methods=['POST'])
@admin_required
def topup_proses():
    flash('Top up saldo berhasil! (Demo)', 'success')
    return redirect(url_for('topup'))

# ============================================================
# LACAK KARTU (Track Card)
# ============================================================

@app.route('/lacak')
@login_required
def lacak_kartu():
    return render_template('lacak_kartu.html', anggota_data=ANGGOTA_DATA)

# ============================================================
# TRANSAKSI (Transactions)
# ============================================================

@app.route('/transaksi')
@login_required
def transaksi():
    return render_template('transaksi.html', transaksi_data=TRANSAKSI_DATA)

# ============================================================
# API ENDPOINTS (for AJAX)
# ============================================================

@app.route('/api/anggota/<anggota_id>')
@login_required
def api_anggota_detail(anggota_id):
    anggota = next((a for a in ANGGOTA_DATA if a['id'] == anggota_id), None)
    if anggota:
        return jsonify(anggota)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/scan/nfc/<nfc_uid>')
@login_required
def api_scan_nfc(nfc_uid):
    anggota = next((a for a in ANGGOTA_DATA if a['nfc_uid'] == nfc_uid), None)
    if anggota:
        return jsonify({'success': True, 'data': anggota})
    return jsonify({'success': False, 'message': 'Kartu NFC tidak terdaftar'}), 404

@app.route('/api/scan/qr/<qr_data>')
@login_required
def api_scan_qr(qr_data):
    anggota = next((a for a in ANGGOTA_DATA if a['qr_data'] == qr_data), None)
    if anggota:
        return jsonify({'success': True, 'data': anggota})
    return jsonify({'success': False, 'message': 'QR Code tidak valid'}), 404

# ============================================================
# TEMPLATE FILTERS
# ============================================================

@app.template_filter('rupiah')
def rupiah_format(value):
    return f"Rp {value:,.0f}".replace(",", ".")

@app.template_filter('datetime_format')
def datetime_format_filter(value, fmt='%d %b %Y, %H:%M'):
    try:
        dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime(fmt)
    except:
        return value

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# ============================================================
# RUN
# ============================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
