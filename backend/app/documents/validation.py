"""
Upload validation: magic-byte MIME sniffing + file-size limit.

We do NOT trust the Content-Type header or file extension supplied by the
client — we sniff the actual bytes (DESIGN.md §5.6).
"""

from fastapi import HTTPException

# Allowed MIME types for tax documents (PDF + common image formats for scans)
_MAGIC: list[tuple[bytes, str]] = [
    (b"%PDF", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"II*\x00", "image/tiff"),   # little-endian TIFF
    (b"MM\x00*", "image/tiff"),   # big-endian TIFF
]

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def sniff_mime(data: bytes) -> str | None:
    """Return the detected MIME type from magic bytes, or None if unrecognised."""
    for magic, mime in _MAGIC:
        if data[: len(magic)] == magic:
            return mime
    return None


def validate_upload(data: bytes) -> str:
    """Validate size and MIME; return the detected MIME type or raise HTTP 4xx."""
    if not data:
        raise HTTPException(status_code=422, detail="Empty file")

    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)} MB)",
        )

    mime = sniff_mime(data)
    if mime is None:
        raise HTTPException(
            status_code=415,
            detail="File type not allowed. Accepted: PDF, PNG, JPEG, TIFF",
        )

    return mime
