#!/usr/bin/env python3
"""Render a terminal-style narrated demo video from captured CLI output."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1280, 720
BG = "#0e141b"
FG = "#dce6ee"
MUTED = "#93a2b2"
CYAN = "#75d3ed"
MINT = "#66e3bd"
AMBER = "#f3c77a"
LINE = "#263543"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["/System/Library/Fonts/Supplemental/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"]
        if not bold else
        ["/System/Library/Fonts/Supplemental/Menlo.ttc", "/System/Library/Fonts/Menlo.ttc"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size, index=1 if bold else 0)
        except OSError:
            continue
    return ImageFont.load_default()


FONT = load_font(18)
FONT_SMALL = load_font(14)
FONT_TITLE = load_font(22, bold=True)


def extract(text: str, start: str, end: str | None = None) -> list[str]:
    i = text.find(start)
    if i < 0:
        return [f"Missing expected CLI section: {start}"]
    i += len(start)
    j = text.find(end, i) if end else len(text)
    part = text[i:j if j >= 0 else len(text)].strip()
    return part.splitlines()


def prepare_lines(lines: list[str], width: int = 92) -> list[str]:
    result: list[str] = []
    for line in lines:
        if not line.strip():
            result.append("")
        else:
            result.extend(textwrap.wrap(line, width=width, subsequent_indent="  ") or [""])
    return result


def make_slide(title: str, lines: list[str], command: str, outfile: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.text((48, 26), "stock-research   ·   zsh   ·   read-only", fill=MUTED, font=FONT_SMALL)
    draw.text((48, 71), "$ " + command, fill=MINT, font=FONT_TITLE)
    draw.line((48, 111, WIDTH - 48, 111), fill=LINE, width=1)
    draw.text((48, 132), title, fill=CYAN, font=FONT_TITLE)
    y = 173
    max_rows = 20
    for line in prepare_lines(lines)[:max_rows]:
        if line.startswith("## "):
            color = MINT
        elif any(token in line for token in ("SYNTHETIC", "fictional", "DISABLED", "not live")):
            color = AMBER
        else:
            color = FG
        draw.text((52, y), line, fill=color, font=FONT)
        y += 23
    if len(prepare_lines(lines)) > max_rows:
        draw.text((52, y + 2), "…continued in the next view", fill=MUTED, font=FONT_SMALL)
    draw.line((48, HEIGHT - 48, WIDTH - 48, HEIGHT - 48), fill=LINE, width=1)
    draw.text((48, HEIGHT - 36), "NORTHSTAR   ·   DEMO DATA IS FICTIONAL", fill=MUTED, font=FONT_SMALL)
    disclosure = "AI-GENERATED VOICE"
    bbox = draw.textbbox((0, 0), disclosure, font=FONT_SMALL)
    draw.text((WIDTH - 48 - (bbox[2] - bbox[0]), HEIGHT - 36), disclosure, fill=AMBER, font=FONT_SMALL)
    image.save(outfile)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True, help="captured output of --demo --ai-brief")
    parser.add_argument("--narration", type=Path, default=ROOT / "demo-narration-ai.txt")
    parser.add_argument("--audio", type=Path, default=ROOT / "media" / "cli-ai-narration.mp3")
    parser.add_argument("--output", type=Path, default=ROOT / "media" / "Stock-Research-CLI-AI-Demo.mp4")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        parser.error("ffmpeg and ffprobe are required")
    if not args.audio.is_file():
        parser.error(f"narration audio not found: {args.audio}")

    output = args.transcript.read_text(encoding="utf-8")
    ai_start = output.find("## Snapshot context")
    ai_lines = output[ai_start:].splitlines() if ai_start >= 0 else ["AI brief was not found in the CLI capture."]
    ai_head = ai_lines[:20]
    ai_tail = ai_lines[20:40]
    slides: list[tuple[str, list[str]]] = [
        ("Stock Research CLI  |  READ-ONLY", [
            "$ .venv/bin/python stock_research_cli.py --demo --ai-brief",
            "DATA MODE : SYNTHETIC DEMO — fictional companies and metrics",
            "TRADING   : DISABLED — no broker connection or order execution",
            "AI BRIEF  : optional; requested explicitly with --ai-brief",
        ]),
        ("PORTFOLIO + WATCHLIST", extract(output, "PORTFOLIO", "POPULAR / EMERGING-GROWTH SCREEN")),
        ("SCREENING + REVIEW FLAGS", extract(output, "POPULAR / EMERGING-GROWTH SCREEN", "AI RESEARCH BRIEF (OpenAI; supplied data only)")),
        ("AI RESEARCH BRIEF · SNAPSHOT", ai_head),
    ]
    if ai_tail:
        slides.append(("AI RESEARCH BRIEF · RISKS + QUESTIONS", ai_tail))
    slides.append(("RESEARCH SCOPE", [
        "Use dated market snapshots that you can verify.",
        "The screens are prompts for further research, not advice.",
        "No live data feed, brokerage link, or trade execution.",
        "The AI brief runs only when you explicitly add --ai-brief.",
        "Demo names and values shown here are fictional.",
    ]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="stock-cli-video-") as work:
        temp = Path(work)
        pngs = []
        for index, (title, lines) in enumerate(slides, 1):
            png = temp / f"slide-{index:02}.png"
            make_slide(title, lines, ".venv/bin/python stock_research_cli.py --demo --ai-brief", png)
            pngs.append(png)

        duration_text = subprocess.check_output([
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(args.audio),
        ], text=True).strip()
        duration = float(duration_text)
        paragraphs = [p.strip() for p in args.narration.read_text(encoding="utf-8").split("\n\n") if p.strip()]
        counts = [max(1, len(p.split())) for p in paragraphs]
        total_words = sum(counts)
        cumulative = []
        acc = 0
        for count in counts:
            acc += count
            cumulative.append(acc / total_words)
        frame_count = max(1, int(duration + 0.5))
        for frame in range(frame_count):
            portion = (frame + 0.5) / frame_count
            scene = next((i for i, cutoff in enumerate(cumulative) if portion <= cutoff), len(cumulative) - 1)
            scene = min(scene, len(pngs) - 1)
            frame_path = temp / f"frame-{frame:04}.png"
            shutil.copyfile(pngs[scene], frame_path)

        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-framerate", "1", "-i", str(temp / "frame-%04d.png"),
            "-i", str(args.audio), "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
            str(args.output),
        ], check=True)
    print(f"Wrote video: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
