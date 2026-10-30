"""Orchestration: one YouTube URL -> one clean transcript, captions-first."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import captions
from .download import VideoData, download_audio, fetch_video
from .exceptions import NoCaptionsError
from .logging_setup import get_logger

log = get_logger()

# Below this many characters, captions are treated as missing/useless.
_MIN_USABLE_CHARS = 400


@dataclass
class TranscriptResult:
    video: VideoData
    language: str  # language the transcript text is in
    source: str  # "manual-captions" | "auto-captions" | "whisper"
    cues: list[tuple[float, str]]

    @property
    def plaintext(self) -> str:
        return captions.to_plaintext(self.cues)

    @property
    def timestamped(self) -> str:
        return captions.to_timestamped(self.cues)


def _pick_caption_lang(video: VideoData, langs: tuple[str, ...]) -> str | None:
    """Prefer requested langs in order; prefer manual over auto within a lang."""
    # exact/base-language match in requested priority order
    for want in langs:
        for have in video.subtitle_files:
            if have.split("-")[0] == want:
                return have
    # otherwise any subtitle we got
    return next(iter(video.subtitle_files), None)


def transcribe_video(
    url: str,
    langs: tuple[str, ...] = ("fr", "en"),
    force_whisper: bool = False,
    whisper_model: str = "large-v3",
    cookies_from_browser: str | None = None,
) -> TranscriptResult:
    with tempfile.TemporaryDirectory(prefix="rmcycling-") as tmp:
        video = fetch_video(
            url, tmp, langs=langs, cookies_from_browser=cookies_from_browser
        )
        log.info("fetched %r (%ds) by %s", video.title, video.duration, video.uploader)

        if not force_whisper:
            lang = _pick_caption_lang(video, langs)
            if lang:
                cues = captions.parse_vtt(video.subtitle_files[lang])
                text = captions.to_plaintext(cues)
                if len(text) >= _MIN_USABLE_CHARS:
                    source = (
                        "manual-captions"
                        if lang in video.manual_sub_langs
                        else "auto-captions"
                    )
                    log.info("using %s (%s), %d chars", source, lang, len(text))
                    return TranscriptResult(video, lang, source, cues)
                log.info("captions for %s too short (%d chars) — falling back", lang, len(text))

        # Whisper fallback
        log.info("transcribing audio with Whisper (%s)…", whisper_model)
        from .transcribe import transcribe_audio  # lazy: optional dependency

        wav = download_audio(url, tmp, cookies_from_browser=cookies_from_browser)
        cues = transcribe_audio(wav, model_size=whisper_model, language=langs[0])
        if not cues:
            raise NoCaptionsError(f"no captions and Whisper produced nothing for {url}")
        return TranscriptResult(video, langs[0], "whisper", cues)
