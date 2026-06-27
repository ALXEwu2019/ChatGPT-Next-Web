#!/usr/bin/env bash
# 按 2026 不良明细 + 返工完成清单 修复创建 V4（需 config.json 或环境变量凭证）
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f config.json ]]; then
  cp config.v4.wiki.example.json config.json
  echo "已生成 config.json，请填入 app_id / app_secret，或设置环境变量："
  echo "  export FEISHU_APP_ID=cli_xxx"
  echo "  export FEISHU_APP_SECRET=xxx"
  exit 1
fi

echo "== 1/3 sync_defect_rework_from_2026 =="
python3 sync_defect_rework_from_2026.py "$@"

echo ""
echo "== 2/3 remediate_defect_leader_view =="
python3 remediate_defect_leader_view.py

echo ""
echo "== 3/3 verify_p2 =="
python3 verify_p2.py

echo ""
echo "完成。表单字段顺序与四条自动化须在飞书界面确认。"
