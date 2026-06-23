#!/usr/bin/env python3
"""P1 acceptance checks against live Feishu base (read-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from sync_batch_summary import extract_text, load_config

BASE = "https://open.feishu.cn/open-apis"


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def list_records(cfg: dict, table_id: str) -> list[dict]:
    app = cfg["feishu"]["base_app_token"]
    h = {"Authorization": f"Bearer {token(cfg)}"}
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 500}
        if page:
            params["page_token"] = page
        r = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table_id}/records",
            headers=h,
            params=params,
            timeout=60,
        )
        data = r.json()["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def main() -> int:
    cfg_path = Path(__file__).with_name("config.json")
    if not cfg_path.exists():
        print("FAIL: config.json missing")
        return 1
    cfg = load_config(cfg_path)
    tables = cfg["tables"]
    link = cfg.get("link_tables", {})

    control_id = link.get("control", {}).get("table_id", "tbl6bCLJThyUaD8U")
    checks: list[tuple[str, bool, str]] = []

    control = list_records(cfg, control_id)
    checks.append(("管控表≥4行", len(control) >= 4, f"实际{len(control)}行"))

    zhidong_ok = any(
        "recvnmMdIn6lCo" in str(r.get("fields", {}).get("产品"))
        for r in control
    )
    checks.append(("止动块管控行产品关联", zhidong_ok, "样例3/4行应关联ZHIDONG"))

    summary = list_records(cfg, tables["batch_summary"])
    sum_rows = len(summary)
    checks.append(("汇总表有数据", sum_rows > 0, f"{sum_rows}行"))

    has_test = any(
        extract_text(r.get("fields", {}).get("批号文本")) == "S-TEST-A" for r in summary
    )
    checks.append(("汇总含S-TEST-A", has_test, "需已确认报工+跑脚本"))

    main_rows = list_records(cfg, tables["production_log"])
    confirmed = [
        r
        for r in main_rows
        if extract_text(r.get("fields", {}).get("工序下发状态")) == "已确认"
    ]
    checks.append(("主表有已确认记录", len(confirmed) > 0, f"{len(confirmed)}条"))

    ctrl_test = any(
        extract_text(r.get("fields", {}).get("批号文本")) == "S-TEST-A" for r in control
    )
    checks.append(("管控有S-TEST-A", ctrl_test, "首道选批测试用"))

    print("P1 验收检查")
    print("-" * 50)
    all_ok = True
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name} — {detail}")
        all_ok = all_ok and ok

    print("-" * 50)
    manual = [
        "上道批号6视图筛选（界面手工，勿用有效合格>0若保存失败）",
        "首道关联管控批筛选2视图",
        "合格合计查找4条件含生产区域",
        "cron 8/12/20 点",
    ]
    print("仍需人工确认：")
    for m in manual:
        print(f"  - {m}")

    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
