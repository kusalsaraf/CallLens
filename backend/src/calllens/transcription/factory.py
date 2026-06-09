"""Factories that select Transcriber and Diarizer from application settings."""

from calllens.core.config import get_settings
from calllens.transcription.base import Diarizer, Transcriber


def get_transcriber() -> Transcriber:
    """Return the configured Transcriber implementation.

    Returns:
        A Transcriber selected by TRANSCRIBER_PROVIDER setting.

    Raises:
        ValueError: If TRANSCRIBER_PROVIDER is unrecognised, or if a
            managed provider is selected without the required API key.
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
    if settings.transcriber_provider == "assemblyai":
        if not settings.assemblyai_api_key:
            raise ValueError("ASSEMBLYAI_API_KEY is required when TRANSCRIBER_PROVIDER=assemblyai")
        from calllens.transcription.assemblyai import AssemblyAITranscriber

        return AssemblyAITranscriber()
    raise ValueError(f"Unknown transcriber provider: {settings.transcriber_provider!r}")


def get_diarizer() -> Diarizer:
    """Return the configured Diarizer implementation.

    When TRANSCRIBER_PROVIDER=assemblyai, returns PassthroughDiarizer
    regardless of DIARIZER_PROVIDER setting (AssemblyAI returns speakers
    in its transcription response).

    Returns:
        A Diarizer selected by DIARIZER_PROVIDER setting.

    Raises:
        ValueError: If DIARIZER_PROVIDER is unrecognised.
    """
    settings = get_settings()

    if settings.transcriber_provider == "assemblyai":
        from calllens.transcription.passthrough_diarizer import PassthroughDiarizer

        return PassthroughDiarizer()

    if settings.diarizer_provider == "null":
        from calllens.transcription.null_diarizer import NullDiarizer

        return NullDiarizer()
    if settings.diarizer_provider == "pyannote":
        from calllens.transcription.pyannote_diarizer import PyannoteDiarizer

        return PyannoteDiarizer()
    if settings.diarizer_provider == "passthrough":
        from calllens.transcription.passthrough_diarizer import PassthroughDiarizer

        return PassthroughDiarizer()
    raise ValueError(f"Unknown diarizer provider: {settings.diarizer_provider!r}")
