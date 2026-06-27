#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export FEISHU_BASE_APP_TOKEN="${FEISHU_BASE_APP_TOKEN:-NiyZbKpKfae9x3sUP64cl9SFnRb}"
python3 remediate_2026_p0.py --fix-all "$@"
