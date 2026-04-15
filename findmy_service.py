"""
Kartu Pintar - Google Find Hub Location Service
================================================

SETUP:
1. cd kartu-pintar
2. git clone https://github.com/leonboe1/GoogleFindMyTools.git findmy_tools
3. pip install -r findmy_tools/requirements.txt
4. python findmy_tools/main.py   (login Google pertama kali, butuh Chrome)
5. Tambah tracker di Admin Panel → Monitoring → FindMy Trackers
6. Aktifkan di app.py (lihat bawah file ini)

PERUBAHAN:
- Tracker mapping sekarang baca dari database (tabel findmy_tracker)
- Tidak perlu hardcode FINDMY_TRACKER_MAP di config.py lagi
- Kelola tracker via Admin Panel

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
from datetime import datetime
from threading import Thread

FINDMY_TOOLS_PATH = os.path.join(os.path.dirname(__file__), 'findmy_tools')
if FINDMY_TOOLS_PATH not in sys.path:
    sys.path.insert(0, FINDMY_TOOLS_PATH)

logger = logging.getLogger('findmy_service')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s: %(message)s'))
logger.addHandler(handler)


class FindMyLocationService:

    def __init__(self, app=None):
        self.app = app
        self._running = False
        self._thread = None
        self._tools = None

    def init_app(self, app):
        self.app = app
        logger.info("FindMy service initialized (reading trackers from database)")

    def _get_tracker_map(self):
        """Get tracker mapping from database: { canonical_id: kartu_id }"""
        if not self.app:
            return {}
        
        with self.app.app_context():
            from models import FindMyTracker
            trackers = FindMyTracker.query.filter_by(is_active=True).all()
            return {t.canonical_id: t.anggota.kartu_id for t in trackers if t.anggota}

    def _load_tools(self):
        """Lazy import GoogleFindMyTools"""
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
            logger.info("GoogleFindMyTools loaded successfully")
            return self._tools
        except ImportError as e:
            logger.error(f"Cannot import GoogleFindMyTools: {e}")
            logger.error(f"Make sure it's cloned at: {FINDMY_TOOLS_PATH}")
            return None

    def list_trackers(self):
        """List semua tracker dari akun Google"""
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
            logger.error(f"Error listing trackers: {e}")
            return []

    def get_location(self, canonic_device_id, device_name="Tracker"):
        """Request & decrypt lokasi satu tracker"""
        tools = self._load_tools()
        if not tools:
            return []

        try:
            logger.info(f"Requesting location for {device_name}...")

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
                logger.warning(f"Timeout for {device_name}")
                return []

            return self._decrypt_locations(result, tools)
        except Exception as e:
            logger.error(f"Error getting location for {device_name}: {e}")
            return []

    def _decrypt_locations(self, device_update, tools):
        """Decrypt E2EE location data"""
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
                except Exception as e:
                    logger.warning(f"Decrypt single location failed: {e}")
        except Exception as e:
            logger.error(f"Decrypt locations failed: {e}")
        return locations

    def update_all_locations(self):
        """Fetch lokasi semua tracker, update database"""
        if not self.app:
            return
        
        tracker_map = self._get_tracker_map()
        if not tracker_map:
            logger.info("No trackers configured in database")
            return

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
                logger.info(f"Updated {anggota.nama}: {latest['latitude']:.6f}, {latest['longitude']:.6f}")

    def start_worker(self, interval=60):
        """Background thread: fetch lokasi tiap N detik"""
        if self._running:
            return
        self._running = True

        def worker():
            logger.info(f"Background worker started (interval: {interval}s)")
            while self._running:
                try:
                    self.update_all_locations()
                except Exception as e:
                    logger.error(f"Worker error: {e}")
                time.sleep(interval)

        self._thread = Thread(target=worker, daemon=True)
        self._thread.start()

    def stop_worker(self):
        self._running = False


def register_findmy_routes(app, findmy_service):
    """API routes untuk FindMy integration"""
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

    @app.route('/api/findmy/trackers', methods=['GET'])
    @admin_required
    def api_findmy_trackers():
        """Get tracker mapping from database"""
        try:
            from models import FindMyTracker
            trackers = FindMyTracker.query.filter_by(is_active=True).all()
            return jsonify({
                'success': True, 
                'data': {t.canonical_id: t.anggota.kartu_id for t in trackers if t.anggota}
            })
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/findmy/google-trackers', methods=['GET'])
    @admin_required
    def api_findmy_google_trackers():
        """List all trackers from Google account"""
        try:
            return jsonify({'success': True, 'data': findmy_service.list_trackers()})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/findmy/locate/<kartu_id>', methods=['POST'])
    @admin_required
    def api_findmy_locate(kartu_id):
        """Request location for specific card"""
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

    @app.route('/api/findmy/update-all', methods=['POST'])
    @admin_required
    def api_findmy_update_all():
        """Update locations for all trackers"""
        try:
            findmy_service.update_all_locations()
            return jsonify({'success': True, 'message': 'Updated'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/findmy/update-location', methods=['POST'])
    @admin_required
    def api_findmy_update_location():
        """Update location for a tracker (called by sync script)"""
        from models import db, FindMyTracker, Anggota
        
        data = request.get_json()
        canonical_id = data.get('canonical_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        address = data.get('address')
        
        tracker = FindMyTracker.query.filter_by(canonical_id=canonical_id).first()
        if not tracker:
            return jsonify({'success': False, 'message': 'Tracker not found'}), 404
        
        tracker.last_seen = datetime.now()
        tracker.last_latitude = latitude
        tracker.last_longitude = longitude
        tracker.last_address = address
        
        # Also update anggota
        if tracker.anggota:
            tracker.anggota.lokasi_lat = latitude
            tracker.anggota.lokasi_lng = longitude
            tracker.anggota.lokasi_nama = address or 'GPS via Find Hub'
            tracker.anggota.lokasi_waktu = datetime.now()
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Updated {tracker.anggota.kartu_id if tracker.anggota else canonical_id}'})


# ============================================================
# CARA AKTIVASI DI app.py:
# ============================================================
#
# Tambahkan di bawah baris "app = create_app()" :
#
# from findmy_service import FindMyLocationService, register_findmy_routes
# findmy = FindMyLocationService()
# findmy.init_app(app)
# register_findmy_routes(app, findmy)
# # findmy.start_worker(interval=60)  # Uncomment untuk auto-update tiap 1 menit
#
# TIDAK PERLU LAGI menambahkan FINDMY_TRACKER_MAP di config.py
# Kelola tracker via Admin Panel → Monitoring → FindMy Trackers
