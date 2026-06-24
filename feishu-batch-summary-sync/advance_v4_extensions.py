#!/usr/bin/env python3
"""Advance V4 optional extensions: #70/#80 test chain, reconciliation, PTJ92."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

from advance_v4_greenfield import COMMON_KEEP, Client
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"
TRACE = "tblWv5lus3TI8zM3"

PROD_STOPPER = "rechKic8YG1cTc"
PROD_ZHIDONG = "recvnmMdIn6lCo"
PROD_PTJ92 = "recvnngInM41nM"

PROC = {
    "#2030": "recC9QvIgUH8oK",
    "#4050": "recs76rS587WRW",
    "#60": "recfoJ5q7gJVtK",
    "#70": "recIZhFG8RKKMI",
    "#80": "recvnmMevC5Dbr",
    "#1020": "recy0wR8UdunUU",
    "#3040": "recST53o7KuXQy",
    "#50": "recRxX5JjvzuEm",
}

# 末道视图（P1 已建，本脚本补测试数据 + 列收敛复核）
END_VIEW_IDS = ("vewqlHptpP", "vewUWGnXfU", "vewEJZrQu5")

RECON_VIEW_ID = "vewEEYWvZN"
RECON_KEEP = {
    "批号文本", "产品", "工序代码", "生产区域", "状态",
    "本工序下发数量", "合格合计", "合格合计_#4050", "对账差异", "是否超产",
}

PTJ92_FIELDS = [
    ("关联管控批_PTJ92#1020", CTRL),
    ("上道批号_PTJ92#3040", MAIN),
    ("上道批号_PTJ92#50", MAIN),
]

PTJ92_VIEWS = [
    ("PTJ92·#1020报工", "grid"),
    ("PTJ92·#3040报工", "grid"),
    ("PTJ92·#50报工", "grid"),
]

PTJ92_TRACE = [
    ("PTJ92-#1020", PROD_PTJ92, "#1020", True, "工位代码", "#1020 首道"),
    ("PTJ92-#3040", PROD_PTJ92, "#3040", False, "无", "不需要追溯号"),
    ("PTJ92-#50", PROD_PTJ92, "#50", False, "无", "检测出库合一"),
]

# S-TEST-A 链路（API 实测）
UPSTREAM_STOPPER_60 = "recvnmEzmWn7PY"
UPSTREAM_STOPPER_4050 = "recvnmEp5WLit7"


def patch_record_links(client: Client, record_id: str, fields: dict, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] patch {record_id}: {list(fields.keys())}"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/records/{record_id}",
        json={"fields": fields},
    )
    ok = resp.get("code") == 0
    return f"{'patched' if ok else 'FAIL'} {record_id}: {resp.get('msg', '')}"


def ensure_upstream_chain(client: Client, dry_run: bool) -> list[str]:
    """补 #60 上道链接，使批号沿 S-TEST-A 链传到 #70。"""
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 500})
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        proc = f.get("工序代码")
        proc_ids = proc[0].get("record_ids", []) if isinstance(proc, list) and proc else []
        if PROC["#60"] not in proc_ids:
            continue
        up = f.get("上道批号_STOPPER#60") or f.get("上道批号")
        has_up = isinstance(up, list) and up and up[0].get("record_ids")
        if not has_up:
            return [
                patch_record_links(
                    client,
                    it["record_id"],
                    {
                        "上道批号": [UPSTREAM_STOPPER_4050],
                        "上道批号_STOPPER#60": [UPSTREAM_STOPPER_4050],
                    },
                    dry_run,
                )
            ]
    return ["skip: #60 upstream already set"]


def list_views(client: Client, table: str) -> list[dict]:
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


def ensure_field(client: Client, table: str, name: str, link_table: str, dry_run: bool) -> str:
    fields = client.list_fields(table)
    if any(f["field_name"] == name for f in fields):
        return f"skip field: {name}"
    if dry_run:
        return f"[dry-run] create field {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields",
        json={
            "field_name": name,
            "type": 18,
            "property": {"table_id": link_table, "multiple": False},
        },
    )
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} field {name}: {resp.get('msg', '')}"


