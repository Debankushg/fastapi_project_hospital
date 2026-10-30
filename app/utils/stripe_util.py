import stripe

from app.config import settings
from .http_error_util import HttpError


def get_stripe() -> stripe.StripeClient:
    """A Stripe client; 503 when STRIPE_SECRET_KEY is not configured."""
    if not settings.STRIPE_SECRET_KEY:
        raise HttpError(503, "Online payments are not configured on this server")
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def to_minor_units(amount: float | str) -> int:
    """Smallest currency unit (cents/paise) for a decimal amount."""
    return round(float(amount) * 100)
