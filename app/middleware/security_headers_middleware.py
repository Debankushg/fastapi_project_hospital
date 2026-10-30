from fastapi import FastAPI, Request


def install_security_headers(app: FastAPI) -> None:
    """The useful subset of what helmet() sets (no CSP: it would break Swagger UI)."""

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        return response
