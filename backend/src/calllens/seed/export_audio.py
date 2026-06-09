"""Export synthetic call audio to disk for manual upload/testing.

Requires the optional ``demo`` dependency group (edge-tts, pydub) and ffmpeg.
Does NOT ingest into the database — only writes audio files.

Usage::

    python -m calllens.seed.export_audio
    python -m calllens.seed.export_audio --count 4 --out data/audio
    python -m calllens.seed.export_audio --scenario demo-billing-good
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from calllens.seed.scenarios import SCENARIOS, Turn

logger = logging.getLogger(__name__)

SynthesizeFn = Callable[[list[Turn]], Coroutine[Any, Any, bytes]]


async def _default_synthesize(turns: list[Turn]) -> bytes:
    """Synthesize turns using the real edge-tts + pydub pipeline."""
    from calllens.seed.tts import synthesize_call

    return await synthesize_call(turns)


async def export_audio(
    *,
    count: int | None = None,
    out_dir: Path = Path("data/audio"),
    scenario_id: str | None = None,
    synthesize_fn: SynthesizeFn | None = None,
) -> list[Path]:
    """Synthesize scenario scripts and write audio files to disk.

    Args:
        count: Max number of scenarios to export. None = all.
        out_dir: Directory to write audio files into (created if missing).
        scenario_id: If set, export only the matching scenario.
        synthesize_fn: Optional synthesize function override for testing.
            Replaces the full synthesize_call pipeline.

    Returns:
        List of written file paths.
    """
    synth = synthesize_fn or _default_synthesize

    if scenario_id:
        selected = [s for s in SCENARIOS if s["id"] == scenario_id]
        if not selected:
            ids = [s["id"] for s in SCENARIOS]
            raise ValueError(f"Unknown scenario {scenario_id!r}. Available: {ids}")
    else:
        selected = SCENARIOS[:count] if count else list(SCENARIOS)

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for idx, scenario in enumerate(selected, 1):
        slug = scenario["id"]
        audio_bytes = await synth(scenario["turns"])

        path = out_dir / f"{idx:02d}_{slug}.mp3"
        path.write_bytes(audio_bytes)
        written.append(path)

        logger.info("Wrote %s (%d bytes)", path, len(audio_bytes))

    logger.info("Exported %d audio files to %s", len(written), out_dir)
    return written


def main() -> None:
    """CLI entrypoint for exporting synthetic audio."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="Export synthetic call audio to disk")
    parser.add_argument("--count", type=int, default=None, help="Number of scenarios to export")
    parser.add_argument("--out", type=str, default="data/audio", help="Output directory")
    parser.add_argument("--scenario", type=str, default=None, help="Export a single scenario by ID")
    args = parser.parse_args()

    written = asyncio.run(
        export_audio(
            count=args.count,
            out_dir=Path(args.out),
            scenario_id=args.scenario,
        )
    )

    print(f"\nDone — {len(written)} file(s) written to {args.out}/")
    for p in written:
        print(f"  {p}")

    sys.exit(0)


if __name__ == "__main__":
    main()
