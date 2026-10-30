"""Command-line entry point.

    rmcycling URL [URL ...]
    rmcycling --urls-file videos.txt --out workouts
    rmcycling URL --whisper            # force the local Whisper path
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .exceptions import RMCyclingError
from .logging_setup import get_logger
from .output import write_transcript
from .pipeline import transcribe_video

log = get_logger()


def _read_urls_file(path: str) -> list[str]:
    urls = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rmcycling",
        description="Turn YouTube cycling videos into clean transcripts for a Claude session.",
    )
    parser.add_argument("urls", nargs="*", help="YouTube URLs")
    parser.add_argument("--urls-file", help="File with one URL per line (# comments allowed)")
    parser.add_argument("--out", default="workouts", help="Output directory (default: workouts)")
    parser.add_argument(
        "--langs",
        default="fr,en",
        help="Caption language priority, comma-separated (default: fr,en)",
    )
    parser.add_argument(
        "--whisper",
        action="store_true",
        help="Skip captions and always transcribe audio with local Whisper",
    )
    parser.add_argument(
        "--whisper-model", default="large-v3", help="faster-whisper model size"
    )
    parser.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        help="Use cookies from this browser (e.g. chrome, safari) to dodge 429s / bot checks",
    )
    args = parser.parse_args(argv)

    urls = list(args.urls)
    if args.urls_file:
        urls += _read_urls_file(args.urls_file)
    if not urls:
        parser.error("no URLs given (pass URLs or --urls-file)")

    langs = tuple(x.strip() for x in args.langs.split(",") if x.strip())

    failures = 0
    for url in urls:
        try:
            result = transcribe_video(
                url,
                langs=langs,
                force_whisper=args.whisper,
                whisper_model=args.whisper_model,
                cookies_from_browser=args.cookies_from_browser,
            )
            path = write_transcript(result, args.out)
            log.info("wrote %s (via %s)", path, result.source)
        except RMCyclingError as exc:
            failures += 1
            log.error("FAILED %s: %s", url, exc)

    log.info("done: %d ok, %d failed", len(urls) - failures, failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
