#!/usr/bin/env python3
"""
Sync the IcyBox database: ingest new events and scrape latest odds/grails.

Runs build_db.py then scrape_boxes.py in sequence.
Set up as a cron job to run every 12 hours:

  crontab -e
  0 */12 * * * cd /path/to/icybox_stream && .venv/bin/python tools/sync_db.py --input ./icybox-data.jsonl --output /path/to/output >> sync.log 2>&1

Usage:
  python tools/sync_db.py
  python tools/sync_db.py --input ./icybox-data.jsonl --output '/Volumes/Crucial X9/projects/icybox_stream'
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime, timezone


def run_tool(script: str, args: list):
    """Run a Python script and stream its output."""
    cmd = [sys.executable, script] + args
    result = subprocess.run(cmd, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description='Sync IcyBox database')
    parser.add_argument('--input', default='./icybox-data.jsonl',
                        help='Path to JSONL data file (default: ./icybox-data.jsonl)')
    parser.add_argument('--output', default='./watch-catalog',
                        help='Output directory (default: ./watch-catalog)')
    args = parser.parse_args()

    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'=== IcyBox DB Sync: {now} ===\n')

    # Step 1: Ingest new events
    print('--- Ingesting events ---')
    rc = run_tool('tools/build_db.py', ['--input', args.input, '--output', args.output])
    if rc != 0:
        print(f'[error] build_db.py failed with exit code {rc}')
        sys.exit(1)

    # Step 2: Scrape latest odds and grails
    print('\n--- Scraping box pages ---')
    rc = run_tool('tools/scrape_boxes.py', ['--output', args.output])
    if rc != 0:
        print(f'[error] scrape_boxes.py failed with exit code {rc}')
        sys.exit(1)

    print(f'\n=== Sync complete: {now} ===')


if __name__ == '__main__':
    main()
