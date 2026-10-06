#!/bin/sh
# Local alternative to the GitHub Actions job: pull from Garmin on this Mac, then push.
# Usage: ./update_and_push.sh   (run from anywhere; it cds into its own folder)
set -e
cd "$(dirname "$0")"
. ./garmin-env/bin/activate 2>/dev/null || . ../garmin-env/bin/activate
python fetch_golf.py
git add data
if git diff --cached --quiet; then
  echo "Nothing to commit."
else
  git commit -m "Update golf data"
  git push
fi
