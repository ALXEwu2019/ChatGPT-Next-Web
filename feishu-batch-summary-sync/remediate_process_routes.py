#!/usr/bin/env python3
"""Rebuild routes/trace rules and fix view filters after 工序表 12-row restructure."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from advance_v4_extensions import patch_view_columns
from advance_v4_greenfield import COMMON_KEEP, VIEW_KEEP, Client
from fix_ptj92_upstream import PTJ92_VIEWS
from process_registry import (
    CHAINS,
    FIRST_CTRL_FIELD,
    OPERATOR_VIEWS,
    PROD,
    ROUTE_LABEL,
    ROUTE_META,
    TRACE_RULES,
    UPSTREAM_FIELD,
    proc_id,
    upstream_code,
)
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"
ROUTE = "tblwr4ItIzWPW6bb"
TRACE = "tblWv5lus3TI8zM3"

# 主表字段（固定 field_id）
FLD_PRODUCT = "fldSUoQi47"
FLD_PROCESS = "fldMxRQhnU"
FLD_STATUS = "fld1PUlkCs"

ZHIDONG_2030_VIEW = "止动块·#2030报工"


def ensure_field(client: Client, table: str, name: str, link_table: str, dry_run: bool) -> str:
    if any(f["field_name"] == name for f in client.list_fields(table)):
        return f"skip field: {name}"
    if dry_run:
        return f"[dry-run] create field {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields",
        json={"field_name": name, "type": 18, "property": {"table_id": link_table, "multiple": False}},
    )
    ok = resp.get("code") == 0
    fid = resp.get("data", {}).get("field", {}).get("field_id", "")
    return f"{'created' if ok else 'FAIL'} field {name} ({fid}): {resp.get('msg', '')}"


def ensure_view(client: Client, name: str, dry_run: bool) -> str | None:
    for v in _list_views(client, MAIN):
        if v.get("view_name") == name:
            return v.get("view_id")
    if dry_run:
        return None
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/views",
        json={"view_name": name, "view_type": "grid"},
    )
    if resp.get("code") != 0:
        return None
    return resp.get("data", {}).get("view", {}).get("view_id")


def _list_views(client: Client, table: str) -> list[dict]:
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/views", params=params)["data"]
        items.extend(data["items"])
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def operator_keep(view_id: str, product: str, code: str) -> set[str]:
    """与 advance_v4_greenfield.VIEW_KEEP / PTJ92 视图列一致，避免覆盖后隐藏批号/有效数列。"""
    if view_id in VIEW_KEEP:
        return set(VIEW_KEEP[view_id])
    if view_id in PTJ92_VIEWS:
        return set(PTJ92_VIEWS[view_id]["keep"])
    base = set(COMMON_KEEP)
    up = upstream_code(product, code)
    if up is None:
        fname = FIRST_CTRL_FIELD.get((product, code), "关联管控批")
        base.add(fname)
        if fname != "关联管控批":
            base.add("关联管控批")
    else:
        base.add(UPSTREAM_FIELD[(product, code)])
        base.add("上道批号")
    if code in ("#2030", "#4050") or (product == "ZHIDONG" and code == "#2030"):
        base.add("生产区域")
    if code == "#60" or (product == "PTJ92" and code == "#1020"):
        base.add("工位代码")
    return base


def patch_view_filter(
    client: Client, view_id: str, product: str, process_code: str, dry_run: bool
) -> str:
    conditions = [
        {"field_id": FLD_PRODUCT, "operator": "is", "value": json.dumps([PROD[product]])},
        {"field_id": FLD_PROCESS, "operator": "is", "value": json.dumps([proc_id(product, process_code)])},
    ]
    body = {"property": {"filter_info": {"conjunction": "and", "conditions": conditions}}}
    if dry_run:
        return f"[dry-run] filter {view_id} {product}{process_code}"
    resp = client.call("PATCH", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{view_id}", json=body)
    ok = resp.get("code") == 0
    return f"{'filter ok' if ok else 'FAIL filter'} {view_id} {product}{process_code}: {resp.get('msg', '')}"


def delete_all_records(client: Client, table: str, dry_run: bool) -> list[str]:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/records", params={"page_size": 500})
    ids = [it["record_id"] for it in data.get("data", {}).get("items", [])]
    if not ids:
        return [f"skip delete {table}: empty"]
    if dry_run:
        return [f"[dry-run] delete {len(ids)} from {table}"]
    lines: list[str] = []
    for i in range(0, len(ids), 500):
        chunk = ids[i : i + 500]
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{table}/records/batch_delete",
            json={"records": chunk},
        )
        lines.append(f"deleted {len(chunk)} from {table}: {resp.get('msg', '')}")
    return lines


def rebuild_routes(client: Client, dry_run: bool) -> list[str]:
    lines = delete_all_records(client, ROUTE, dry_run)
    route_ids: dict[str, str] = {}
    rows: list[dict] = []

    for product, chain in CHAINS.items():
        for order, code in enumerate(chain, start=1):
            label = ROUTE_LABEL[(product, code)]
            dim, source = ROUTE_META[(product, code)]
            fields: dict = {
                "路线名称": label,
                "顺序": order,
                "是否首道": order == 1,
                "汇总维度": dim,
                "批号来源": source,
                "产品": [PROD[product]],
                "工序代码": [proc_id(product, code)],
            }
            rows.append({"fields": fields, "_label": label})

    if dry_run:
        lines.append(f"[dry-run] create {len(rows)} route rows")
        return lines

    # 首道先建
    for row in rows:
        if row["fields"]["是否首道"]:
            label = row.pop("_label")
            resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{ROUTE}/records", json={"fields": row["fields"]})
            if resp.get("code") == 0:
                route_ids[label] = resp["data"]["record"]["record_id"]
            lines.append(f"route {label}: {resp.get('msg', '')}")

    # 下道带上道工序（关联路线表上一行）
    for row in rows:
        if row["fields"]["是否首道"]:
            continue
        label = row.pop("_label")
        product = None
        code = None
        for p, chain in CHAINS.items():
            for c in chain:
                if ROUTE_LABEL.get((p, c)) == label:
                    product, code = p, c
        assert product and code
        up_label = ROUTE_LABEL[(product, upstream_code(product, code) or "")]
        if up_label in route_ids:
            row["fields"]["上道工序"] = [route_ids[up_label]]
        resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{ROUTE}/records", json={"fields": row["fields"]})
        if resp.get("code") == 0:
            route_ids[label] = resp["data"]["record"]["record_id"]
        lines.append(f"route {label}: {resp.get('msg', '')}")
    return lines


def rebuild_trace(client: Client, dry_run: bool) -> list[str]:
    lines = delete_all_records(client, TRACE, dry_run)
    rows = []
    for name, product, code, need, seg3, note in TRACE_RULES:
        rows.append(
            {
                "fields": {
                    "规则名称": name,
                    "产品": [PROD[product]],
                    "工序代码": [proc_id(product, code)],
                    "需要追溯号": need,
                    "段3来源字段": seg3,
                    "段3说明": note,
                }
            }
        )
    if dry_run:
        lines.append(f"[dry-run] create {len(rows)} trace rules")
        return lines
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{TRACE}/records/batch_create",
        json={"records": rows},
    )
    n = len(resp.get("data", {}).get("records", []))
    lines.append(f"trace rules: {resp.get('msg', '')} ({n} rows)")
    return lines


def setup_zhidong_2030(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.append(ensure_field(client, MAIN, "关联管控批_止动块#2030", CTRL, dry_run))
    lines.append(ensure_field(client, MAIN, "上道批号_止动块#4050", MAIN, dry_run))
    vid = ensure_view(client, ZHIDONG_2030_VIEW, dry_run)
    if vid:
        OPERATOR_VIEWS[vid] = ("ZHIDONG", "#2030")
        lines.append(patch_view_columns(client, MAIN, vid, operator_keep(vid, "ZHIDONG", "#2030"), dry_run))
        lines.append(patch_view_filter(client, vid, "ZHIDONG", "#2030", dry_run))
    elif dry_run:
        lines.append(f"[dry-run] create view {ZHIDONG_2030_VIEW}")
    return lines


def patch_operator_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for vid, (product, code) in OPERATOR_VIEWS.items():
        lines.append(patch_view_columns(client, MAIN, vid, operator_keep(vid, product, code), dry_run))
        lines.append(patch_view_filter(client, vid, product, code, dry_run))
    return lines


def print_proc_map() -> None:
    print("\n工序引用表（产品 × 工序代码 → record_id）")
    print("-" * 60)
    for product, chain in CHAINS.items():
        for code in chain:
            print(f"  {product:8} {code:6} → {proc_id(product, code)}  ({ROUTE_LABEL[(product, code)]})")
    print("-" * 60)
    print("下道选批：上道批号_* 关联筛选 → 上道工序 record_id + 已确认")
    for (product, code), fname in sorted(UPSTREAM_FIELD.items()):
        up = upstream_code(product, code)
        if up:
            print(f"  {fname:28} 上道={up}  id={proc_id(product, up)}")


def run(dry_run: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_process_routes — 工序表 12 行对齐")
    print("-" * 60)
    lines: list[str] = []
    lines.extend(setup_zhidong_2030(client, dry_run))
    lines.extend(rebuild_routes(client, dry_run))
    lines.extend(rebuild_trace(client, dry_run))
    lines.extend(patch_operator_views(client, dry_run))
    for line in lines:
        print(line)
    print_proc_map()
    print("-" * 60)
    print("下一步：python3 remediate_v4_formulas.py && python3 seed_workflow_e2e.py --full-chain")
    print("手工：各「上道批号_*」字段在飞书界面配置关联筛选（上道工序+已确认）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
