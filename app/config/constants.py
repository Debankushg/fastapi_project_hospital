BCRYPT_ROUNDS = 12

MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15

RECOVERY_CODE_COUNT = 8
TOTP_WINDOW = 1

TOKEN_TTL_SECONDS = {"mfa_pending": 5 * 60, "mfa_setup": 15 * 60, "full": 60 * 60}

AUTH_RATE_LIMIT = {"window_seconds": 15 * 60, "limit": 30}
