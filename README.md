# Golf tracker

A static site (GitHub Pages) showing your Garmin golf rounds: scorecards, score trend,
results by hole, scoring by par type, and per-course stats.

```
Garmin Connect  ->  fetch_golf.py  ->  data/rounds.json  ->  index.html (GitHub Pages)
```

The browser never talks to Garmin. A script pulls your rounds into `data/rounds.json`,
and the page only reads that file.

## 1. First run on your Mac

With your `garmin-env` virtual environment active and the tokens you already saved in
`~/.garminconnect`:

```bash
python fetch_golf.py
python -m http.server 8000
```

Open http://localhost:8000. (Opening `index.html` by double-click won't work, because
browsers block `fetch` on `file://` pages.)

## 2. Put it on GitHub

```bash
git init
git add .
git commit -m "Golf tracker"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/golf-tracker.git
git push -u origin main
```

Then in the repo: Settings > Pages > Build and deployment > Deploy from a branch >
`main` / `(root)`. The site appears at `https://YOUR-USERNAME.github.io/golf-tracker/`.

Privacy: GitHub Pages on a free account needs a public repo, so `data/rounds.json`
(courses, dates, scores) will be public. Garmin account IDs are stripped by the script.
`data/raw/` (full scorecards and shot data) is git-ignored on purpose.

## 3. Keep it updated

### Option A: GitHub Actions (hands-off, may be blocked)

`.github/workflows/update.yml` runs every 6 hours.

1. Copy your saved tokens: `pbcopy < ~/.garminconnect/garmin_tokens.json`
2. Repo > Settings > Secrets and variables > Actions > New repository secret.
   Name: `GARMIN_TOKENS`, value: paste.
3. Actions tab > Update golf data > Run workflow, to test it.

Known risks: Garmin sometimes rate-limits (429) or blocks datacenter IPs like GitHub's,
and refreshed tokens are not saved back to the secret, so it may stop working after a
while. If the run fails, use option B.

### Option B: run it from your Mac (more reliable)

```bash
./update_and_push.sh
```

To run it on a schedule, add a cron entry with `crontab -e`, for example every 6 hours:

```
0 */6 * * * /Users/cwt/Desktop/golf-tracker/update_and_push.sh >> /tmp/golf.log 2>&1
```

(Adjust the path. Your Mac must be awake, and cron may need Full Disk Access on macOS.)

## Files

- `fetch_golf.py` - incremental poller, writes `data/rounds.json`
- `index.html` - the whole site, no build step
- `.github/workflows/update.yml` - scheduled job
- `update_and_push.sh` - local pull and push
