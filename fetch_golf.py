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
import sys

from garminconnect import Garmin

ROOT = pathlib.Path(__file__).parent
DATA = ROOT / "data"
RAW = DATA / "raw"
ROUNDS_FILE = DATA / "rounds.json"

# Fields that identify you on Garmin. Dropped before anything is committed.
PRIVATE_FIELDS = {"customerId", "playerProfileId"}


   def login() -> Garmin:
       client = Garmin(os.environ.get("GARMIN_EMAIL") or None,
                       os.environ.get("GARMIN_PASSWORD") or None)
       tokens = os.environ.get("GARMIN_TOKENS")
       client.login(tokens if tokens else "~/.garminconnect")
       return client


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
        )
        if not needs_detail:
            continue

        for name, fn in (("scorecard", client.get_golf_scorecard),
                         ("shots", client.get_golf_shot_data)):
            try:
                save_json(RAW / f"{sid}_{name}.json", fn(sid))
                print(f"saved {sid} {name}")
            except Exception as exc:  # shot data is missing for some rounds
                print(f"skipped {sid} {name}: {exc}")

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
