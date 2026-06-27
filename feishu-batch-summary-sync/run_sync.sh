#!/usr/bin/env bash
# Wrapper for cron / manual runs. Adjust SCRIPT_DIR if deployed elsewhere.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sync_batch_summary.log"

PYTHON="${PYTHON:-python3}"

if [[ ! -f "$SCRIPT_DIR/config.json" ]]; then
  echo "$(date -Iseconds) ERROR config.json not found in $SCRIPT_DIR" >>"$LOG_FILE"
  exit 1
fi

{
  echo "===== $(date -Iseconds) sync start ====="
  "$PYTHON" "$SCRIPT_DIR/sync_batch_summary.py" -v
  echo "===== $(date -Iseconds) sync done ====="
} >>"$LOG_FILE" 2>&1
