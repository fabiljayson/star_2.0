from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import PurePosixPath

from django.conf import settings
from rest_framework import exceptions, status

# Extension → audio container verified from magic bytes (filenames and
# declared MIME types are never trusted).
AUDIO_KIND_BY_EXTENSION = {
    ".wav": "wav",
    ".ogg": "ogg",
    ".webm": "webm",
    ".mp3": "mp3",
    ".m4a": "m4a",
}

# Deterministic mock transcripts — clearly labelled, never presented as
# real speech or medically accurate output.
_MOCK_TEXT = {
    "en": (
        "[SIMULATED TRANSCRIPTION - MOCK PROVIDER, NOT REAL SPEECH] "
        "Demonstration operative note dictation for the STAR platform. "
        "The patient reference stays pseudonymous. Review and correct this "
        "text manually before saving a draft or submitting the record."
    ),
    "fr": (
        "[TRANSCRIPTION SIMULEE - MOCK, PAS DE VRAIE PAROLE] "
        "Diction de note operatoire de demonstration pour la plateforme STAR. "
        "La reference patient reste pseudonyme. Relisez et corrigez ce texte "
        "avant d'enregistrer un brouillon ou de soumettre le compte rendu."
    ),
}


class TranscriptionUnavailable(exceptions.APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "The transcription service is unavailable. Continue typing manually; "
        "your draft is untouched."
    )
    default_code = "transcription_unavailable"


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    provider: str
    simulated: bool
    confidence: float
    uncertain: bool


class BaseTranscriptionProvider:
    name = "base"

    def transcribe(self, data: bytes, *, language: str, filename: str) -> TranscriptionResult:
        raise NotImplementedError


class MockTranscriptionProvider(BaseTranscriptionProvider):
    """Deterministic development provider.

    Honours `TRANSCRIPTION_MOCK_FAILURE` so automated tests and demos can
    exercise the provider-failure path without any external dependency.
    """

    name = "mock"

    def transcribe(self, data: bytes, *, language: str, filename: str) -> TranscriptionResult:
        if settings.TRANSCRIPTION_MOCK_FAILURE:
            raise TranscriptionUnavailable(
                "The configured transcription provider did not accept the "
                "audio (simulated outage). Your draft is untouched."
            )
        return TranscriptionResult(
            text=_MOCK_TEXT.get(language, _MOCK_TEXT["en"]),
            language=language,
            provider=self.name,
            simulated=True,
            confidence=0.0,
            uncertain=True,
        )


_PROVIDERS = {
    "mock": MockTranscriptionProvider,
}


def get_provider() -> BaseTranscriptionProvider:
    name = settings.TRANSCRIPTION_PROVIDER
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise RuntimeError(
            f"Unknown TRANSCRIPTION_PROVIDER '{name}'. "
            f"Available: {', '.join(sorted(_PROVIDERS))}."
        ) from None


def _detected_audio_kind(head: bytes) -> str | None:
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"\x1a\x45\xdf\xa3":  # EBML (WebM/Matroska)
        return "webm"
    if head[:3] == b"ID3":
        return "mp3"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        return "mp3"
    if head[4:8] == b"ftyp":  # MP4/M4A family
        return "m4a"
    return None


def validate_and_read_audio(file) -> dict:
    """Enforce size/extension/content rules for dictation audio uploads."""
    allowed = {
        ext.lower(): AUDIO_KIND_BY_EXTENSION[ext.lower()]
        for ext in settings.AUDIO_ALLOWED_EXTENSIONS
        if ext.lower() in AUDIO_KIND_BY_EXTENSION
    }
    max_bytes = settings.AUDIO_MAX_SIZE_MB * 1024 * 1024

    original_name = getattr(file, "name", "") or ""
    extension = PurePosixPath(original_name).suffix.lower()

    if extension not in allowed:
        raise exceptions.ValidationError(
            {"audio": f"Audio extension '{extension or '(none)'}' is not permitted."}
        )

    size = getattr(file, "size", None)
    if size is not None and size > max_bytes:
        raise exceptions.ValidationError(
            {"audio": f"Audio exceeds the {settings.AUDIO_MAX_SIZE_MB} MB limit."}
        )

    data = file.read()
    if not data:
        raise exceptions.ValidationError({"audio": "The uploaded audio is empty."})
    if len(data) > max_bytes:
        raise exceptions.ValidationError(
            {"audio": f"Audio exceeds the {settings.AUDIO_MAX_SIZE_MB} MB limit."}
        )

    detected = _detected_audio_kind(data[:16])
    expected = allowed[extension]
    if detected is None:
        raise exceptions.ValidationError(
            {
                "audio": "Audio content could not be verified "
                "(the file type is not recognised)."
            }
        )
    if detected != expected:
        raise exceptions.ValidationError(
            {"audio": "Audio content does not match its extension."}
        )

    return {
        "data": data,
        "extension": extension,
        "detected_kind": detected,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def supported_languages() -> list[str]:
    return [lang.strip().lower() for lang in settings.TRANSCRIPTION_LANGUAGES if lang.strip()]


def provider_name() -> str:
    """Name reported to clients — simulated results are always labelled."""
    return os.environ.get("TRANSCRIPTION_PROVIDER", "mock")
