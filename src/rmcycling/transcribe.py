"""Local Whisper fallback (faster-whisper).

Only used when a video has no usable captions. Imported lazily so the base
install stays light (yt-dlp only) — install the model runtime with:
    uv sync --extra whisper
"""

from __future__ import annotations

from .exceptions import TranscriptionError, WhisperNotInstalledError
from .logging_setup import get_logger, timing

log = get_logger()


@timing
def transcribe_audio(
    wav_path: str,
    model_size: str = "large-v3",
    language: str | None = "fr",
) -> list[tuple[float, str]]:
    """Transcribe a wav into (start_seconds, text) cues, shaped like captions.parse_vtt."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise WhisperNotInstalledError(
            "faster-whisper is not installed. Run: uv sync --extra whisper"
        ) from exc

    log.info("loading Whisper model %s (first run downloads it)…", model_size)
    # int8 runs comfortably on an Apple-silicon CPU without a GPU.
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    try:
        segments, info = model.transcribe(wav_path, language=language, vad_filter=True)
        log.info("detected language %s (p=%.2f)", info.language, info.language_probability)
        return [(seg.start, seg.text.strip()) for seg in segments if seg.text.strip()]
    except Exception as exc:  # noqa: BLE001
        raise TranscriptionError(f"Whisper failed on {wav_path}: {exc}") from exc
