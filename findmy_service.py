"""
Kartu Pintar - Google Find Hub Location Service
================================================

SETUP:
1. cd kartu-pintar
2. git clone https://github.com/leonboe1/GoogleFindMyTools.git findmy_tools
3. pip install -r findmy_tools/requirements.txt
4. python findmy_tools/main.py   (login Google pertama kali, butuh Chrome)
5. Catat canonic_device_id MiLi Card kamu
6. Set FINDMY_TRACKER_MAP di config.py
7. Aktifkan di app.py (lihat bawah file ini)

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

    def __init__(self, app=None, tracker_map=None):
        self.app = app
        self.tracker_map = tracker_map or {}
        self._running = False
        self._thread = None
        self._tools = None

    def init_app(self, app):
        self.app = app
        self.tracker_map = app.config.get('FINDMY_TRACKER_MAP', {})
        logger.info(f"FindMy initialized with {len(self.tracker_map)} tracker mappings")

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
        try:
            result_hex = tools['request_device_list']()
            device_list = tools['parse_device_list_protobuf'](result_hex)
            tools['refresh_custom_trackers'](device_list)
            canonic_ids = tools['get_canonic_ids'](device_list)

            return [{
                'device_name': name,
                'canonic_id': cid,
                'kartu_id': self.tracker_map.get(cid, 'UNMAPPED'),
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
        if not self.app or not self.tracker_map:
            return

        with self.app.app_context():
            from models import db, Anggota, LokasiHistory

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
                anggota.lokasi_lat = latest['latitude']
                anggota.lokasi_lng = latest['longitude']
                anggota.lokasi_nama = f"GPS via Find Hub (±{latest.get('accuracy', '?')}m)"
                anggota.lokasi_waktu = latest['timestamp']

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

    def start_worker(self, interval=300):
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
    from flask import jsonify

    @app.route('/api/findmy/trackers', methods=['GET'])
    def api_findmy_trackers():
        try:
            return jsonify({'success': True, 'data': findmy_service.list_trackers()})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500

    @app.route('/api/findmy/locate/<kartu_id>', methods=['POST'])
    def api_findmy_locate(kartu_id):
        canonic_id = None
        for cid, kid in findmy_service.tracker_map.items():
            if kid == kartu_id:
                canonic_id = cid
                break
        if not canonic_id:
            return jsonify({'success': False, 'message': f'No tracker mapped to {kartu_id}'}), 404

        locs = findmy_service.get_location(canonic_id, kartu_id)
        return jsonify({'success': True, 'data': [{
            'latitude': l['latitude'], 'longitude': l['longitude'],
            'timestamp': l['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            'accuracy': l.get('accuracy'),
        } for l in locs if l.get('latitude')]})

    @app.route('/api/findmy/update-all', methods=['POST'])
    def api_findmy_update_all():
        try:
            findmy_service.update_all_locations()
            return jsonify({'success': True, 'message': 'Updated'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500


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
# # findmy.start_worker(interval=300)  # Uncomment untuk auto-update tiap 5 menit
#
# Dan di config.py tambahkan:
#
# FINDMY_TRACKER_MAP = {
#     'canonic_device_id_dari_main_py': 'KP-2025-001',
# }