def ensure_view(client: Client, table: str, name: str, view_type: str, dry_run: bool) -> tuple[str, str | None]:
    for v in list_views(client, table):
        if v.get("view_name") == name:
            return f"skip view: {name}", v.get("view_id")
    if dry_run:
        return f"[dry-run] create view {name}", None
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/views",
        json={"view_name": name, "view_type": view_type},
    )
    vid = resp.get("data", {}).get("view", {}).get("view_id")
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} view {name}: {resp.get('msg', '')}", vid


def patch_view_columns(
    client: Client, table: str, view_id: str, keep_names: set[str], dry_run: bool
) -> str:
    fields = client.list_fields(table)
    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary = next(f["field_id"] for f in fields if f.get("is_primary"))
    keep_ids = {primary}
    for n in keep_names:
        if n in name_to_id:
            keep_ids.add(name_to_id[n])
    hidden = [f["field_id"] for f in fields if f["field_id"] not in keep_ids]
    if dry_run:
        return f"[dry-run] view {view_id}: show {len(keep_ids)} hide {len(hidden)}"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{table}/views/{view_id}",
        json={"property": {"hidden_fields": hidden}},
    )
    ok = resp.get("code") == 0
    return f"{'view ok' if ok else 'FAIL'} {view_id}: {resp.get('msg', '')}"


def seed_ptj92_trace(client: Client, dry_run: bool) -> list[str]:
    existing = client.count_records(TRACE)
    if existing >= 11:
        return [f"skip trace: already {existing} rows"]
    rows = []
    for name, prod, proc_code, need, seg3, note in PTJ92_TRACE:
        rows.append(
            {
                "fields": {
                    "规则名称": name,
                    "产品": [prod],
                    "工序代码": [PROC[proc_code]],
                    "需要追溯号": need,
                    "段3来源字段": seg3,
                    "段3说明": note,
                }
            }
        )
    if dry_run:
        return [f"[dry-run] create {len(rows)} PTJ92 trace rules"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{TRACE}/records/batch_create",
        json={"records": rows},
    )
    n = len(resp.get("data", {}).get("records", []))
    return [f"PTJ92 trace rules: {resp.get('msg')} ({n} rows)"]


def seed_ptj92_control(client: Client, dry_run: bool) -> list[str]:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{CTRL}/records", params={"page_size": 500})
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        if f.get("批号文本") == "P-TEST-A":
            return ["skip control: P-TEST-A exists"]
    row = {
        "fields": {
            "批号文本": "P-TEST-A",
            "产品": [PROD_PTJ92],
            "工序代码": [PROC["#1020"]],
            "状态": "已下发",
            "本工序下发数量": 300,
        }
    }
    if dry_run:
        return ["[dry-run] create control P-TEST-A #1020"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{CTRL}/records",
        json=row,
    )
    ok = resp.get("code") == 0
    return [f"{'created' if ok else 'FAIL'} control P-TEST-A: {resp.get('msg', '')}"]


def has_main_row(client: Client, product: str, proc: str) -> bool:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 500})
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        prod = f.get("产品")
        proc_f = f.get("工序代码")
        prod_ids = prod[0].get("record_ids", []) if isinstance(prod, list) and prod else []
        proc_ids = proc_f[0].get("record_ids", []) if isinstance(proc_f, list) and proc_f else []
        if product in prod_ids and PROC[proc] in proc_ids and f.get("工序下发状态") == "已确认":
            return True
    return False


