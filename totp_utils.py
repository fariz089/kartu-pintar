"""
TOTP / 2FA utility module
- Pure-Python TOTP (RFC 6238) implementation: no external runtime dep beyond pyotp (optional).
- Falls back to manual HMAC-SHA1 implementation if pyotp is not installed.
- Generates otpauth:// URIs and SVG QR codes (segno already in requirements.txt).
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote

import segno

ISSUER = "SmartCard Poltekad"
DIGITS = 6
PERIOD = 30
ALGORITHM = "SHA1"


# ---------- Secret generation ----------
def generate_secret(length_bytes: int = 20) -> str:
    """Generate base32 secret (160-bit recommended by RFC 4226)."""
    return base64.b32encode(os.urandom(length_bytes)).decode("ascii").rstrip("=")


# ---------- TOTP core ----------
def _hotp(secret_b32: str, counter: int, digits: int = DIGITS) -> str:
    # Pad base32 if needed
    pad = (8 - len(secret_b32) % 8) % 8
    key = base64.b32decode(secret_b32 + ("=" * pad), casefold=True)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code_int = (struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code_int).zfill(digits)


def current_totp(secret_b32: str, t: int = None) -> str:
    if t is None:
        t = int(time.time())
    counter = t // PERIOD
    return _hotp(secret_b32, counter)


def verify_totp(secret_b32: str, code: str, window: int = 1) -> bool:
    """Verify a TOTP code with +/- `window` periods of clock-skew tolerance."""
    if not code or not secret_b32:
        return False
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return False
    now = int(time.time())
    counter = now // PERIOD
    for offset in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret_b32, counter + offset), code):
            return True
    return False


# ---------- otpauth URI ----------
def build_otpauth_uri(secret_b32: str, account_name: str, issuer: str = ISSUER) -> str:
    label = quote(f"{issuer}:{account_name}")
    params = (
        f"secret={secret_b32}&issuer={quote(issuer)}"
        f"&algorithm={ALGORITHM}&digits={DIGITS}&period={PERIOD}"
    )
    return f"otpauth://totp/{label}?{params}"


# ---------- QR code as SVG data URI ----------
def qr_data_uri(otpauth_uri: str, scale: int = 6) -> str:
    """Render otpauth URI to inline SVG data URI for <img src=...>."""
    qr = segno.make(otpauth_uri, error="m")
    import io
    buf = io.BytesIO()
    # Black-on-white: maximum scanner compatibility. The container .totp-qr
    # already provides a white card, so we keep the same scheme inside the SVG.
    qr.save(buf, kind="svg", scale=scale, dark="#000000", light="#FFFFFF", border=2)
    svg_bytes = buf.getvalue()
    b64 = base64.b64encode(svg_bytes).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def qr_data_uri_png(otpauth_uri: str, scale: int = 8) -> str:
    """PNG version (used by mobile API which doesn't render SVG easily)."""
    qr = segno.make(otpauth_uri, error="m")
    import io
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=scale, dark="#000000", light="#FFFFFF", border=2)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


# ---------- Backup codes ----------
def generate_backup_codes(n: int = 8) -> list:
    """Generate n human-readable backup codes (e.g. ABCD-1234)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # avoid 0/O/1/I
    out = []
    for _ in range(n):
        s = "".join(secrets.choice(alphabet) for _ in range(8))
        out.append(f"{s[:4]}-{s[4:]}")
    return out
