#!/usr/bin/env python3
"""Verify V4 optional extensions: end process, reconciliation, PTJ92."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from sync_batch_summary import extract_text, load_config

BASE = "https://open.feishu.cn/open-apis"

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"
TRACE = "tblWv5lus3TI8zM3"
SUMMARY = "tblu1h0huPW1Mixd"

PROC_70 = "recIZhFG8RKKMI"
PROC_1020 = "recy0wR8UdunUU"
PROD_STOPPER = "rechKic8YG1cTc"
PROD_PTJ92 = "recvnngInM41nM"

RECON_VIEW = "vewEEYWvZN"
PTJ92_VIEWS = ("PTJ92·#1020报工", "PTJ92·#3040报工", "PTJ92·#50报工")
PTJ92_FIELDS = ("关联管控批_PTJ92#1020", "上道批号_PTJ92#3040", "上道批号_PTJ92#50")


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def list_records(app: str, table: str, headers: dict) -> list[dict]:
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 500}
        if page:
            params["page_token"] = page
        data = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/records",
            headers=headers,
            params=params,
            timeout=60,
        ).json()["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def field_names(app: str, table: str, headers: dict) -> set[str]:
    r = requests.get(
        f"{BASE}/bitable/v1/apps/{app}/tables/{table}/fields",
        headers=headers,
        timeout=30,
    )
    return {f["field_name"] for f in r.json()["data"]["items"]}


def view_names(app: str, table: str, headers: dict) -> set[str]:
    r = requests.get(
        f"{BASE}/bitable/v1/apps/{app}/tables/{table}/views",
        headers=headers,
        params={"page_size": 100},
        timeout=30,
    )
    return {v["view_name"] for v in r.json()["data"]["items"]}


def proc_id(fields: dict, key: str) -> str | None:
    v = fields.get(key)
    if isinstance(v, list) and v:
        return v[0].get("record_ids", [None])[0]
    return None


def check(name: str, ok: bool, detail: str) -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} — {detail}")
    return ok


def main() -> int:
    cfg_path = Path(__file__).with_name("config.json")
    if not cfg_path.exists():
        print("FAIL: config.json missing")
        return 1
    cfg = load_config(cfg_path)
    app = cfg["feishu"]["base_app_token"]
    headers = {"Authorization": f"Bearer {token(cfg)}"}

    print("Extensions 验收检查")
    print("-" * 50)
    ok = True

    main_rows = list_records(app, MAIN, headers)
    stopper_70 = sum(
        1
        for r in main_rows
        if proc_id(r.get("fields", {}), "工序代码") == PROC_70
        and proc_id(r.get("fields", {}), "产品") == PROD_STOPPER
        and extract_text(r.get("fields", {}).get("工序下发状态")) == "已确认"
    )
    ok &= check("STOPPER #70 已确认报工", stopper_70 > 0, f"{stopper_70} 条")

    summary = list_records(app, SUMMARY, headers)
    sum_70 = any(
        extract_text(r.get("fields", {}).get("工序代码")) == "#70"
        and float(r.get("fields", {}).get("合格合计") or 0) >= 55
        for r in summary
    )
    ok &= check("汇总含 #70 行", sum_70, "跑 sync 后应有 S-TEST-A-#70 合格55")

    ctrl_fields = field_names(app, CTRL, headers)
    ok &= check("管控对账字段", {"对账差异", "是否超产", "合格合计"}.issubset(ctrl_fields), "齐全")
    ctrl_views = view_names(app, CTRL, headers)
    ok &= check("管理·批工序对账视图", "管理·批工序对账" in ctrl_views, f"view {RECON_VIEW}")

    main_fields = field_names(app, MAIN, headers)
    ok &= check("PTJ92 per-view 字段", set(PTJ92_FIELDS).issubset(main_fields), str(PTJ92_FIELDS))
    main_views = view_names(app, MAIN, headers)
    ok &= check("PTJ92 报工视图", all(v in main_views for v in PTJ92_VIEWS), "3 视图")

    ctrl = list_records(app, CTRL, headers)
    ptj_ctrl = any(
        extract_text(r.get("fields", {}).get("批号文本")) == "P-TEST-A"
        and proc_id(r.get("fields", {}), "产品") == PROD_PTJ92
        for r in ctrl
    )
    ok &= check("PTJ92 管控批 P-TEST-A", ptj_ctrl, "首道 #1020 测试")

    trace_n = requests.get(
        f"{BASE}/bitable/v1/apps/{app}/tables/{TRACE}/records",
        headers=headers,
        params={"page_size": 1},
        timeout=30,
    ).json()["data"].get("total", 0)
    ok &= check("追溯规则≥11行", trace_n >= 11, f"{trace_n} 行（含 PTJ92 3 行）")

    print("-" * 50)
    print("手工：PTJ92 三视图关联筛选（openclaw-p3-ptj92-prompt-cn.md）")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
