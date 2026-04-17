FROM python:3.11-slim

WORKDIR /app

# ⚠️  PATCH: Tambah libffi-dev + libssl-dev buat cryptography/pyscrypt build,
# dan git buat kasus kalau findmy_tools submodule perlu rebuild.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    libffi-dev libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install root Python deps + gunicorn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# ============================================================
# ⚠️  PATCH: Install findmy_tools runtime deps
# ============================================================
# Bug sebelumnya: Dockerfile tidak install requirements findmy_tools,
# jadi `_load_tools()` gagal ImportError (gpsoauth, pyscrypt, protobuf,
# aiohttp, http_ece, pycryptodomex, ecdsa, dll. tidak ada).
#
# Kita skip package yang cuma dibutuhkan saat FIRST-TIME login interaktif
# (undetected-chromedriver, selenium, frida) — itu dipakai sekali aja
# buat generate secrets.json, tidak butuh di runtime container.
# ============================================================
RUN pip install --no-cache-dir \
    gpsoauth>=1.1.1 \
    requests>=2.32.3 \
    beautifulsoup4>=4.12.3 \
    pyscrypt>=1.6.2 \
    cryptography>=43.0.3 \
    pycryptodomex>=3.21.0 \
    ecdsa>=0.19.0 \
    pytz>=2024.2 \
    protobuf>=5.28.3 \
    httpx>=0.28.0 \
    h2>=4.1.0 \
    aiohttp>=3.11.8 \
    http_ece>=1.1.0

# Copy source
COPY . .

# Create leader-lock directory (used by findmy_service.acquire_leader_lock)
RUN mkdir -p /var/run/kartu-pintar && chmod 777 /var/run/kartu-pintar
ENV FINDMY_LEADER_LOCK=/var/run/kartu-pintar/findmy_leader.lock

EXPOSE 5000

# ⚠️  NOTE: Sekarang worker FindMy jalan di dalam gunicorn (cuma 1 worker
# yang dapat leader lock). Kalau mau lebih clean, pakai docker-compose.yml
# yang spawn service `findmy-worker` terpisah + set FINDMY_AUTO_START=0 di sini.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
