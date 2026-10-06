#!/usr/bin/env python3
"""Pull golf rounds from Garmin Connect into data/rounds.json.

Incremental: rounds already saved are kept; only new rounds (and the most
recent one, in case it was edited) get their detail + shot data refetched.

Auth, in order of preference:
  1. GARMIN_TOKENS env var  - the contents of garmin_tokens.json (used by GitHub Actions)
  2. ~/.garminconnect       - tokens saved by a previous interactive login (used locally)
"""
import datetime as dt
import json
import os
import pathlib
import re
import sys

from garminconnect import Garmin

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
RAW = DATA / "raw"
DETAILS = DATA / "details"
ROUNDS_FILE = DATA / "rounds.json"
CLUBS_FILE = DATA / "clubs.json"
STATS_FILE = DATA / "stats.json"

# Fields that identify you on Garmin. Dropped before anything is committed.
PRIVATE_FIELDS = {"customerId", "playerProfileId"}


def login() -> Garmin:
    client = Garmin(os.environ.get("GARMIN_EMAIL") or None,
                    os.environ.get("GARMIN_PASSWORD") or None)
    tokens = os.environ.get("GARMIN_TOKENS")
    # login() accepts either a token-store path or the token JSON itself.
    client.login(tokens if tokens else "~/.garminconnect")
    return client


# Keys dropped from the public detail files: anything that locates you on the
# course or identifies your Garmin account.
_PRIVATE_KEY = re.compile(
    r"(lat|lon|lng|latitude|longitude|loc|pos)$|location|position|coordinate|gps|"
    r"customer|profile|userid|displayname|fullname|email|username",
    re.IGNORECASE,
)


def sanitize(obj):
    """Recursively remove location and identity fields."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items() if not _PRIVATE_KEY.search(k)}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj


def save_if_changed(path: pathlib.Path, data) -> bool:
    text = json.dumps(data, indent=2, sort_keys=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def clean(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in PRIVATE_FIELDS}


def save_json(path: pathlib.Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def fetch_all_summaries(client: Garmin) -> list[dict]:
    rows, start, page = [], 0, 100
    while True:
        resp = client.get_golf_summary(start=start, limit=page)
        batch = resp.get("scorecardSummaries", []) if isinstance(resp, dict) else resp
        rows.extend(batch)
        if len(batch) < page:
            return rows
        start += page


def main() -> int:
    DATA.mkdir(exist_ok=True)
    existing = {}
    if ROUNDS_FILE.exists():
        old = json.loads(ROUNDS_FILE.read_text(encoding="utf-8"))
        existing = {r["id"]: r for r in old.get("rounds", [])}

    client = login()
    summaries = fetch_all_summaries(client)
    if not summaries:
        print("Garmin returned no rounds; leaving data untouched.")
        return 0

    newest_id = max(summaries, key=lambda r: r.get("startTime", ""))["id"]
    merged = dict(existing)

    for row in summaries:
        sid = row["id"]
        merged[sid] = clean(row)

        needs_detail = (
            sid not in existing
            or sid == newest_id
            or row.get("roundInProgress")
            or not (DETAILS / f"{sid}.json").exists()
        )
        if not needs_detail:
            continue

        detail = {}
        for name, fn in (("scorecard", client.get_golf_scorecard),
                         ("shots", client.get_golf_shot_data)):
            try:
                raw = fn(sid)
                save_json(RAW / f"{sid}_{name}.json", raw)  # git-ignored, full fidelity
                detail[name] = sanitize(raw)
                print(f"saved {sid} {name}")
            except Exception as exc:  # shot data is missing for some rounds
                print(f"skipped {sid} {name}: {exc}")
        if detail:
            save_if_changed(DETAILS / f"{sid}.json", detail)

    # Account-wide club distances and overall stats (best effort).
    for path, fn, label in ((CLUBS_FILE, client.get_golf_club_stats, "clubs"),
                            (STATS_FILE, client.get_golf_user_stats, "stats")):
        try:
            if save_if_changed(path, sanitize(fn())):
                print(f"updated {label}")
        except Exception as exc:
            print(f"skipped {label}: {exc}")

    rounds = sorted(merged.values(), key=lambda r: r.get("startTime", ""))
    out = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rounds": rounds,
    }

    # Only rewrite when rounds changed, so a no-op run doesn't create a commit.
    if ROUNDS_FILE.exists():
        prev = json.loads(ROUNDS_FILE.read_text(encoding="utf-8"))
        if prev.get("rounds") == rounds:
            print("No changes.")
            return 0

    save_json(ROUNDS_FILE, out)
    print(f"Wrote {len(rounds)} rounds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
