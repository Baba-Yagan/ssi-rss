#!/bin/bash

# Capture both time and curl output, with error redirection
{ time curl -s https://ssi.inc/updates -o updates.html > >(tee output.log) 2> >(tee error.log >&2); } 2>&1

# Check exit status
if [ $? -ne 0 ]; then
    echo "Getting page for updates failed - curl error occurred"
    exit 1
fi

# Generate RSS feed
python3 fin.py

echo "RSS generation completed"

# Remove the sleep when running in GitHub Actions (cron handles scheduling)
if [ -z "$GITHUB_ACTIONS" ]; then
    sleep 24h
fi