import hashlib
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings
from app.config.constants import RECOVERY_CODE_COUNT


# AES-256-GCM with an explicit 64-hex-char key (used directly when rotating keys).
# Stored as iv:tag:ciphertext (hex), the same format as the Node backend.
def encrypt_with_key(plain: str, hex_key: str) -> str:
    iv = secrets.token_bytes(12)
    sealed = AESGCM(bytes.fromhex(hex_key)).encrypt(iv, plain.encode(), None)  # ciphertext || 16-byte tag
    ct, tag = sealed[:-16], sealed[-16:]
    return ":".join(b.hex() for b in (iv, tag, ct))


def decrypt_with_key(payload: str, hex_key: str) -> str:
    iv, tag, ct = (bytes.fromhex(p) for p in payload.split(":"))
    return AESGCM(bytes.fromhex(hex_key)).decrypt(iv, ct + tag, None).decode()


def encrypt(plain: str) -> str:
    return encrypt_with_key(plain, settings.MFA_ENCRYPTION_KEY)


def decrypt(payload: str) -> str:
    return decrypt_with_key(payload, settings.MFA_ENCRYPTION_KEY)


# Recovery codes are high-entropy random, so a fast hash is sufficient.
def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def generate_recovery_codes(n: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes = []
    for _ in range(n):
        h = secrets.token_hex(5)
        codes.append(f"{h[:5]}-{h[5:]}")
    return codes
