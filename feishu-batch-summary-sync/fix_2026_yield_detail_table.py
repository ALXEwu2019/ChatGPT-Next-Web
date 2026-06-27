#!/usr/bin/env python3
"""梳理 2026「报工产量明细表」：镜像字段、视图、与主表对账。

行模型 C2：
  关联报工头 × 生产区域 × 报工类型(合格/返工/报废) × 数量

用法:
  python3 fix_2026_yield_detail_table.py --dry-run
  python3 fix_2026_yield_detail_table.py --fix
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from remediate_2026_summary import APP, Client, MAIN_TABLE, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
DETAIL = "tblheKbZ7R9LxtvF"

LINK = "fldwoMGMjN"
BATCH_TEXT = "fldZLTps45"
PRODUCT = "fldAxROAE1"
PROC = "fldsUBu9NX"
REGION = "fldd3bCLnm"
YIELD_TYPE = "fldcbd3z3Z"
QTY = "fldQfSIzdH"

MAIN_BATCH = "fldn9YCUgm"
MAIN_PRODUCT = "fldxzxo5Tp"
MAIN_PROC = "fldwknKvOm"
MAIN_PROC_NAME = "fldN48QWI4"
MAIN_BATCH_KEY = "fldnWH0ZKH"
MAIN_TRACE = "fldvkctHVc"
MAIN_STATUS = "fldOUZwxgp"

VIEW_LEDGER = "产量·明细台账"
VIEW_OK = "产量·合格"
VIEW_SCRAP = "产量·报废"

LEDGER_KEEP = {
    "明细编号",
    "关联报工头",
    "批号文本",
    "产品",
    "工序代码",
    "工序名称",
    "批工序键",
    "完整追溯号",
    "工序下发状态",
    "生产区域",
    "报工类型",
    "数量",
    "行摘要",
    "备注",
}


def _link(table: str, link_fid: str, col_fid: str) -> str:
    return f"bitable::$table[{table}].$field[{link_fid}].$column[{col_fid}]"


def build_row_summary_expr() -> str:
    batch = f"bitable::$table[{DETAIL}].$field[{BATCH_TEXT}]"
    proc = f"bitable::$table[{DETAIL}].$field[{PROC}]"
    region = f"bitable::$table[{DETAIL}].$field[{REGION}]"
    ytype = f"bitable::$table[{DETAIL}].$field[{YIELD_TYPE}]"
    qty = f"bitable::$table[{DETAIL}].$field[{QTY}]"
    return f'CONCATENATE({batch}," ",{proc}," ",{region}," ",{ytype},"=",{qty})'


def patch_formula(client: Client, fid: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] {name}"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{DETAIL}/fields/{fid}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def ensure_formula(client: Client, name: str, expr: str, dry_run: bool) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(DETAIL)}
    if name in fields:
        return patch_formula(client, fields[name]["field_id"], name, expr, dry_run)
    if dry_run:
        return f"[dry-run] create {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{DETAIL}/fields",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    fid = resp.get("data", {}).get("field", {}).get("field_id", "?")
    return f"{'created' if ok else 'FAIL'}: {name} id={fid} — {resp.get('msg', '')}"


def list_views(client: Client) -> dict[str, str]:
    views: dict[str, str] = {}
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{DETAIL}/views", params=params)["data"]
        for v in data["items"]:
            views[v["view_name"]] = v["view_id"]
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return views


def ensure_view(client: Client, name: str, dry_run: bool) -> str | None:
    views = list_views(client)
    if name in views:
        return views[name]
    if dry_run:
        return f"dry-{name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{DETAIL}/views",
        json={"view_name": name, "view_type": "grid"},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create view {name}: {resp.get('msg')}")
    return resp["data"]["view"]["view_id"]


def patch_view_columns(client: Client, view_id: str, keep: set[str], dry_run: bool) -> str:
    fields = client.list_fields(DETAIL)
    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary = next(f["field_id"] for f in fields if f.get("is_primary"))
    keep_ids = {primary, *(name_to_id[n] for n in keep if n in name_to_id)}
    hidden = [f["field_id"] for f in fields if f["field_id"] not in keep_ids]
    if dry_run:
        return f"[dry-run] view {view_id} hide {len(hidden)}"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{DETAIL}/views/{view_id}",
        json={"property": {"hidden_fields": hidden}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: columns — {resp.get('msg', '')}"


def patch_type_filter(client: Client, view_id: str, type_name: str, dry_run: bool) -> str:
    fields = client.list_fields(DETAIL)
    flow = next(f for f in fields if f["field_name"] == "报工类型")
    opt = next(o for o in flow["property"]["options"] if o["name"] == type_name)
    body = {
        "property": {
            "filter_info": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_id": flow["field_id"],
                        "field_type": flow["type"],
                        "operator": "is",
                        "value": json.dumps([opt["id"]]),
                    }
                ],
            }
        }
    }
    if dry_run:
        return f"[dry-run] filter {type_name}"
    resp = client.call("PATCH", f"/bitable/v1/apps/{APP}/tables/{DETAIL}/views/{view_id}", json=body)
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: filter {type_name} — {resp.get('msg', '')}"


def verify(client: Client) -> list[str]:
    time.sleep(8)
    lines: list[str] = []
    fields = {f["field_name"] for f in client.list_fields(DETAIL)}
    for n in ("批号文本", "产品", "工序代码", "批工序键", "行摘要"):
        lines.append(f"{'PASS' if n in fields else 'FAIL'}: 字段 {n}")
    rows = client.list_records(DETAIL)
    lines.append(f"明细行数: {len(rows)}")
    for row in rows[:5]:
        f = row["fields"]
        lines.append(
            f"  {extract_text(f.get('批号文本'))} {extract_text(f.get('工序代码'))} "
            f"{extract_text(f.get('生产区域'))} {extract_text(f.get('报工类型'))}={f.get('数量')}"
        )
    return lines


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_yield_detail_table — 报工产量明细梳理")
    print("-" * 60)

    mirror = _link(DETAIL, LINK, MAIN_BATCH)
    lines = [
        patch_formula(client, BATCH_TEXT, "批号文本", mirror, dry_run),
        patch_formula(client, PRODUCT, "产品", _link(DETAIL, LINK, MAIN_PRODUCT), dry_run),
        patch_formula(client, PROC, "工序代码", _link(DETAIL, LINK, MAIN_PROC), dry_run),
        ensure_formula(client, "工序名称", _link(DETAIL, LINK, MAIN_PROC_NAME), dry_run),
        ensure_formula(client, "批工序键", _link(DETAIL, LINK, MAIN_BATCH_KEY), dry_run),
        ensure_formula(client, "完整追溯号", _link(DETAIL, LINK, MAIN_TRACE), dry_run),
        ensure_formula(client, "工序下发状态", _link(DETAIL, LINK, MAIN_STATUS), dry_run),
        ensure_formula(client, "行摘要", build_row_summary_expr(), dry_run),
    ]
    for line in lines:
        print(line)

    print("\n## 视图")
    vid_ledger = ensure_view(client, VIEW_LEDGER, dry_run)
    vid_ok = ensure_view(client, VIEW_OK, dry_run)
    vid_scrap = ensure_view(client, VIEW_SCRAP, dry_run)
    if not dry_run:
        for vid, label in ((vid_ledger, "ledger"), (vid_ok, "ok"), (vid_scrap, "scrap")):
            if isinstance(vid, str) and not vid.startswith("dry"):
                print(patch_view_columns(client, vid, LEDGER_KEEP, dry_run))
        if isinstance(vid_ok, str) and not vid_ok.startswith("dry"):
            print(patch_type_filter(client, vid_ok, "合格", dry_run))
        if isinstance(vid_scrap, str) and not vid_scrap.startswith("dry"):
            print(patch_type_filter(client, vid_scrap, "报废", dry_run))
    else:
        print(f"[dry-run] views {VIEW_LEDGER}/{VIEW_OK}/{VIEW_SCRAP}")

    if not dry_run:
        print("\n## 验收")
        for line in verify(client):
            print(line)

    print("-" * 60)
    print("下一步: python3 sync_yield_detail_from_main.py --backfill")
    print(f"链接: https://kcnfxml9dtzq.feishu.cn/base/{APP}?table={DETAIL}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix", action="store_true")
    args = p.parse_args()
    if not args.fix and not args.dry_run:
        p.error("specify --fix or --dry-run")
    try:
        return run(args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
