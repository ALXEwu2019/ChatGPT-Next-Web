#!/usr/bin/env python3
"""验收 8 个报工 form 关联字段是否已配置（首道 2 + 上道 6）。"""

from __future__ import annotations

import sys

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config

FIRST_DONE = ("关联管控批_STOPPER#2030", "关联管控批_止动块#4050")
UPSTREAM = (
    "上道批号_STOPPER#4050",
    "上道批号_STOPPER#60",
    "上道批号_STOPPER#70",
    "上道批号_止动块#60",
    "上道批号_止动块#70",
    "上道批号_止动块#80",
)


def main() -> int:
    cfg = load_2026_config()
    c = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    fields = {f["field_name"]: f for f in c.list_fields(MAIN_TABLE)}

    print("2026 报工 form 关联字段验收")
    print("-" * 50)
    print("说明：API 读不到「指定记录」筛选，仅检查字段存在与关联表。")
    print()

    ok = True
    for name in FIRST_DONE:
        f = fields.get(name)
        tgt = (f.get("property") or {}).get("table_id") if f else None
        good = f and tgt == "tblyvJJhyq5KoT4F"
        print(f"[{'PASS' if good else 'FAIL'}] {name} → 管控表")
        ok = ok and good

    for name in UPSTREAM:
        f = fields.get(name)
        tgt = (f.get("property") or {}).get("table_id") if f else None
        good = f and tgt == MAIN_TABLE
        mark = "PASS" if good else "FAIL"
        note = "（筛选须在列头创建时配置，请对照 P1·上道池 视图手工点选验证）"
        print(f"[{mark}] {name} → 主表 {note}")
        ok = ok and good

    print("-" * 50)
    print("首道 2 项应由飞书 AI 已完成；上道 6 项请按 fix_2026_upstream_link_filters.py --print-manual 重建列并配筛选。")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
