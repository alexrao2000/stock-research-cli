#!/usr/bin/env python3
"""Generate demo narration WAVs with a neural Microsoft Edge voice."""

from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import edge_tts

VOICE = "en-US-AndrewMultilingualNeural"
RATE = "-8%"


def read_scenes(path: Path) -> list[tuple[int, str]]:
    content = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?m)^Scene\s+(\d+)\s*$", content))
    scenes: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        text = content[match.end():end].strip()
        if text:
            scenes.append((int(match.group(1)), text))
    if not scenes:
        raise ValueError(f"No 'Scene N' sections found in {path}")
    return scenes


async def render(scenes: list[tuple[int, str]], out_dir: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to convert generated audio to WAV")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stock-narration-") as temporary:
        for number, text in scenes:
            mp3 = Path(temporary) / f"scene-{number}.mp3"
            communicate = edge_tts.Communicate(text, voice=VOICE, rate=RATE)
            await communicate.save(str(mp3))
            wav = out_dir / f"scene-{number}.wav"
            subprocess.run(
                [ffmpeg, "-y", "-v", "error", "-i", str(mp3), "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
                check=True,
            )
            print(f"Wrote {wav}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=Path("narration.txt"))
    parser.add_argument("--output", type=Path, default=Path("media"))
    args = parser.parse_args()
    asyncio.run(render(read_scenes(args.script), args.output))


if __name__ == "__main__":
    main()
