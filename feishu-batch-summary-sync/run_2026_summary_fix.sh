#!/usr/bin/env bash
# 2026 批工序产量汇总表 — 审计 → 修复 → 同步
set -euo pipefail
cd "$(dirname "$0")"
export FEISHU_BASE_APP_TOKEN="${FEISHU_BASE_APP_TOKEN:-NiyZbKpKfae9x3sUP64cl9SFnRb}"

echo "== 1/3 审计 =="
python3 remediate_2026_summary.py --audit

echo ""
echo "== 2/3 修复结构 + 去重 =="
python3 remediate_2026_summary.py --fix-all

echo ""
echo "== 3/3 同步（需主表有已确认记录才有新数据）=="
python3 sync_batch_summary.py --config config.2026.json -v

echo ""
echo "== 验收 =="
python3 remediate_2026_summary.py --audit
