#!/usr/bin/env python3
"""2026 Base P1 验收（管控对账 + 池视图 + 主表状态）。"""

from __future__ import annotations

import sys
from pathlib import Path

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_text

CTRL = "tblyvJJhyq5KoT4F"
SUM = "tblXonlkdLxrTLXE"


def main() -> int:
    cfg = load_2026_config()
    c = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    checks: list[tuple[str, bool, str]] = []

    ctrl_f = {f["field_name"] for f in c.list_fields(CTRL)}
    checks.append(("管控·合格合计字段", "合格合计" in ctrl_f, str(ctrl_f & {"合格合计", "对账差异", "是否超产", "生产区域"})))

    ctrl_rows = c.list_records(CTRL)
    with_q = sum(1 for r in ctrl_rows if r["fields"].get("合格合计") not in (None, "", 0))
    checks.append(("管控·合格合计有数", with_q > 0, f"{with_q}/{len(ctrl_rows)} 行"))

    main_rows = c.list_records(MAIN_TABLE)
    confirmed = sum(
        1 for r in main_rows if extract_text(r["fields"].get("工序下发状态")) in ("已确认", "已审核")
    )
    checks.append(("主表·可汇总行", confirmed >= 20, f"{confirmed}/{len(main_rows)}"))

    bt_ok = sum(1 for r in main_rows if extract_text(r["fields"].get("批号文本")))
    checks.append(("主表·批号文本", bt_ok == len(main_rows), f"{bt_ok}/{len(main_rows)}"))

    views = c.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/views", params={"page_size": 100})["data"]["items"]
    pools = [v for v in views if v["view_name"].startswith("P1·上道池")]
    checks.append(("P1·上道池视图", len(pools) >= 6, f"{len(pools)} 个"))

    sum_n = len(c.list_records(SUM))
    checks.append(("汇总表·有数据", sum_n >= 8, f"{sum_n} 行"))

    print("2026 P1 验收")
    print("-" * 50)
    ok_all = True
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name} — {detail}")
        ok_all = ok_all and ok
    print("-" * 50)
    if not ok_all:
        print("待完成：8 个报工 form 关联筛选（飞书界面 / AI Prompt）")
    return 0 if ok_all else 2


if __name__ == "__main__":
    sys.exit(main())
