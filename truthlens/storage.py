"""Utility functions for case storage.

- Generate a unique case ID.
- Compute SHA‑256 hash of a file.
- Save the original file read‑only under `data/cases/<case_id>/originals`.
- Detect media type from file extension.
- Ensure the directory structure exists.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from .schemas import InputFile

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "cases"

EXTENSION_MAP = {
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "webp": "image",
    "mp4": "video",
    "mov": "video",
    "avi": "video",
    "mkv": "video",
    "wav": "audio",
    "mp3": "audio",
    "m4a": "audio",
    "flac": "audio",
    "txt": "text",
    "md": "text",
}


def detect_media_type(filename_or_path: str | Path) -> str:
    """Detect media type from file extension."""
    suffix = Path(filename_or_path).suffix.lstrip(".").lower()
    return EXTENSION_MAP.get(suffix, "unknown")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def generate_case_id() -> str:
    """Create a case identifier like ``c_YYYYMMDD_HHMMSS``."""
    return f"c_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def sha256_file(path: Path) -> str:
    """Return the hex SHA‑256 digest of *path*.

    The file is read in binary mode in chunks to avoid loading huge files
    entirely into memory.
    """
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def save_originals(file_paths: List[Path]) -> Tuple[str, List[InputFile]]:
    """Store the uploaded files and return ``case_id`` and ``InputFile`` list.

    ``file_paths`` are absolute paths to the temporary uploaded files. The
    function copies each file into ``data/cases/<case_id>/originals`` and makes
    the copy read‑only. It also builds the ``InputFile`` metadata required by the
    ``Report`` model.
    """
    case_id = generate_case_id()
    case_dir = DATA_ROOT / case_id
    originals_dir = case_dir / "originals"
    _ensure_dir(originals_dir)

    inputs: List[InputFile] = []
    for idx, src in enumerate(file_paths):
        dest = originals_dir / src.name
        dest.write_bytes(src.read_bytes())
        # Make the copy read‑only.
        dest.chmod(0o444)
        file_sha = sha256_file(dest)
        inputs.append(
            InputFile(
                file_id=f"f_{idx+1:04d}",
                filename=src.name,
                media_type=detect_media_type(src.name),
                sha256=file_sha,
                size_bytes=dest.stat().st_size,
            )
        )
    return case_id, inputs
