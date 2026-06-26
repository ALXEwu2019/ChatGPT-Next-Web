#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export FEISHU_BASE_APP_TOKEN="${FEISHU_BASE_APP_TOKEN:-NiyZbKpKfae9x3sUP64cl9SFnRb}"
python3 audit_2026_comprehensive.py --out ../docs/audit-2026-comprehensive-cn.md
