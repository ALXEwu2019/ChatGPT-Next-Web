#!/usr/bin/env python3
"""Fix PTJ92 upstream link fields and view filters on production log main table."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from advance_v4_extensions import COMMON_KEEP, patch_view_columns
from advance_v4_greenfield import Client
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"

from process_registry import PROD, proc_id

PTJ92_VIEWS = {
    "vew2SeSRgG": {
        "name": "PTJ92·#1020报工",
        "keep": COMMON_KEEP | {"关联管控批_PTJ92#1020", "关联管控批", "工位代码"},
        # 首道：本视图只显示 PTJ92·#1020 报工行
        "filter": [
            ("fldSUoQi47", 18, PROD["PTJ92"]),
            ("fldMxRQhnU", 18, proc_id("PTJ92", "#1020")),
        ],
    },
    "vewDNLBqX5": {
        "name": "PTJ92·#3040报工",
        "keep": COMMON_KEEP | {"上道批号_PTJ92#3040", "上道批号"},
        # 本视图显示 #3040 报工行；上道池在字段「上道批号_PTJ92#3040」单独筛 #1020
        "filter": [
            ("fldSUoQi47", 18, PROD["PTJ92"]),
            ("fldMxRQhnU", 18, proc_id("PTJ92", "#3040")),
        ],
    },
    "vewhTfcmic": {
        "name": "PTJ92·#50报工",
        "keep": COMMON_KEEP | {"上道批号_PTJ92#50", "上道批号"},
        # 本视图显示 #50 报工行；上道池在字段「上道批号_PTJ92#50」单独筛 #3040
        "filter": [
            ("fldSUoQi47", 18, PROD["PTJ92"]),
            ("fldMxRQhnU", 18, proc_id("PTJ92", "#50")),
        ],
    },
}

UPSTREAM_FIELDS = (
    ("上道批号_PTJ92#3040", proc_id("PTJ92", "#1020")),
    ("上道批号_PTJ92#50", proc_id("PTJ92", "#3040")),
)

UPSTREAM_POOL_VIEWS = (
    (
        "PTJ92·上道池#1020",
        [
            ("fldSUoQi47", 18, PROD["PTJ92"]),
            ("fldMxRQhnU", 18, proc_id("PTJ92", "#1020")),
            ("fld1PUlkCs", 3, STATUS_CONFIRMED),
        ],
    ),
    (
        "PTJ92·上道池#3040",
        [
            ("fldSUoQi47", 18, PROD["PTJ92"]),
            ("fldMxRQhnU", 18, proc_id("PTJ92", "#3040")),
            ("fld1PUlkCs", 3, STATUS_CONFIRMED),
        ],
    ),
)


def recreate_upstream_field(client: Client, name: str, dry_run: bool) -> tuple[str, str | None]:
    """Delete + recreate link field to clear wrong 关联记录筛选 in UI."""
    fields = client.list_fields(MAIN)
    existing = next((f for f in fields if f["field_name"] == name), None)
    old_id = existing["field_id"] if existing else None

    if dry_run:
        return f"[dry-run] recreate link field {name}", old_id

    if existing:
        resp = client.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{old_id}")
        if resp.get("code") != 0:
            return f"FAIL delete {name}: {resp.get('msg', '')}", old_id
        time.sleep(0.5)

    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields",
        json={
            "field_name": name,
            "type": 18,
            "property": {"table_id": MAIN, "multiple": False},
        },
    )
    if resp.get("code") != 0:
        return f"FAIL create {name}: {resp.get('msg', '')}", old_id
    new_id = resp.get("data", {}).get("field", {}).get("field_id")
    return f"recreated: {name} ({old_id} -> {new_id})", new_id


def patch_view_filter(
    client: Client, view_id: str, view_name: str, conditions: list[tuple[str, int, str]], dry_run: bool
) -> str:
    payload = {
        "property": {
            "filter_info": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_id": field_id,
                        "field_type": field_type,
                        "operator": "is",
                        "value": json.dumps([value]),
                    }
                    for field_id, field_type, value in conditions
                ],
            }
        }
    }
    if dry_run:
        return f"[dry-run] patch view filter {view_name}: {len(conditions)} conditions"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{view_id}",
        json=payload,
    )
    ok = resp.get("code") == 0
    return f"{'view filter ok' if ok else 'FAIL view filter'}: {view_name} — {resp.get('msg', '')}"


def verify_view_filters(client: Client) -> list[str]:
    lines: list[str] = []
    proc_by_id = {proc_id("PTJ92", c): c for c in ("#1020", "#3040", "#50")}
    expected_proc = {
        "vew2SeSRgG": "#1020",
        "vewDNLBqX5": "#3040",
        "vewhTfcmic": "#50",
    }
    for view_id, exp in expected_proc.items():
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{view_id}")
        name = PTJ92_VIEWS[view_id]["name"]
        fi = data.get("data", {}).get("view", {}).get("property", {}).get("filter_info") or {}
        got = None
        for c in fi.get("conditions") or []:
            if c.get("field_id") == "fldMxRQhnU":
                val = json.loads(c.get("value") or "[]")
                got = proc_by_id.get(val[0], val[0]) if val else None
        lines.append(f"{'PASS' if got == exp else 'FAIL'} {name} 工序筛选={got} (期望 {exp})")
    return lines


def ensure_upstream_pool_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    views = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views", params={"page_size": 100})
    existing = {v["view_name"]: v["view_id"] for v in views.get("data", {}).get("items", [])}
    for name, conds in UPSTREAM_POOL_VIEWS:
        vid = existing.get(name)
        if not vid:
            if dry_run:
                lines.append(f"[dry-run] create pool view {name}")
                continue
            resp = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{MAIN}/views",
                json={"view_name": name, "view_type": "grid"},
            )
            vid = resp.get("data", {}).get("view", {}).get("view_id")
            lines.append(f"{'created' if resp.get('code')==0 else 'FAIL'} pool view {name}: {resp.get('msg','')}")
        else:
            lines.append(f"skip pool view: {name}")
        if vid:
            lines.append(patch_view_filter(client, vid, name, conds, dry_run))
    return lines


def run(dry_run: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    lines: list[str] = []

    print("fix_ptj92_upstream — 重建上道字段 + 修正视图筛选")
    print("-" * 60)

    for name, upstream in UPSTREAM_FIELDS:
        msg, _ = recreate_upstream_field(client, name, dry_run)
        up_code = "#1020" if upstream == proc_id("PTJ92", "#1020") else "#3040"
        lines.append(f"{msg} (上道工序应为 {up_code})")

    for view_id, spec in PTJ92_VIEWS.items():
        lines.append(patch_view_filter(client, view_id, spec["name"], spec["filter"], dry_run))
        lines.append(patch_view_columns(client, MAIN, view_id, spec["keep"], dry_run))

    lines.extend(ensure_upstream_pool_views(client, dry_run))

    for line in lines:
        print(line)

    if not dry_run:
        print("-" * 60)
        print("验收：")
        for line in verify_view_filters(client):
            print(line)
        print("-" * 60)
        print("请在飞书界面逐视图配置「上道批号_PTJ92#*」关联筛选（OpenAPI 无法写入）：")
        print("  PTJ92·#3040报工 → 上道批号_PTJ92#3040 (fld09hh79X)")
        print("    工序代码 = #1020 · 工序下发状态 = 已确认 · 产品 = PTJ92")
        print("  PTJ92·#50报工 → 上道批号_PTJ92#50 (fldaJjkrtj)")
        print("    工序代码 = #3040 · 工序下发状态 = 已确认 · 产品 = PTJ92")
        print("  可参考只读上道池视图：PTJ92·上道池#1020 / PTJ92·上道池#3040")

    print("-" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Fix PTJ92 upstream batch fields and view filters")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
