"""
Kartu Pintar - Google Find Hub Location Service
================================================

⚠️  PATCHED VERSION — Fix auto-update tracker tidak jalan di Gunicorn.
    Perubahan utama:
      1. File-lock leader election — saat gunicorn pakai --workers 4, cuma
         SATU worker yang beneran jalanin loop update. Mencegah spam Google API.
      2. Status tracking (`last_run`, `last_error`, `run_count`) bisa dibaca
         dari endpoint /api/findmy/worker-status untuk monitoring dari UI.
      3. Logging pakai print() + flush=True biar langsung muncul di
         docker logs / gunicorn stdout (logger kadang di-swallow).
      4. Context-manager untuk thread lifecycle (graceful shutdown).

SETUP:
1. cd kartu-pintar
2. git clone https://github.com/leonboe1/GoogleFindMyTools.git findmy_tools
3. pip install -r findmy_tools/requirements.txt
4. python findmy_tools/main.py   (login Google pertama kali, butuh Chrome)
5. Tambah tracker di Admin Panel → Monitoring → FindMy Trackers
6. Aktifkan di app.py (lihat bawah file ini)

CATATAN:
- Hanya bisa jalan di server/komputer (butuh Chrome untuk auth pertama kali)
- Lokasi tidak real-time (delay 1-15 menit tergantung kepadatan Android)
- E2EE encrypted — hanya akun owner yang bisa decrypt
"""

import sys
import os
import time
import hashlib
import logging
import traceback
from datetime import datetime
from threading import Thread, Lock

FINDMY_TOOLS_PATH = os.path.join(os.path.dirname(__file__), 'findmy_tools')
if FINDMY_TOOLS_PATH not in sys.path:
    sys.path.insert(0, FINDMY_TOOLS_PATH)

logger = logging.getLogger('findmy_service')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s [%(levelname)s]: %(message)s'))
    logger.addHandler(handler)


def _log(msg, level='info'):
    """Log + print (print dengan flush jadi pasti muncul di docker logs)."""
    getattr(logger, level)(msg)
    try:
        print(f"[FindMy] {msg}", flush=True)
    except Exception:
        pass


# ============================================================
# LEADER ELECTION — pastikan cuma 1 gunicorn worker yang jalanin loop
# ============================================================
# Kenapa perlu: Gunicorn `--workers 4` bikin 4 proses paralel.
# Kalau tiap proses jalanin FindMy loop, Google API akan kena spam 4x/menit
# dan bisa kena throttle/ban. Kita pakai fcntl.flock() buat election:
# proses pertama yang dapat lock = leader. Sisanya skip worker loop.

_LEADER_LOCK_PATH = os.environ.get(
    'FINDMY_LEADER_LOCK',
    '/tmp/kartu_pintar_findmy_leader.lock'
)
_leader_lock_fd = None  # Must stay open selama proses hidup!


