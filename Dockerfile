FROM python:3.11-slim

WORKDIR /app

# Build tools + libs for cryptography/pyscrypt/etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    libffi-dev libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Jakarta
# Install root Python deps + gunicorn
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# ============================================================
# ⚠️  PATCH v2: Install findmy_tools runtime deps
# ============================================================
# Kenapa selenium + undetected-chromedriver ikut di-install:
# Meskipun Chrome HANYA dipanggil saat first-time login (generate secrets.json),
# modul-modul ini di-import di LEVEL MODULE melalui chain:
#   NovaApi/nova_request.py
#     -> Auth/aas_token_retrieval.py
#       -> Auth/auth_flow.py
#         -> chrome_driver.py  (`import undetected_chromedriver as uc`)
#         -> `from selenium.webdriver.support.ui import WebDriverWait`
#
# Jadi `import NovaApi.nova_request` langsung gagal kalau selenium tidak ada.
# Package-nya kita install tapi Chrome binary TIDAK perlu — Chrome cuma
# dipanggil kalau token expired, dan kita sudah punya secrets.json.
#
# `frida` ada di requirements.txt tapi TIDAK dipakai di kode manapun
# (grep-confirmed), jadi tetap kita skip buat hemat image size.
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
    http_ece>=1.1.0 \
    selenium>=4.27.1 \
    undetected-chromedriver>=3.5.5

# Copy source
COPY . .

# Create leader-lock directory (used by findmy_service.acquire_leader_lock)
RUN mkdir -p /var/run/kartu-pintar && chmod 777 /var/run/kartu-pintar
ENV FINDMY_LEADER_LOCK=/var/run/kartu-pintar/findmy_leader.lock

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
