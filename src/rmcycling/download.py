"""yt-dlp wrappers: fetch metadata + one subtitle track, and audio for Whisper.

Two-phase on purpose. Metadata (``download=False``) is cheap and never hits
YouTube's subtitle rate-limiter. Subtitle download (the ``timedtext`` endpoint)
is aggressively throttled, so we request a *single* language, self-throttle, and
treat a 429 as "no captions" — the pipeline then falls back to Whisper.

Reimplements GrooverAudio's download-with-retry pattern without its proxy/token
plumbing. ``cookies_from_browser`` is the escape hatch when YouTube tightens up.
"""

from __future__ import annotations

import glob
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError as YTDLPDownloadError

from .exceptions import DownloadError
from .logging_setup import get_logger, timing

log = get_logger()

_MAX_RETRIES = 3
_BASE_BACKOFF = 2.0  # seconds, grows linearly with jitter


@dataclass
class VideoData:
    """Everything we pulled for one video."""

    id: str
    title: str
    description: str
    uploader: str
    duration: int  # seconds
    webpage_url: str
    chapters: list[dict] = field(default_factory=list)
    # lang -> path to a .vtt file on disk
    subtitle_files: dict[str, str] = field(default_factory=dict)
    # langs that have human-authored (not auto-generated) subtitles
    manual_sub_langs: set[str] = field(default_factory=set)


def _base_opts(cookies_from_browser: str | None) -> dict:
    opts: dict = {"quiet": True, "no_warnings": True, "noprogress": True}
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    return opts


def _with_retries(fn, *, what: str):
    """Run fn() with a few retries and linear backoff + jitter."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return fn()
        except YTDLPDownloadError as exc:  # noqa: PERF203
            last_exc = exc
            wait = _BASE_BACKOFF * attempt + random.uniform(0, 1.5)
            log.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                what, attempt, _MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    raise DownloadError(f"{what} failed after {_MAX_RETRIES} attempts: {last_exc}")


def _choose_lang(
    manual: dict, auto: dict, langs: tuple[str, ...]
) -> tuple[str | None, bool]:
    """Pick the best available subtitle lang. Prefer manual, then the original/auto.

    Returns (lang_code, is_manual). We prefer the *original* language (e.g. fr)
    over YouTube's machine-translated tracks (e.g. en-from-fr) — Claude does the
    translating better than YouTube does.
    """
    for want in langs:
        for have in manual:
            if have.split("-")[0] == want:
                return have, True
    for want in langs:
        for have in auto:
            if have.split("-")[0] == want:
                return have, False
    return None, False


@timing
def fetch_video(
    url: str,
    workdir: str | Path,
    langs: tuple[str, ...] = ("fr", "en"),
    cookies_from_browser: str | None = None,
) -> VideoData:
    """Fetch metadata, then download the single best subtitle track (if any)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    # Phase 1: metadata only — robust, no timedtext calls.
    meta_opts = _base_opts(cookies_from_browser) | {"skip_download": True}

    def _meta() -> dict:
        with YoutubeDL(meta_opts) as ydl:
            return ydl.extract_info(url, download=False)

    info = _with_retries(_meta, what=f"metadata for {url}")

    vid_id = info.get("id", "unknown")
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    lang, is_manual = _choose_lang(manual, auto, langs)

    subtitle_files: dict[str, str] = {}
    manual_sub_langs: set[str] = set()

    # Phase 2: one subtitle language, tolerant of 429 / timedtext failures.
    if lang:
        path = _download_one_subtitle(
            url, lang, is_manual, workdir, cookies_from_browser
        )
        if path:
            subtitle_files[lang] = path
            if is_manual:
                manual_sub_langs.add(lang)
    else:
        log.info("no subtitles advertised for %s in %s", url, langs)

    return VideoData(
        id=vid_id,
        title=info.get("title", ""),
        description=info.get("description") or "",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration=int(info.get("duration") or 0),
        webpage_url=info.get("webpage_url") or url,
        chapters=info.get("chapters") or [],
        subtitle_files=subtitle_files,
        manual_sub_langs=manual_sub_langs,
    )


def _download_one_subtitle(
    url: str,
    lang: str,
    is_manual: bool,
    workdir: Path,
    cookies_from_browser: str | None,
) -> str | None:
    """Download exactly one subtitle track. Return its path, or None on failure."""
    opts = _base_opts(cookies_from_browser) | {
        "skip_download": True,
        "writesubtitles": is_manual,
        "writeautomaticsub": not is_manual,
        "subtitleslangs": [lang],
        "subtitlesformat": "vtt",
        "sleep_interval_subtitles": 2,  # self-throttle to dodge 429
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        matches = glob.glob(str(workdir / f"{info['id']}.{lang}*.vtt"))
        if matches:
            return matches[0]
        log.warning("subtitle download for %s reported no file", lang)
        return None
    except YTDLPDownloadError as exc:
        log.warning("subtitle download for %s failed (will try Whisper): %s", lang, exc)
        return None


@timing
def download_audio(
    url: str, workdir: str | Path, cookies_from_browser: str | None = None
) -> str:
    """Download audio only and return the path to a 16 kHz mono wav (for Whisper)."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_base = str(workdir / "%(id)s")

    opts = _base_opts(cookies_from_browser) | {
        "format": "bestaudio/best",
        "outtmpl": out_base,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        # 16 kHz mono is what Whisper wants; let ffmpeg resample.
        "postprocessor_args": {"extractaudio+ffmpeg_o": ["-ac", "1", "-ar", "16000"]},
    }

    def _run() -> dict:
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=True)

    info = _with_retries(_run, what=f"audio for {url}")
    wav = workdir / f"{info['id']}.wav"
    if not wav.exists():
        raise DownloadError(f"expected audio at {wav} but it is missing")
    return str(wav)
