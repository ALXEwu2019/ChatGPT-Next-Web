#!/usr/bin/env python3
"""Sprint verification: route, linkage, defect tables."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

CONFIG = Path(__file__).with_name("config.json")
BASE = "https://open.feishu.cn/open-apis"

TABLES = {
    "route": "tblwr4ItIzWPW6bb",
    "linkage": "tblUyVVrhKQOu1pO",
    "defect_detail": "tblMtQ4aEwlzuhWs",
    "defect_reason": "tblvX8KSv73TluVk",
}


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def count_records(app: str, table_id: str, headers: dict) -> int:
    total = 0
    page_token = None
    while True:
        params: dict = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table_id}/records",
            headers=headers,
            params=params,
            timeout=60,
        )
        data = r.json()["data"]
        total += len(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return total


def field_names(app: str, table_id: str, headers: dict) -> set[str]:
    r = requests.get(
        f"{BASE}/bitable/v1/apps/{app}/tables/{table_id}/fields",
        headers=headers,
        timeout=30,
    )
    return {f["field_name"] for f in r.json()["data"]["items"]}


def linkage_stats(app: str, headers: dict) -> dict:
    items = []
    page_token = None
    while True:
        params: dict = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        r = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{TABLES['linkage']}/records",
            headers=headers,
            params=params,
            timeout=60,
        )
        data = r.json()["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")

    enabled = rework = scrap = 0
    for it in items:
        f = it.get("fields", {})
        st = f.get("启用状态")
        disp = f.get("不良类型")
        if st == "启用":
            enabled += 1
            if disp == "返工":
                rework += 1
            elif disp == "报废":
                scrap += 1
    return {"total": len(items), "enabled": enabled, "rework": rework, "scrap": scrap}


def check(name: str, ok: bool, detail: str) -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} — {detail}")
    return ok


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    app = cfg["feishu"]["base_app_token"]
    headers = {"Authorization": f"Bearer {token(cfg)}"}

    print("Sprint 验收检查")
    print("-" * 50)
    ok = True

    route_n = count_records(app, TABLES["route"], headers)
    ok &= check("产品工序路线表", route_n == 11, f"{route_n} 行（目标 11）")

    reason_n = count_records(app, TABLES["defect_reason"], headers)
    ok &= check("不良原因库", reason_n >= 46, f"{reason_n} 行（目标 ≥46）")

    link = linkage_stats(app, headers)
    ok &= check(
        "联动规则总数",
        link["total"] == 137,
        f"{link['total']} 行（目标 137）",
    )
    ok &= check("联动启用", link["enabled"] == 110, f"{link['enabled']}（目标 110）")
    ok &= check("联动返工", link["rework"] == 23, f"{link['rework']}（目标 23）")
    ok &= check("联动报废", link["scrap"] == 87, f"{link['scrap']}（目标 87）")

    detail_fields = field_names(app, TABLES["defect_detail"], headers)
    ok &= check(
        "不良明细·处置类型字段",
        "处置类型" in detail_fields,
        "已存在" if "处置类型" in detail_fields else "缺失",
    )

    print("-" * 50)
    print("P1 界面：✅ 已验收（2026-06-23）")
    print("联动四视图：✅ 已验收（返工23/报废87/历史27；启用视图分组展示119行）")
    print("待完成：cron、P2 状态机")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
