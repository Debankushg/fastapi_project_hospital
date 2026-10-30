from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.error_middleware import install_error_handlers
from app.middleware.security_headers_middleware import install_security_headers
from app.routes import router
from app.utils.response_util import ApiJSONResponse

# Swagger UI at /api/docs and the raw spec at /api/docs.json (generated from the routes and schemas).
app = FastAPI(
    title="Hospital API",
    version="1.0.0",
    default_response_class=ApiJSONResponse,
    docs_url="/api/docs",
    openapi_url="/api/docs.json",
    redoc_url=None,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
install_security_headers(app)
install_error_handlers(app)


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


app.include_router(router, prefix="/api")
