#!/usr/bin/env bash
# 2026 生产 Base 汇总同步（cron / 手动）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sync_2026.log"

PYTHON="${PYTHON:-python3}"
CONFIG="${CONFIG:-config.2026.json}"

if [[ ! -f "$SCRIPT_DIR/$CONFIG" ]]; then
  echo "$(date -Iseconds) ERROR $CONFIG not found in $SCRIPT_DIR" >>"$LOG_FILE"
  exit 1
fi

{
  echo "===== $(date -Iseconds) sync_2026 start ====="
  "$PYTHON" "$SCRIPT_DIR/sync_batch_summary.py" --config "$CONFIG" -v
  echo "===== $(date -Iseconds) sync_2026 done ====="
} >>"$LOG_FILE" 2>&1
