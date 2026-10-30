"""Upload structured workouts to the intervals.icu calendar.

intervals.icu parses the plain-text workout syntax in an event's ``description``
into structured steps, so uploading is just: POST one WORKOUT event per session.

Reads credentials from the environment or a local ``.env`` (gitignored):
    INTERVALS_ATHLETE_ID=i751377
    INTERVALS_API_KEY=...

Plan file is JSON: a list of sessions, e.g.
    [
      {"date": "2026-11-03", "name": "FTP Test (RM 20min)", "description": "Warmup\\n- 15m ramp 45-65%\\n..."},
      {"date": "2026-11-05", "name": "SV1 Base 60m", "type": "Ride", "description": "..."}
    ]

Usage:
    uv run python -m rmcycling.upload plan.json            # upload
    uv run python -m rmcycling.upload plan.json --dry-run  # print, don't send
    uv run python -m rmcycling.upload --set-ftp 265 --weight 71
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from .logging_setup import get_logger

log = get_logger()

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_BASE = "https://intervals.icu/api/v1"


def _load_env() -> tuple[str, str]:
    env: dict[str, str] = {}
    dotenv = Path(".env")
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    import os

    aid = os.environ.get("INTERVALS_ATHLETE_ID") or env.get("INTERVALS_ATHLETE_ID")
    key = os.environ.get("INTERVALS_API_KEY") or env.get("INTERVALS_API_KEY")
    if not aid or not key:
        sys.exit("Missing INTERVALS_ATHLETE_ID / INTERVALS_API_KEY (set env or .env)")
    return aid, key


class IntervalsClient:
    """Minimal intervals.icu REST client (stdlib only)."""

    def __init__(self, athlete_id: str, api_key: str) -> None:
        self.athlete_id = athlete_id
        auth = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {auth}",
            "User-Agent": _UA,  # Cloudflare 1010s a default urllib UA
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        url = f"{_BASE}/athlete/{self.athlete_id}{path}"
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                txt = r.read().decode()
                return r.status, (json.loads(txt) if txt else None)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()[:500]

    def create_workout(
        self, date: str, name: str, description: str, wtype: str = "Ride"
    ) -> tuple[int, object]:
        """Create a planned WORKOUT event. `date` is YYYY-MM-DD."""
        body = {
            "category": "WORKOUT",
            "start_date_local": f"{date}T00:00:00",
            "type": wtype,
            "name": name,
            "description": description,
        }
        return self._call("POST", "/events", body)

    def list_workouts(self, oldest: str, newest: str) -> list[dict]:
        """List planned WORKOUT events between two YYYY-MM-DD dates (inclusive)."""
        status, evs = self._call(
            "GET", f"/events?oldest={oldest}&newest={newest}&category=WORKOUT"
        )
        return evs if status == 200 and isinstance(evs, list) else []

    def delete_event(self, event_id: int) -> int:
        status, _ = self._call("DELETE", f"/events/{event_id}")
        return status

    def set_ftp(self, ftp: int | None, weight: float | None) -> tuple[int, object]:
        """Update cycling FTP and/or weight on the athlete profile."""
        settings: dict = {}
        if ftp is not None:
            settings["ftp"] = ftp
        if weight is not None:
            settings["icu_weight"] = weight
        return self._call("PUT", "/settings", settings)


def upload_plan(plan_path: str, dry_run: bool = False, replace: bool = False) -> int:
    sessions = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    client = IntervalsClient(*_load_env())

    if replace and sessions and not dry_run:
        dates = [s["date"] for s in sessions]
        existing = client.list_workouts(min(dates), max(dates))
        for e in existing:
            client.delete_event(e["id"])
        log.info("replace: removed %d existing workout(s) in range", len(existing))

    failures = 0
    for s in sessions:
        name, date = s["name"], s["date"]
        if dry_run:
            log.info("[dry-run] %s  %s", date, name)
            continue
        status, resp = client.create_workout(
            date, name, s["description"], s.get("type", "Ride")
        )
        if status == 200 and isinstance(resp, dict):
            log.info("uploaded %s  %s  (load=%s)", date, name, resp.get("icu_training_load"))
        else:
            failures += 1
            log.error("FAILED %s %s -> %s %s", date, name, status, resp)
    log.info("done: %d ok, %d failed", len(sessions) - failures, failures)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rmcycling-upload")
    p.add_argument("plan", nargs="?", help="plan.json with sessions to upload")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing planned workouts in the plan's date range before uploading",
    )
    p.add_argument("--set-ftp", type=int, help="Set cycling FTP on the profile")
    p.add_argument("--weight", type=float, help="Set weight (kg) on the profile")
    args = p.parse_args(argv)

    if args.set_ftp is not None or args.weight is not None:
        client = IntervalsClient(*_load_env())
        status, resp = client.set_ftp(args.set_ftp, args.weight)
        log.info("set profile -> %s", status if status == 200 else f"{status} {resp}")

    if args.plan:
        return upload_plan(args.plan, dry_run=args.dry_run, replace=args.replace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
