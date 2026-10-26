# Safe Superintelligence (SSI) Updates RSS Feed

An automated RSS feed generator for the [SSI updates page](https://ssi.inc/updates).

## RSS Feed

**Feed URL:** `https://raw.githubusercontent.com/<your-user>/<your-repo>/refs/heads/main/updates.rss`

## About

This project automatically scrapes the ssi.inc/updates page and generates an RSS feed of all posted updates, making it easy to stay notified when Safe Superintelligence posts a new announcement.

## Updates

The RSS feed is automatically updated daily to ensure you never miss new updates.

## Technical Details

- **Source:** [ssi.inc/updates](https://ssi.inc/updates)
- **Update Frequency:** Daily (GitHub Actions cron at 12:00 UTC)
- **Format:** RSS 2.0
- **Language:** English

### How it works

- `run.sh` downloads the updates page with curl
- `fin.py` parses the dated entries, diffs them against `updates_entries.json` (tracking when each entry was first seen, used as the item's `pubDate`), and writes `updates.rss`
- `.github/workflows/daily-update.yml` runs the above daily and commits any feed changes back to `main`