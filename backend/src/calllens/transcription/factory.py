"""Factories that select Transcriber and Diarizer from application settings."""

from calllens.core.config import get_settings
from calllens.transcription.base import Diarizer, Transcriber


def get_transcriber() -> Transcriber:
    """Return the configured Transcriber implementation.

    Returns:
        A Transcriber selected by TRANSCRIBER_PROVIDER setting.

    Raises:
        ValueError: If TRANSCRIBER_PROVIDER is unrecognised.
    """
    settings = get_settings()
    if settings.transcriber_provider == "stub":
        from calllens.transcription.stub import StubTranscriber

        return StubTranscriber()
    if settings.transcriber_provider == "faster_whisper":
        from calllens.transcription.whisper import FasterWhisperTranscriber

        return FasterWhisperTranscriber()
    if settings.transcriber_provider == "groq":
        from calllens.transcription.groq_whisper import GroqWhisperTranscriber

        return GroqWhisperTranscriber()
    raise ValueError(f"Unknown transcriber provider: {settings.transcriber_provider!r}")


def get_diarizer() -> Diarizer:
    """Return the configured Diarizer implementation.

    Returns:
        A Diarizer selected by DIARIZER_PROVIDER setting.

    Raises:
        ValueError: If DIARIZER_PROVIDER is unrecognised.
    """
    settings = get_settings()
    if settings.diarizer_provider == "null":
        from calllens.transcription.null_diarizer import NullDiarizer

        return NullDiarizer()
    if settings.diarizer_provider == "pyannote":
        from calllens.transcription.pyannote_diarizer import PyannoteDiarizer

        return PyannoteDiarizer()
    raise ValueError(f"Unknown diarizer provider: {settings.diarizer_provider!r}")
