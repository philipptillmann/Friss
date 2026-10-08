import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlsplit
from fastapi import HTTPException, Request

COOKIE = 'friss_session'
PASSWORD_HASH = os.getenv('FRISS_PASSWORD_HASH', '')
SECURE = os.getenv('FRISS_COOKIE_SECURE', 'false').lower() == 'true'
LIFETIME = 30 * 86400

def encode_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return f'scrypt:{salt}:{digest}'

def verify_password(password):
    try:
        algorithm, salt, digest = PASSWORD_HASH.split(':')
        if algorithm != 'scrypt': return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def same_origin(request: Request):
    origin = request.headers.get('origin')
    if not origin or urlsplit(origin).netloc != request.headers.get('host'):
        raise HTTPException(403, 'Same-origin request required')

def session_valid(request, db):
    token = request.cookies.get(COOKIE)
    if not token: return False
    with db() as c:
        row = c.execute('SELECT expires, password_version FROM sessions WHERE token=?', (token_hash(token),)).fetchone()
    return bool(row and row['expires'] > time.time() and hmac.compare_digest(row['password_version'], hashlib.sha256(PASSWORD_HASH.encode()).hexdigest()))
