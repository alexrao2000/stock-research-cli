#!/usr/bin/env python3
"""Create a clearly disclosed AI narration MP3 for the CLI demo."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openai_features import generate_speech


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, default=ROOT / "demo-narration-ai.txt")
    parser.add_argument("--output", type=Path, default=ROOT / "media" / "cli-ai-narration.mp3")
    parser.add_argument("--voice", default="marin", help="OpenAI speech voice (default: marin)")
    args = parser.parse_args()
    text = args.script.read_text(encoding="utf-8").strip()
    if len(text) > 4096:
        parser.error("narration script must be at most 4096 characters")
    try:
        generate_speech(text, args.output, ROOT, voice=args.voice)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f"narration: {exc}\n")
    print(f"Wrote narration: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
