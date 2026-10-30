"""Typed exception hierarchy.

Same idea as GrooverAudio's custom exceptions: typed errors make failures easy
to catch per-stage and easy to count/alert on later.
"""

from __future__ import annotations


class RMCyclingError(Exception):
    """Base class for all errors raised by this tool."""


class DownloadError(RMCyclingError):
    """yt-dlp failed to fetch the video metadata, subtitles, or audio."""


class NoCaptionsError(RMCyclingError):
    """The video has no usable subtitles/captions in any requested language."""


class TranscriptionError(RMCyclingError):
    """The Whisper fallback failed to produce a transcript."""


class WhisperNotInstalledError(TranscriptionError):
    """faster-whisper is not installed. Install with: uv sync --extra whisper"""
