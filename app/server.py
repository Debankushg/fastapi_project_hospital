"""Entry point:  python -m app.server"""

import uvicorn

from app.config import settings

if __name__ == "__main__":
    uvicorn.run("app.app:app", host="0.0.0.0", port=settings.PORT, reload=settings.NODE_ENV == "development")
