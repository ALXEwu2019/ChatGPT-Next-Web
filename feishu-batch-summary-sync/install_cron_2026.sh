#!/usr/bin/env bash
# 安装 2026 汇总 cron（每天 8:00 / 12:00 / 20:00，服务器本地时区）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER="# feishu-sync-2026"
CRON_FILE=$(mktemp)

chmod +x "$SCRIPT_DIR/run_sync_2026.sh"

# 保留已有 crontab，去掉旧 marker 行
(crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "run_sync_2026.sh" || true) >"$CRON_FILE"

cat >>"$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
$MARKER
0 8 * * * cd $SCRIPT_DIR && ./run_sync_2026.sh
0 12 * * * cd $SCRIPT_DIR && ./run_sync_2026.sh
0 20 * * * cd $SCRIPT_DIR && ./run_sync_2026.sh
EOF

crontab "$CRON_FILE"
rm -f "$CRON_FILE"

echo "已安装 cron（8/12/20 点）:"
crontab -l | grep -A3 "$MARKER"
echo ""
echo "试跑: cd $SCRIPT_DIR && ./run_sync_2026.sh && tail -5 logs/sync_2026.log"
