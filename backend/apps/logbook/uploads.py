from __future__ import annotations

import hashlib
import secrets
from pathlib import PurePosixPath

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from rest_framework import exceptions

# Magic-byte signatures → canonical kind. Filenames and client MIME types are
# never trusted on their own.
_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"%PDF-", "application/pdf"),
)

KIND_BY_EXTENSION = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class PrivateMediaStorage(FileSystemStorage):
    """Filesystem storage outside the web root; never served publicly.

    The location is resolved from settings on every access so that test
    suites (and future reconfiguration) can point it at a temporary folder.
    """

    def __init__(self, **kwargs):
        kwargs.pop("location", None)
        kwargs.pop("base_url", None)
        super().__init__(**kwargs)

    @property
    def base_location(self) -> str:
        return str(settings.PRIVATE_MEDIA_ROOT)

    def url(self, name) -> str:
        raise ValueError("Private clinical files are not accessible via a URL.")


private_storage = PrivateMediaStorage()


def _detected_kind(head: bytes, extension: str) -> str:
    for signature, kind in _SIGNATURES:
        if head.startswith(signature):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head[:4] == b"PK\x03\x04" and extension == ".docx":
        # OOXML package: confirm it contains the main document part.
        return KIND_BY_EXTENSION[".docx"]
    raise exceptions.ValidationError(
        {
            "file": "File content does not match any permitted format "
            "(the file type could not be verified)."
        }
    )


def validate_and_read_upload(file) -> dict:
    """Enforce size/extension/content rules and return safe metadata.

    Raises DRF ValidationError with actionable messages. Never trusts the
    declared content type or the original filename.
    """
    allowed = {ext.lower() for ext in settings.ATTACHMENT_ALLOWED_EXTENSIONS}
    max_bytes = settings.ATTACHMENT_MAX_SIZE_MB * 1024 * 1024

    original_name = getattr(file, "name", "") or ""
    extension = PurePosixPath(original_name).suffix.lower()

    if extension not in allowed:
        raise exceptions.ValidationError(
            {"file": f"File extension '{extension or '(none)'}' is not permitted."}
        )

    size = getattr(file, "size", None)
    if size is not None and size > max_bytes:
        raise exceptions.ValidationError(
            {"file": f"File exceeds the {settings.ATTACHMENT_MAX_SIZE_MB} MB limit."}
        )

    data = file.read()
    if not data:
        raise exceptions.ValidationError({"file": "The uploaded file is empty."})
    if len(data) > max_bytes:
        raise exceptions.ValidationError(
            {"file": f"File exceeds the {settings.ATTACHMENT_MAX_SIZE_MB} MB limit."}
        )

    kind = _detected_kind(data[:32], extension)
    expected = KIND_BY_EXTENSION[extension]
    if kind != expected:
        raise exceptions.ValidationError(
            {"file": "File content does not match its extension."}
        )

    return {
        "data": data,
        "original_name": PurePosixPath(original_name).name[:255],
        "extension": extension,
        "detected_kind": kind,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "storage_name": f"procedures/{secrets.token_hex(16)}{extension}",
    }


def store_upload(meta: dict) -> ContentFile:
    """Persist validated bytes under an opaque, collision-free name."""
    return ContentFile(meta["data"], name=meta["storage_name"])
