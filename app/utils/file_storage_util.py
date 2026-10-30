import asyncio
import re
import uuid
from pathlib import Path
from urllib.parse import unquote

from app.config import settings

_root = Path(settings.UPLOAD_DIR).resolve() / "prescriptions"


def is_pdf(buf: bytes) -> bool:
    """PDF files start with "%PDF-". Checked on the bytes, not just the Content-Type header."""
    return len(buf) > 5 and buf[:5] == b"%PDF-"


async def save_prescription_file(buf: bytes) -> str:
    stored_name = f"{uuid.uuid4()}.pdf"

    def write() -> None:
        _root.mkdir(parents=True, exist_ok=True)
        with open(_root / stored_name, "xb") as f:
            f.write(buf)

    await asyncio.to_thread(write)
    return stored_name


def prescription_file_path(stored_name: str) -> Path:
    return _root / Path(stored_name).name


async def delete_prescription_files(stored_names: list[str]) -> None:
    def rm() -> None:
        for n in stored_names:
            prescription_file_path(n).unlink(missing_ok=True)

    await asyncio.to_thread(rm)


def safe_file_name(raw: str | None) -> str:
    """Makes a safe display name: no path parts, always ends with .pdf."""
    try:
        decoded = unquote(raw or "", errors="strict")
    except UnicodeDecodeError:
        decoded = raw or ""
    cleaned = re.sub(r"[\x00-\x1f]", "", decoded).replace("\\", "/")
    base = cleaned.split("/")[-1][:120] or "prescription"
    return base if base.lower().endswith(".pdf") else f"{base}.pdf"
