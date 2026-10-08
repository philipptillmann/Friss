#!/usr/bin/env python3
import getpass
import hashlib
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = root / '.env'
if not path.exists():
    raise SystemExit('Create .env from .env.example first.')
password = getpass.getpass('New Friss password (at least 12 characters): ')
if len(password) < 12:
    raise SystemExit('Use at least 12 characters.')
if password != getpass.getpass('Confirm password: '):
    raise SystemExit('Passwords do not match.')
salt = secrets.token_hex(16)
digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
lines = [line for line in path.read_text().splitlines() if not line.startswith('FRISS_PASSWORD_HASH=')]
lines.append(f'FRISS_PASSWORD_HASH=scrypt:{salt}:{digest}')
path.write_text('\n'.join(lines)+'\n')
path.chmod(0o600)
print('Password hash saved. Recreate the container to apply it. Existing sessions will be invalidated.')
