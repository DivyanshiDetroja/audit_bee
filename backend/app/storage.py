"""
Private file storage.

Files are stored outside any public/static directory, keyed by an opaque
UUID (no extension, never the original filename).  The only way to retrieve
a file is through an authenticated, authorized FastAPI route.

Local-disk implementation for the demo.  Production swap: replace save/load
with boto3 calls to an S3 bucket with private ACLs and presigned URLs.
"""

from pathlib import Path

UPLOAD_DIR = Path("uploads")


def _safe_path(storage_key: str) -> Path:
    """Resolve the storage path and guard against path-traversal attacks.
    storage_key is always a UUID we generate, so this is belt-and-suspenders."""
    base = UPLOAD_DIR.resolve()
    path = (base / storage_key).resolve()
    if not str(path).startswith(str(base)):
        raise ValueError(f"Invalid storage key: {storage_key!r}")
    return path


def save_file(storage_key: str, data: bytes) -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _safe_path(storage_key).write_bytes(data)


def load_file(storage_key: str) -> bytes:
    path = _safe_path(storage_key)
    if not path.exists():
        raise FileNotFoundError(storage_key)
    return path.read_bytes()


def delete_file(storage_key: str) -> None:
    path = _safe_path(storage_key)
    if path.exists():
        path.unlink()
