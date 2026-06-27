#!/usr/bin/env bash
# V4 全面审计 + 修复（日志编号保持自动编号）
set -euo pipefail
cd "$(dirname "$0")"

CONFIG="${1:-config.json}"

echo "========== 修复前审计 =========="
python3 audit_v4_comprehensive.py --config "$CONFIG" || true

echo ""
echo "========== 全面修复 =========="
python3 remediate_v4_comprehensive.py --config "$CONFIG" --skip-audit
