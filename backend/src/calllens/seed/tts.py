"""Synthetic audio generation via edge-tts + pydub.

Requires the optional ``demo`` dependency group:
    uv sync --group demo

Also requires ffmpeg installed on the system (needed by pydub).
The ``synthesize_call`` function is injectable for testing — pass a custom
``tts_fn`` to avoid real network calls.
"""

from __future__ import annotations

import io
import logging
import tempfile
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from calllens.seed.scenarios import Turn

logger = logging.getLogger(__name__)

AGENT_VOICE = "en-US-GuyNeural"
CUSTOMER_VOICE = "en-US-JennyNeural"

TtsFn = Callable[[str, str], Coroutine[Any, Any, bytes]]


async def _edge_tts_synthesize(text: str, voice: str) -> bytes:
    """Synthesize text to MP3 bytes using edge-tts.

    Args:
        text: Text to speak.
        voice: Edge-TTS voice name.

    Returns:
        MP3 audio bytes.
    """
    try:
        import edge_tts
    except ImportError as exc:
        raise ImportError("edge-tts is not installed. Run: uv sync --group demo") from exc

    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


async def synthesize_call(
    turns: list[Turn],
    *,
    tts_fn: TtsFn | None = None,
) -> bytes:
    """Synthesize a multi-turn call script into a single audio file.

    Each turn is synthesized with a distinct voice per speaker role
    (agent vs customer), then concatenated via pydub. A short silence
    gap separates turns.

    Args:
        turns: Ordered list of speaker turns.
        tts_fn: Optional TTS function override for testing.
            Signature: async (text, voice) -> bytes (MP3).

    Returns:
        Concatenated MP3 audio bytes for the full call.
    """
    try:
        from pydub import AudioSegment
    except ImportError as exc:
        raise ImportError("pydub is not installed. Run: uv sync --group demo") from exc

    synth = tts_fn or _edge_tts_synthesize
    silence = AudioSegment.silent(duration=400)
    combined = AudioSegment.empty()

    for turn in turns:
        voice = AGENT_VOICE if turn["speaker"] == "agent" else CUSTOMER_VOICE
        mp3_bytes = await synth(turn["text"], voice)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            tf.write(mp3_bytes)
            tf_path = Path(tf.name)

        try:
            segment = AudioSegment.from_mp3(str(tf_path))
            combined += segment + silence
        finally:
            tf_path.unlink(missing_ok=True)

    output = io.BytesIO()
    combined.export(output, format="mp3")
    return output.getvalue()
