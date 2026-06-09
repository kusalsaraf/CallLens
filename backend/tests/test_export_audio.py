"""Tests for the audio export CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from calllens.seed.export_audio import export_audio
from calllens.seed.scenarios import SCENARIOS, Turn


async def _mock_synthesize(turns: list[Turn]) -> bytes:
    """Return deterministic fake audio bytes without pydub/edge-tts."""
    content = "|".join(t["text"][:10] for t in turns)
    return b"\xff\xfb\x90\x00" + content.encode()


class TestExportAudio:
    """Verify export_audio writes the expected files with mocked synthesis."""

    @pytest.mark.asyncio
    async def test_exports_all_scenarios(self, tmp_path: Path) -> None:
        """Exporting all scenarios writes one file per scenario."""
        out = tmp_path / "audio"
        written = await export_audio(out_dir=out, synthesize_fn=_mock_synthesize)

        assert len(written) == len(SCENARIOS)
        for p in written:
            assert p.exists()
            assert p.stat().st_size > 0
            assert p.suffix == ".mp3"

    @pytest.mark.asyncio
    async def test_exports_count(self, tmp_path: Path) -> None:
        """--count limits the number of exported files."""
        out = tmp_path / "audio"
        written = await export_audio(count=3, out_dir=out, synthesize_fn=_mock_synthesize)

        assert len(written) == 3

    @pytest.mark.asyncio
    async def test_exports_single_scenario(self, tmp_path: Path) -> None:
        """--scenario exports exactly one matching file."""
        slug = SCENARIOS[0]["id"]
        out = tmp_path / "audio"
        written = await export_audio(scenario_id=slug, out_dir=out, synthesize_fn=_mock_synthesize)

        assert len(written) == 1
        assert slug in written[0].name

    @pytest.mark.asyncio
    async def test_unknown_scenario_raises(self, tmp_path: Path) -> None:
        """An unknown scenario ID raises ValueError."""
        out = tmp_path / "audio"
        with pytest.raises(ValueError, match="Unknown scenario"):
            await export_audio(
                scenario_id="nonexistent", out_dir=out, synthesize_fn=_mock_synthesize
            )

    @pytest.mark.asyncio
    async def test_creates_output_dir(self, tmp_path: Path) -> None:
        """Output directory is created if it doesn't exist."""
        out = tmp_path / "nested" / "dir" / "audio"
        assert not out.exists()

        written = await export_audio(count=1, out_dir=out, synthesize_fn=_mock_synthesize)

        assert out.exists()
        assert len(written) == 1
