# Prompt: synthesize RM's method into my 2-week plan

Use this when the transcripts are RM Methodic's **methodology/education** videos
(SV1, FTP testing, winter periodization, 8-day blocks, home-trainer) rather than
single follow-along sessions. Paste this prompt, then `profile.md`, then several
transcript markdown files from `workouts/`, into a Claude session (Sonnet 5 is fine).

---

You are a cycling coach. I'll give you (1) my athlete profile and (2) transcripts
of several French-language RM Methodic Cycling videos that explain *how* they train
(not single workouts). Synthesize their method into a concrete plan for me.

**Do this:**

1. **Extract RM's training principles** from the transcripts, in English: how they
   structure winter base, SV1 (premier seuil) development, FTP/threshold work,
   VO2max, the 8-day block idea, intensity distribution, FTP testing, recovery.
   Note where the videos actually give numbers (durations, %FTP, zones, RPE) vs
   where they speak only in general terms.

2. **Build me a 2-week block** (my planning window) of indoor trainer sessions on
   the Wahoo Kickr Core, applying their method to my profile:
   - 3–4 trainer sessions/week, leaving room for 1–2 CrossFit sessions (drop
     CrossFit to 1 in a 4-session week). Lay out which day is what.
   - A sensible intensity mix for a 71 kg rider whose goal is to raise FTP ~15–20%
     over the winter and climb faster — bias early blocks toward SV1/aerobic base,
     then introduce threshold and VO2max.
   - If my FTP is marked TBD, make **session 1 an FTP test** (use RM's own test
     protocol from the transcript) and express everything else in %FTP.

3. **Write each session out** in two formats so I can load it:
   - **intervals.icu text syntax** (e.g. `Warmup 10m ramp 50%-75%`, `4x`,
     `- 2m 95%`, `- 2m 55%`, `Cooldown 5m ramp 60%-40%`; blank lines around repeats).
   - A **Zwift `.zwo`** file (XML: `<Warmup>`, `<SteadyState>`, `<IntervalsT>`,
     `<Cooldown>`; power as a decimal fraction of FTP, durations in seconds).

4. **Explain the "why"** briefly per session — which RM principle it applies and
   what adaptation it targets — so I understand the plan, not just follow it.

5. **Flag** anything you inferred or that conflicts between videos, and call out
   where RM's method assumes more training volume than my 3–4 sessions/week allow
   (and how you adapted for that).

Keep it realistic for someone also doing CrossFit. Don't invent numeric precision
the transcripts don't support — when RM speaks in zones/feel, map to a %FTP range
and say you did.
