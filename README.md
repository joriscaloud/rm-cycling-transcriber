# rm-cycling-transcriber

Turn [RM Methodic Cycling](https://www.youtube.com/@RMMethodicCycling) (French)
YouTube training videos into clean text transcripts, then feed them to a Claude
session that reconstructs the workout, scales it to my FTP, and emits
intervals.icu / Zwift `.zwo` output for my Wahoo Kickr Core.

This repo is **just the transcription step**. The coaching intelligence
(translating, reading the interval structure, scaling, scheduling) happens in a
Claude session — see [`prompts/build_workout.md`](prompts/build_workout.md).

## How it works

```
YouTube URL
   │  yt-dlp
   ▼
description + chapters + French captions   ──►  clean markdown transcript
   │  (if captions missing/useless)                     │
   ▼                                                     ▼
audio → local Whisper (faster-whisper)        paste into a Claude session
                                              with profile.md + the prompt
                                                     │
                                                     ▼
                              intervals.icu workout syntax + .zwo + 2-week plan
                                                     │  sync
                                                     ▼
                                      Zwift → ERG on Wahoo Kickr Core v2
```

**Captions-first** on purpose: YouTube's own French subtitles are free and
instant, and the video description often already contains the session. Whisper
only runs when a video has no usable captions.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) and `ffmpeg` (`brew install ffmpeg`).

```bash
uv sync                    # base install (yt-dlp only)
uv sync --extra whisper    # add the local Whisper fallback (optional, larger)
```

## Usage

```bash
# transcribe the curated list
uv run rmcycling --urls-file videos.txt --out workouts

# one-off
uv run rmcycling "https://www.youtube.com/watch?v=coWRxDydPy4"

# force the Whisper path (e.g. captions are wrong)
uv run rmcycling "<url>" --whisper
```

Transcripts land in `workouts/` as markdown (gitignored). Each file has the
title, channel, duration, chapters, description, and a timestamped transcript.

## Then: build the plan / workout

The curated `videos.txt` list is RM's **methodology** videos (SV1, FTP testing,
winter periodization, 8-day blocks), not single follow-along sessions — so the main
flow synthesizes them into a personalized plan:

**For a 2-week plan** (use these method videos) — open a Claude session and paste:
1. `prompts/build_plan.md`
2. `profile.md` (fill in your FTP first)
3. several transcripts from `workouts/`

**For a single session** (a follow-along workout video) — paste instead:
1. `prompts/build_workout.md`
2. `profile.md`
3. one transcript from `workouts/`

Either way you get intervals.icu syntax + a `.zwo` file + where it fits your block.

## Roadmap (not built yet)

- **Phase 2:** a small `upload.py` that POSTs the generated workout to the
  intervals.icu calendar API (basic auth with an API key) so it auto-syncs to Zwift.
- **Phase 3:** optional frame-grab OCR for videos whose power targets live only in
  on-screen graphics, not speech.

## Notes

- Personal project, for personal training use. Transcripts of third-party videos
  are kept local (gitignored), not committed.
- The transcription patterns (download-with-retry, typed exceptions, logging) are
  reimplemented cleanly, not copied from any employer codebase.
