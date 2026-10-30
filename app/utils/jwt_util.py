import time

import jwt

from app.config import settings
from app.config.constants import TOKEN_TTL_SECONDS
from app.typings.domain_types import TokenStage


def sign_token(user_id: str, stage: TokenStage) -> str:
    now = int(time.time())
    claims = {"sub": user_id, "stage": stage, "iat": now, "exp": now + TOKEN_TTL_SECONDS[stage]}
    return jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> tuple[str, TokenStage]:
    """Raises jwt.PyJWTError (or KeyError for a token without a stage) when invalid or expired."""
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})
    return claims["sub"], claims["stage"]
