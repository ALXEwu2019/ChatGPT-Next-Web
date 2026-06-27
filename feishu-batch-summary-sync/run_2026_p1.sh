#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export FEISHU_BASE_APP_TOKEN="${FEISHU_BASE_APP_TOKEN:-NiyZbKpKfae9x3sUP64cl9SFnRb}"

echo "== P1 API 自动化 =="
python3 remediate_2026_p1.py --fix-all

echo ""
echo "== Cron 安装 =="
chmod +x install_cron_2026.sh run_sync_2026.sh
./install_cron_2026.sh

echo ""
echo "== 试跑 sync =="
./run_sync_2026.sh
tail -8 logs/sync_2026.log

echo ""
echo "== 飞书 AI：请打开并粘贴 =="
echo "  docs/openclaw-2026-p1-feishu-ai-execute-cn.md"
