#!/usr/bin/env python3
"""
Kartu Pintar - FindMy Worker (Standalone)
==========================================

Script worker yang jalan terpisah dari gunicorn. Gunanya:
  - Loop update lokasi semua tracker tiap N detik
  - Jalan sebagai service sendiri di docker-compose (service `findmy-worker`)
  - Web app (gunicorn) bisa di-scale/restart tanpa ganggu tracking

CARA PAKAI:

  Local / dev:
      python findmy_worker.py

  Docker (recommended): Lihat docker-compose.yml service `findmy-worker`.

ENV VARS:
  FINDMY_UPDATE_INTERVAL  Interval loop dalam detik (default: 60)
  FINDMY_LOG_LEVEL        DEBUG|INFO|WARNING|ERROR (default: INFO)

EXIT:
  Ctrl+C atau SIGTERM → worker berhenti graceful.
"""

import os
import sys
import signal
import time
import logging

# ============================================================
# ⚠️ PENTING: Harus SEBELUM `from app import app`
# ============================================================
# `app.py` jalanin FindMy init + start_worker di level module saat di-import.
# Kalau kita tidak override env var di sini, worker akan jalan DUA KALI:
#   1. Dari app.py saat `from app import app` (module-level init)
#   2. Dari main() script ini
# Dua-duanya di proses yang sama = 2x spam Google API.
# Set env var SEKARANG, sebelum app.py kepikiran buat auto-start.
os.environ['FINDMY_AUTO_START'] = '0'

# Ensure the project root is on sys.path (so `from models import ...` works
# when this script is invoked from any working directory).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging before anything else
log_level = os.environ.get('FINDMY_LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='[%(asctime)s] %(name)s [%(levelname)s]: %(message)s',
    stream=sys.stdout,
)
log = logging.getLogger('findmy_worker_main')


def main():
    # Import AFTER setting FINDMY_AUTO_START=0 above
    from app import app
    from findmy_service import FindMyLocationService

    interval = int(os.environ.get('FINDMY_UPDATE_INTERVAL', 60))
    log.info(f"Starting dedicated FindMy worker (interval={interval}s, pid={os.getpid()})")

    service = FindMyLocationService()
    service.init_app(app)

    # In dedicated-worker mode we already know we're the only instance,
    # so no need for file-lock election.
    started = service.start_worker(interval=interval, require_leader=False)
    if not started:
        log.error("Worker failed to start — exiting")
        sys.exit(1)

    # Graceful shutdown on SIGTERM/SIGINT (docker stop sends SIGTERM)
    _stopping = {'flag': False}

    def _handle_shutdown(signum, frame):
        log.info(f"Signal {signum} received — stopping worker gracefully...")
        _stopping['flag'] = True
        service.stop_worker()

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    # Main process stays alive; the actual work runs in service._thread
    log.info("Worker running. Press Ctrl+C to stop.")
    try:
        while not _stopping['flag'] and service._thread and service._thread.is_alive():
            time.sleep(2)
    except KeyboardInterrupt:
        _handle_shutdown(signal.SIGINT, None)

    # Wait briefly for the worker thread to exit cleanly
    if service._thread:
        service._thread.join(timeout=10)

    log.info("Worker stopped.")
    sys.exit(0)


if __name__ == '__main__':
    main()