def seed_end_process_rows(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.extend(ensure_upstream_chain(client, dry_run))
    if has_main_row(client, PROD_STOPPER, "#70"):
        lines.append("skip: STOPPER #70 test row exists")
    else:
        row = {
            "fields": {
                "产品": [PROD_STOPPER],
                "工序代码": [PROC["#70"]],
                "上道批号": [UPSTREAM_STOPPER_60],
                "上道批号_STOPPER#70": [UPSTREAM_STOPPER_60],
                "合格数量": 55,
                "报废数量": 0,
                "工序下发状态": "已确认",
            }
        }
        if dry_run:
            lines.append("[dry-run] create STOPPER #70 test row")
        else:
            resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", json=row)
            lines.append(
                f"{'created' if resp.get('code')==0 else 'FAIL'} STOPPER #70: {resp.get('msg','')}"
            )
    return lines


def setup_ptj92(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for name, link in PTJ92_FIELDS:
        lines.append(ensure_field(client, MAIN, name, link, dry_run))

    view_ids: dict[str, str] = {}
    for vname, vtype in PTJ92_VIEWS:
        msg, vid = ensure_view(client, MAIN, vname, vtype, dry_run)
        lines.append(msg)
        if vid:
            view_ids[vname] = vid

    # refresh views list after create
    if not dry_run:
        for v in list_views(client, MAIN):
            if v.get("view_name") in dict(PTJ92_VIEWS):
                view_ids[v["view_name"]] = v["view_id"]

    ptj92_keep = {
        "vew_ptj1020": COMMON_KEEP | {"关联管控批_PTJ92#1020", "关联管控批", "工位代码"},
        "vew_ptj3040": COMMON_KEEP | {"上道批号_PTJ92#3040", "上道批号"},
        "vew_ptj50": COMMON_KEEP | {"上道批号_PTJ92#50", "上道批号"},
    }
    mapping = {
        "PTJ92·#1020报工": ptj92_keep["vew_ptj1020"],
        "PTJ92·#3040报工": ptj92_keep["vew_ptj3040"],
        "PTJ92·#50报工": ptj92_keep["vew_ptj50"],
    }
    for vname, keep in mapping.items():
        vid = view_ids.get(vname)
        if vid:
            lines.append(patch_view_columns(client, MAIN, vid, keep, dry_run))
        elif dry_run:
            lines.append(f"[dry-run] patch columns for {vname}")

    lines.extend(seed_ptj92_trace(client, dry_run))
    lines.extend(seed_ptj92_control(client, dry_run))
    return lines


def setup_reconciliation(client: Client, dry_run: bool) -> list[str]:
    views = list_views(client, CTRL)
    names = {v.get("view_name") for v in views}
    lines: list[str] = []
    if "管理·批工序对账" in names:
        lines.append("reconcile view: 管理·批工序对账 exists")
        lines.append(patch_view_columns(client, CTRL, RECON_VIEW_ID, RECON_KEEP, dry_run))
    else:
        lines.append("WARN: 管理·批工序对账 view missing — configure in Feishu UI")
    fields = {f["field_name"] for f in client.list_fields(CTRL)}
    for fn in ("对账差异", "是否超产", "合格合计"):
        lines.append(f"{'ok' if fn in fields else 'MISSING'}: ctrl field {fn}")
    return lines


def setup_end_views(client: Client, dry_run: bool) -> list[str]:
    from advance_v4_greenfield import VIEW_KEEP

    lines: list[str] = []
    for vid in END_VIEW_IDS:
        keep = VIEW_KEEP.get(vid)
        if keep:
            lines.append(patch_view_columns(client, MAIN, vid, keep, dry_run))
    lines.extend(seed_end_process_rows(client, dry_run))
    return lines


def run(dry_run: bool, skip_sync: bool, only: str | None) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    results: list[str] = []

    print("advance_v4_extensions")
    print("-" * 60)
    if only in (None, "end"):
        results.append("## 末道 #70/#80")
        results.extend(setup_end_views(client, dry_run))
    if only in (None, "reconcile"):
        results.append("## #4050 对账")
        results.extend(setup_reconciliation(client, dry_run))
    if only in (None, "ptj92"):
        results.append("## PTJ92 全链")
        results.extend(setup_ptj92(client, dry_run))

    for line in results:
        print(line)
    print("-" * 60)

    if not dry_run and not skip_sync:
        from sync_batch_summary import run_sync

        rows = run_sync(cfg, dry_run=False)
        print(f"sync: aggregated {len(rows)} summary rows")

    print("手工剩余：PTJ92 三视图关联筛选（见 openclaw-p3-ptj92-prompt-cn.md）")
    print("文档：docs/v4-extensions-execution-cn.md")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-sync", action="store_true")
    p.add_argument("--only", choices=["end", "reconcile", "ptj92"])
    args = p.parse_args()
    try:
        return run(args.dry_run, args.skip_sync, args.only)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
