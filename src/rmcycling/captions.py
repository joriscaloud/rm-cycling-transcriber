"""Parse WebVTT subtitle files into clean text.

YouTube auto-captions are messy: cues overlap, each line is repeated as the
"rolling" caption scrolls, and words carry inline timing tags like
``<00:00:01.234><c>word</c>``. This strips all of that and de-duplicates.
"""

from __future__ import annotations

import re
from pathlib import Path

# <00:00:01.234> and <c>...</c> inline timing/style tags
_INLINE_TAG = re.compile(r"<[^>]+>")
# "00:00:01.234 --> 00:00:03.456 align:start position:0%"
_TIMESTAMP = re.compile(
    r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})"
)


def _ts_to_seconds(ts: str) -> float:
    ts = ts.replace(",", ".")
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _mmss(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def parse_vtt(path: str | Path) -> list[tuple[float, str]]:
    """Return a de-duplicated list of (start_seconds, text_line) items.

    YouTube's rolling auto-captions repeat each spoken line across cues: a line
    first appears (with inline word-timing tags) in the cue where it's spoken,
    then again as the "finalized" top line of the next cue. So we work at the
    *line* level and drop consecutive duplicates, which collapses the roll.
    """
    raw = Path(path).read_text(encoding="utf-8", errors="replace")

    lines: list[tuple[float, str]] = []
    start: float | None = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TIMESTAMP.search(line)
        if m:
            start = _ts_to_seconds(m.group(1))
            continue
        if line == "WEBVTT" or line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if start is None:
            continue  # cue index numbers / stray headers
        cleaned = _INLINE_TAG.sub("", line).strip()
        if cleaned:
            lines.append((start, cleaned))

    return _dedupe(lines)


def _dedupe(lines: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Collapse consecutive identical caption lines (the rolling-display repeats)."""
    out: list[tuple[float, str]] = []
    for start, text in lines:
        if out and text == out[-1][1]:
            continue
        out.append((start, text))
    return out


def to_plaintext(cues: list[tuple[float, str]]) -> str:
    """Join cues into flowing paragraphs (no timestamps)."""
    return " ".join(text for _, text in cues)


def to_timestamped(cues: list[tuple[float, str]], every_seconds: int = 30) -> str:
    """One line per ~`every_seconds` with a [mm:ss] marker — good for locating intervals."""
    lines: list[str] = []
    bucket_start: float | None = None
    bucket: list[str] = []

    def flush() -> None:
        nonlocal bucket_start, bucket
        if bucket_start is not None and bucket:
            lines.append(f"[{_mmss(bucket_start)}] " + " ".join(bucket))
        bucket_start, bucket = None, []

    for start, text in cues:
        if bucket_start is None:
            bucket_start = start
        if start - bucket_start >= every_seconds:
            flush()
            bucket_start = start
        bucket.append(text)
    flush()
    return "\n".join(lines)