def acquire_leader_lock():
    """
    Try to acquire exclusive flock on the leader lock file.
    Returns True if this process becomes the leader, False otherwise.
    The file descriptor is kept open in a module-level var — closing
    it (or process exit) will release the lock automatically.
    """
    global _leader_lock_fd

    if _leader_lock_fd is not None:
        return True  # Already leader

    # fcntl only works on Unix — skip election on Windows (assume single-proc)
    try:
        import fcntl
    except ImportError:
        _log("fcntl not available (Windows?) — skipping leader election, assuming single process")
        _leader_lock_fd = -1  # sentinel: "we didn't use a real lock but we're the leader"
        return True

    try:
        fd = os.open(_LEADER_LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Write pid for debugging
        os.write(fd, f"{os.getpid()}\n".encode())
        _leader_lock_fd = fd
        _log(f"Acquired leader lock (pid={os.getpid()}, file={_LEADER_LOCK_PATH})")
        return True
    except (BlockingIOError, OSError) as e:
        _log(f"Not the leader (pid={os.getpid()}): {e} — skipping worker loop")
        try:
            os.close(fd)
        except Exception:
            pass
        return False


# ============================================================
# SERVICE
# ============================================================

class FindMyLocationService:

    def __init__(self, app=None):
        self.app = app
        self._running = False
        self._thread = None
        self._tools = None
        self._status_lock = Lock()
        self._status = {
            'started_at': None,
            'is_leader': False,
            'last_run_at': None,
            'last_run_success': None,
            'last_error': None,
            'run_count': 0,
            'success_count': 0,
            'error_count': 0,
            'trackers_updated_last_run': 0,
            'interval_seconds': 60,
        }

    def init_app(self, app):
        self.app = app
        _log("FindMy service initialized (reading trackers from database)")

    # --- Status API ---

    def get_status(self):
        with self._status_lock:
            s = dict(self._status)
        s['is_running'] = self._running
        s['tools_loaded'] = self._tools is not None
        s['pid'] = os.getpid()
        # Serialize datetime
        for k in ('started_at', 'last_run_at'):
            if s.get(k):
                s[k] = s[k].strftime('%Y-%m-%d %H:%M:%S')
        return s

    def _update_status(self, **kwargs):
        with self._status_lock:
            self._status.update(kwargs)

    # --- Tracker map ---

    def _get_tracker_map(self):
        """Get tracker mapping from database: { canonical_id: kartu_id }"""
        if not self.app:
            return {}

        with self.app.app_context():
            from models import FindMyTracker
            trackers = FindMyTracker.query.filter_by(is_active=True).all()
            return {t.canonical_id: t.anggota.kartu_id for t in trackers if t.anggota}

    def _load_tools(self):
        """Lazy import GoogleFindMyTools."""
        if self._tools:
            return self._tools

        try:
            from NovaApi.ListDevices.nbe_list_devices import request_device_list
            from NovaApi.ExecuteAction.LocateTracker.location_request import create_location_request
            from NovaApi.ExecuteAction.LocateTracker.decrypt_locations import (
                retrieve_identity_key, is_mcu_tracker
            )
            from NovaApi.nova_request import nova_request
            from NovaApi.scopes import NOVA_ACTION_API_SCOPE
            from NovaApi.util import generate_random_uuid
            from ProtoDecoders.decoder import (
                parse_device_list_protobuf, get_canonic_ids,
                parse_device_update_protobuf
            )
            from ProtoDecoders import DeviceUpdate_pb2, Common_pb2
            from Auth.fcm_receiver import FcmReceiver
            from FMDNCrypto.foreign_tracker_cryptor import decrypt as fmdn_decrypt
            from KeyBackup.cloud_key_decryptor import decrypt_eik, decrypt_aes_gcm
            from SpotApi.UploadPrecomputedPublicKeyIds.upload_precomputed_public_key_ids import refresh_custom_trackers

            self._tools = {
                'request_device_list': request_device_list,
                'get_canonic_ids': get_canonic_ids,
                'parse_device_list_protobuf': parse_device_list_protobuf,
                'parse_device_update_protobuf': parse_device_update_protobuf,
                'create_location_request': create_location_request,
                'nova_request': nova_request,
                'NOVA_ACTION_API_SCOPE': NOVA_ACTION_API_SCOPE,
                'generate_random_uuid': generate_random_uuid,
                'DeviceUpdate_pb2': DeviceUpdate_pb2,
                'Common_pb2': Common_pb2,
                'FcmReceiver': FcmReceiver,
                'retrieve_identity_key': retrieve_identity_key,
                'is_mcu_tracker': is_mcu_tracker,
                'fmdn_decrypt': fmdn_decrypt,
                'decrypt_aes_gcm': decrypt_aes_gcm,
                'refresh_custom_trackers': refresh_custom_trackers,
            }
            _log("GoogleFindMyTools loaded successfully")
            return self._tools
        except ImportError as e:
            _log(f"Cannot import GoogleFindMyTools: {e}", 'error')
            _log(f"  → Make sure findmy_tools/ exists at: {FINDMY_TOOLS_PATH}", 'error')
            _log(f"  → And deps installed: pip install -r findmy_tools/requirements.txt", 'error')
            self._update_status(last_error=f"ImportError: {e}")
            return None

    def list_trackers(self):
        """List semua tracker dari akun Google."""
        tools = self._load_tools()
        if not tools:
            return []

        tracker_map = self._get_tracker_map()

        try:
            result_hex = tools['request_device_list']()
            device_list = tools['parse_device_list_protobuf'](result_hex)
            tools['refresh_custom_trackers'](device_list)
            canonic_ids = tools['get_canonic_ids'](device_list)

            return [{
                'device_name': name,
                'canonic_id': cid,
                'kartu_id': tracker_map.get(cid, 'UNMAPPED'),
            } for name, cid in canonic_ids]
        except Exception as e:
            _log(f"Error listing trackers: {e}", 'error')
            _log(traceback.format_exc(), 'error')
            return []

    def get_location(self, canonic_device_id, device_name="Tracker"):
        """Request & decrypt lokasi satu tracker."""
        tools = self._load_tools()
        if not tools:
            return []

        try:
            _log(f"Requesting location for {device_name}...")

            result = None
            request_uuid = tools['generate_random_uuid']()

            def handle_response(response):
                nonlocal result
                du = tools['parse_device_update_protobuf'](response)
                if du.fcmMetadata.requestUuid == request_uuid:
                    result = du

            fcm_token = tools['FcmReceiver']().register_for_location_updates(handle_response)
            hex_payload = tools['create_location_request'](canonic_device_id, fcm_token, request_uuid)
            tools['nova_request'](tools['NOVA_ACTION_API_SCOPE'], hex_payload)

            # Wait max 30s
            start = time.time()
            while result is None and (time.time() - start) < 30:
                time.sleep(0.1)

            if result is None:
                _log(f"Timeout waiting for location response: {device_name}", 'warning')
                return []

            return self._decrypt_locations(result, tools)
        except Exception as e:
            _log(f"Error getting location for {device_name}: {e}", 'error')
            _log(traceback.format_exc(), 'error')
            return []

    def _decrypt_locations(self, device_update, tools):
        """Decrypt E2EE location data."""
        locations = []
        try:
            device_reg = device_update.deviceMetadata.information.deviceRegistration
            identity_key = tools['retrieve_identity_key'](device_reg)
            is_mcu = tools['is_mcu_tracker'](device_reg)

            loc_reports = device_update.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
            network_locs = list(loc_reports.networkLocations)
            network_times = list(loc_reports.networkLocationTimestamps)

            if loc_reports.HasField("recentLocation"):
                network_locs.append(loc_reports.recentLocation)
                network_times.append(loc_reports.recentLocationTimestamp)

            for loc, loc_time in zip(network_locs, network_times):
                try:
                    if loc.status == tools['Common_pb2'].Status.SEMANTIC:
                        continue  # Skip semantic locations

                    enc_loc = loc.geoLocation.encryptedReport.encryptedLocation
                    pub_key = loc.geoLocation.encryptedReport.publicKeyRandom

                    if pub_key == b"":
                        ik_hash = hashlib.sha256(identity_key).digest()
                        dec_loc = tools['decrypt_aes_gcm'](ik_hash, enc_loc)
                    else:
                        time_offset = 0 if is_mcu else loc.geoLocation.deviceTimeOffset
                        dec_loc = tools['fmdn_decrypt'](identity_key, enc_loc, pub_key, time_offset)

                    proto_loc = tools['DeviceUpdate_pb2'].Location()
                    proto_loc.ParseFromString(dec_loc)

                    locations.append({
                        'latitude': proto_loc.latitude / 1e7,
                        'longitude': proto_loc.longitude / 1e7,
                        'altitude': proto_loc.altitude,
                        'accuracy': loc.geoLocation.accuracy,
                        'timestamp': datetime.fromtimestamp(int(loc_time.seconds)),
                        'source': 'GoogleFindHub',
                    })
                except Exception as inner:
                    _log(f"Skipping one location due to decrypt error: {inner}", 'warning')
                    continue
        except Exception as e:
            _log(f"Decrypt locations failed: {e}", 'error')
            _log(traceback.format_exc(), 'error')
        return locations

    def update_all_locations(self):
        """Fetch lokasi semua tracker, update database. Returns jumlah tracker ter-update."""
        if not self.app:
            return 0

        tracker_map = self._get_tracker_map()
        if not tracker_map:
            _log("No trackers configured in database (skip this cycle)")
            return 0

        updated_count = 0
        with self.app.app_context():
            from models import db, Anggota, LokasiHistory, FindMyTracker

            for tracker in self.list_trackers():
                if tracker['kartu_id'] == 'UNMAPPED':
                    continue

                anggota = Anggota.query.filter_by(kartu_id=tracker['kartu_id']).first()
                if not anggota:
                    continue

                locs = self.get_location(tracker['canonic_id'], tracker['device_name'])
                geo_locs = [l for l in locs if l.get('latitude')]
                if not geo_locs:
                    _log(f"No geo locations returned for {tracker['device_name']}", 'warning')
                    continue

                latest = max(geo_locs, key=lambda l: l['timestamp'])

                # Update Anggota lokasi terakhir
                anggota.lokasi_lat = latest['latitude']
                anggota.lokasi_lng = latest['longitude']
                anggota.lokasi_nama = f"GPS via Find Hub (±{latest.get('accuracy', '?')}m)"
                anggota.lokasi_waktu = latest['timestamp']

                # Update FindMyTracker record
                findmy_tracker = FindMyTracker.query.filter_by(canonical_id=tracker['canonic_id']).first()
                if findmy_tracker:
                    findmy_tracker.last_seen = latest['timestamp']
                    findmy_tracker.last_latitude = latest['latitude']
                    findmy_tracker.last_longitude = latest['longitude']

                # Add to history
                for loc in geo_locs:
                    db.session.add(LokasiHistory(
                        anggota_id=anggota.id,
                        latitude=loc['latitude'],
                        longitude=loc['longitude'],
                        lokasi_nama='GPS via Find Hub',
                        sumber='GoogleFindHub',
                    ))

                db.session.commit()
                updated_count += 1
                _log(f"Updated {anggota.nama}: {latest['latitude']:.6f}, {latest['longitude']:.6f}")

        return updated_count

    # --- Worker lifecycle ---

    def start_worker(self, interval=60, require_leader=True):
        """
        Background thread: fetch lokasi tiap N detik.

        require_leader=True (default) → pakai file lock supaya cuma 1 proses
        yang jalanin worker. Set False kalau kamu pakai service terpisah
        (mis. `findmy_worker.py`) dan sudah yakin cuma 1 instance.
        """
        if self._running:
            _log("Worker already running, skip start")
            return False

        if require_leader:
            if not acquire_leader_lock():
                _log(f"This process (pid={os.getpid()}) is not the leader — worker not started")
                self._update_status(is_leader=False)
                return False
            self._update_status(is_leader=True)
        else:
            self._update_status(is_leader=True)

        self._running = True
        self._update_status(
            started_at=datetime.now(),
            interval_seconds=interval,
        )

        def worker():
            _log(f"⚡ Background worker started (interval={interval}s, pid={os.getpid()})")
            # Warm-up: load tools once so first failure shows up immediately
            self._load_tools()

            while self._running:
                cycle_start = time.time()
                try:
                    count = self.update_all_locations()
                    self._update_status(
                        last_run_at=datetime.now(),
                        last_run_success=True,
                        last_error=None,
                        run_count=self._status['run_count'] + 1,
                        success_count=self._status['success_count'] + 1,
                        trackers_updated_last_run=count,
                    )
                except Exception as e:
                    err = f"{type(e).__name__}: {e}"
                    _log(f"Worker cycle error: {err}", 'error')
                    _log(traceback.format_exc(), 'error')
                    self._update_status(
                        last_run_at=datetime.now(),
                        last_run_success=False,
                        last_error=err,
                        run_count=self._status['run_count'] + 1,
                        error_count=self._status['error_count'] + 1,
                    )

                # Sleep respecting interval minus time already spent, min 5s
                elapsed = time.time() - cycle_start
                sleep_for = max(5, interval - elapsed)
                # Break sleep into 1s chunks so stop_worker() responds quickly
                for _ in range(int(sleep_for)):
                    if not self._running:
                        break
                    time.sleep(1)

            _log("Worker loop exited")

        self._thread = Thread(target=worker, daemon=True, name='findmy-worker')
        self._thread.start()
        return True

    def stop_worker(self):
        self._running = False
        _log("Worker stop requested")


# ============================================================
# ROUTES — only non-conflicting ones (app.py already has some)
# ============================================================

def register_findmy_routes(app, findmy_service):
    """
    API routes untuk FindMy integration.

    ⚠️  PATCHED: Route `/api/findmy/trackers` dan `/api/findmy/update-location`
    sudah ada di app.py → SKIP biar gak `AssertionError: overwriting endpoint`.
    Cuma daftarkan yang belum ada + tambah status endpoint baru.
    """
    from flask import jsonify, request
    from functools import wraps

    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import session
            if not session.get('user_id'):
                return jsonify({'success': False, 'message': 'Login required'}), 401
            from models import User
            user = User.query.get(session['user_id'])
            if not user or user.role != 'admin':
                return jsonify({'success': False, 'message': 'Admin only'}), 403
            return f(*args, **kwargs)
        return decorated

    # Helper: register route only if endpoint name isn't taken yet
    def safe_route(rule, endpoint, view_func, **opts):
        if endpoint in app.view_functions:
            _log(f"  Route {rule} ({endpoint}) already exists — skip")
            return
        app.add_url_rule(rule, endpoint=endpoint, view_func=view_func, **opts)

    @admin_required
    def api_findmy_google_trackers():
        """List all trackers from Google account (independent of DB mapping)."""
        try:
            return jsonify({'success': True, 'data': findmy_service.list_trackers()})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @admin_required
    def api_findmy_locate(kartu_id):
        """Request fresh location for specific card (on-demand, bypass worker)."""
        from models import FindMyTracker, Anggota

        anggota = Anggota.query.filter_by(kartu_id=kartu_id).first()
        if not anggota:
            return jsonify({'success': False, 'message': f'Anggota {kartu_id} not found'}), 404

        tracker = FindMyTracker.query.filter_by(anggota_id=anggota.id, is_active=True).first()
        if not tracker:
            return jsonify({'success': False, 'message': f'No tracker mapped to {kartu_id}'}), 404

        locs = findmy_service.get_location(tracker.canonical_id, kartu_id)
        return jsonify({'success': True, 'data': [{
            'latitude': l['latitude'], 'longitude': l['longitude'],
            'timestamp': l['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'accuracy': l.get('accuracy'),
        } for l in locs if l.get('latitude')]})

    @admin_required
    def api_findmy_update_all():
        """Force worker run NOW (button di UI)."""
        try:
            count = findmy_service.update_all_locations()
            return jsonify({'success': True, 'message': f'Updated {count} tracker(s)', 'updated': count})
        except Exception as e:
            _log(f"update-all API error: {e}", 'error')
            return jsonify({'success': False, 'message': str(e)}), 500

    @admin_required
    def api_findmy_worker_status():
        """Status worker — supaya UI bisa tampilkan indikator hidup/mati."""
        return jsonify({'success': True, 'data': findmy_service.get_status()})

    safe_route('/api/findmy/google-trackers', 'api_findmy_google_trackers',
               api_findmy_google_trackers, methods=['GET'])
    safe_route('/api/findmy/locate/<kartu_id>', 'api_findmy_locate',
               api_findmy_locate, methods=['POST'])
    safe_route('/api/findmy/update-all', 'api_findmy_update_all',
               api_findmy_update_all, methods=['POST'])
    safe_route('/api/findmy/worker-status', 'api_findmy_worker_status',
               api_findmy_worker_status, methods=['GET'])

    _log("FindMy API routes registered (google-trackers, locate, update-all, worker-status)")


# ============================================================
# CARA AKTIVASI DI app.py (SUDAH DIPATCH — lihat bagian bawah app.py):
# ============================================================
#
# Tidak perlu lagi ditaruh di dalam `if __name__ == '__main__':`
# karena itu bug utamanya — gunicorn gak pernah masuk blok itu.
# Sekarang inisialisasi dilakukan di level module supaya gunicorn juga ikut.
#
# Kelola tracker via Admin Panel → Monitoring → FindMy Trackers
