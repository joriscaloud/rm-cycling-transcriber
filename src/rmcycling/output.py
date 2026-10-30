"""Write a transcript as a self-contained markdown file to paste into Claude."""

from __future__ import annotations

import re
from pathlib import Path

from .pipeline import TranscriptResult


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", text)[:60] or "video"


def _mmss(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def render_markdown(result: TranscriptResult) -> str:
    v = result.video
    parts: list[str] = []
    parts.append(f"# {v.title}\n")
    parts.append(f"- **URL:** {v.webpage_url}")
    parts.append(f"- **Channel:** {v.uploader}")
    parts.append(f"- **Duration:** {_mmss(v.duration)}")
    parts.append(f"- **Transcript source:** {result.source} ({result.language})\n")

    if v.chapters:
        parts.append("## Chapters\n")
        for ch in v.chapters:
            parts.append(f"- [{_mmss(ch.get('start_time', 0))}] {ch.get('title', '')}")
        parts.append("")

    if v.description.strip():
        parts.append("## Description\n")
        parts.append(v.description.strip() + "\n")

    parts.append("## Transcript (timestamped)\n")
    parts.append(result.timestamped + "\n")

    return "\n".join(parts)


def write_transcript(result: TranscriptResult, outdir: str | Path) -> Path:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    filename = f"{_slug(result.video.title)}--{result.video.id}.md"
    path = outdir / filename
    path.write_text(render_markdown(result), encoding="utf-8")
    return path
