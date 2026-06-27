#!/usr/bin/env python3
"""梳理并修复 2026「仓库出入库表」字段与视图。

业务逻辑（L5 仓储层）：
  出库：末道 #70 / #80 / #50 主表已确认 → 主表.出库数量 = 有效合格数量
        仓储选「关联生产记录」登记出库流水，数量 ≤ 应出数量
  入库：计划下发批次入仓 → 选「批号」(管控表) 登记入库流水

用法:
  python3 fix_2026_warehouse_table.py --dry-run
  python3 fix_2026_warehouse_table.py --fix
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from remediate_2026_summary import APP, Client, MAIN_TABLE, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
WH = "tbl8lKqC9zpheaCc"
CTRL = "tblyvJJhyq5KoT4F"

WH_MAIN_LINK = "fldsk4WCVi"
WH_CTRL_LINK = "fldaJZIQdE"
WH_BATCH_TEXT = "fldEBaHq0E"

MAIN_BATCH = "fldn9YCUgm"
MAIN_PRODUCT = "fldxzxo5Tp"
MAIN_PROC = "fldwknKvOm"
MAIN_TRACE = "fldvkctHVc"
MAIN_OUT_QTY = "fldDsuAmgV"
MAIN_STATUS = "fldOUZwxgp"

CTRL_BATCH = "fldHJY853n"

OUTBOUND_PROCS = ("#70", "#80", "#50")

VIEW_OUT_FORM = "仓储·出库登记"
VIEW_IN_FORM = "仓储·入库登记"
VIEW_LEDGER = "仓储·流水总览"

LEDGER_KEEP = {
    "流水编号",
    "流水类型",
    "批号文本",
    "产品",
    "工序代码",
    "完整追溯号",
    "关联生产记录",
    "批号",
    "应出数量",
    "数量",
    "数量校验",
    "经办人",
    "出入库时间",
    "备注",
}


def _link(table: str, link_fid: str, col_fid: str) -> str:
    return f"bitable::$table[{table}].$field[{link_fid}].$column[{col_fid}]"


def build_batch_text_expr() -> str:
    main_batch = _link(WH, WH_MAIN_LINK, MAIN_BATCH)
    ctrl_batch = _link(WH, WH_CTRL_LINK, CTRL_BATCH)
    main_link = f"bitable::$table[{WH}].$field[{WH_MAIN_LINK}]"
    return f"IF(NOT(ISBLANK({main_link})),{main_batch},{ctrl_batch})"


def build_mirror_expr(col: str) -> str:
    return _link(WH, WH_MAIN_LINK, col)


def build_qty_check_expr(out_qty_field: str) -> str:
    qty = f"bitable::$table[{WH}].$field[fldwCy0NQa]"
    expect = f"bitable::$table[{WH}].$field[{out_qty_field}]"
    flow = f"bitable::$table[{WH}].$field[fldCeRnMA0]"
    return (
        f'IF({flow}="出库",'
        f'IF(ISBLANK({expect}),"非末道出库",'
        f'IF({qty}>{expect},"超发","正常")),'
        f'IF({flow}="入库","入库",""))'
    )


def patch_formula(client: Client, fid: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] {name}"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{WH}/fields/{fid}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def ensure_formula(client: Client, name: str, expr: str, dry_run: bool) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(WH)}
    if name in fields:
        return patch_formula(client, fields[name]["field_id"], name, expr, dry_run)
    if dry_run:
        return f"[dry-run] create {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{WH}/fields",
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
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{WH}/views", params=params)["data"]
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
        f"/bitable/v1/apps/{APP}/tables/{WH}/views",
        json={"view_name": name, "view_type": "grid"},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create view {name}: {resp.get('msg')}")
    return resp["data"]["view"]["view_id"]


def patch_view_columns(client: Client, view_id: str, keep: set[str], dry_run: bool) -> str:
    fields = client.list_fields(WH)
    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary = next(f["field_id"] for f in fields if f.get("is_primary"))
    keep_ids = {primary, *(name_to_id[n] for n in keep if n in name_to_id)}
    hidden = [f["field_id"] for f in fields if f["field_id"] not in keep_ids]
    if dry_run:
        return f"[dry-run] view columns hide {len(hidden)}"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{WH}/views/{view_id}",
        json={"property": {"hidden_fields": hidden}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: view columns — {resp.get('msg', '')}"


def patch_view_filter_outbound(client: Client, view_id: str, dry_run: bool) -> str:
    """出库登记：流水类型 = 出库。"""
    fields = client.list_fields(WH)
    flow = next(f for f in fields if f["field_name"] == "流水类型")
    opt = next(o for o in flow["property"]["options"] if o["name"] == "出库")
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
        return "[dry-run] filter 出库"
    resp = client.call("PATCH", f"/bitable/v1/apps/{APP}/tables/{WH}/views/{view_id}", json=body)
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: filter 出库 — {resp.get('msg', '')}"


def patch_view_filter_inbound(client: Client, view_id: str, dry_run: bool) -> str:
    fields = client.list_fields(WH)
    flow = next(f for f in fields if f["field_name"] == "流水类型")
    opt = next(o for o in flow["property"]["options"] if o["name"] == "入库")
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
        return "[dry-run] filter 入库"
    resp = client.call("PATCH", f"/bitable/v1/apps/{APP}/tables/{WH}/views/{view_id}", json=body)
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: filter 入库 — {resp.get('msg', '')}"


def verify(client: Client) -> list[str]:
    time.sleep(8)
    lines: list[str] = []
    fields = {f["field_name"] for f in client.list_fields(WH)}
    for n in ("批号文本", "产品", "工序代码", "应出数量", "数量校验"):
        lines.append(f"{'PASS' if n in fields else 'FAIL'}: 字段 {n}")
    pending = list_pending_outbound(client)
    lines.append(f"主表待出库（已确认末道、有出库数、未登记）: {len(pending)} 行")
    for row in pending[:5]:
        lines.append(f"  · {row['batch']} {row['proc']} 应出={row['out_qty']}")
    return lines


def list_pending_outbound(client: Client) -> list[dict]:
    pending: list[dict] = []
    for row in client.list_records(MAIN):
        f = row.get("fields", {})
        if extract_text(f.get("工序下发状态")) not in ("已确认", "已审核"):
            continue
        proc = extract_text(f.get("工序代码"))
        if proc not in OUTBOUND_PROCS:
            continue
        out_q = f.get("出库数量")
        if out_q in (None, "", 0):
            continue
        wh_link = f.get("仓库出入库表")
        if wh_link and isinstance(wh_link, list) and wh_link[0].get("record_ids"):
            continue
        pending.append(
            {
                "record_id": row["record_id"],
                "batch": extract_text(f.get("批号文本")),
                "proc": proc,
                "out_qty": out_q,
            }
        )
    return pending


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_warehouse_table — 仓库出入库梳理")
    print("-" * 60)

    lines = [
        patch_formula(client, WH_BATCH_TEXT, "批号文本", build_batch_text_expr(), dry_run),
        ensure_formula(client, "产品", build_mirror_expr(MAIN_PRODUCT), dry_run),
        ensure_formula(client, "工序代码", build_mirror_expr(MAIN_PROC), dry_run),
        ensure_formula(client, "完整追溯号", build_mirror_expr(MAIN_TRACE), dry_run),
        ensure_formula(client, "应出数量", build_mirror_expr(MAIN_OUT_QTY), dry_run),
    ]
    fields = {f["field_name"]: f for f in client.list_fields(WH)} if not dry_run else {}
    out_fid = fields.get("应出数量", {}).get("field_id", "fld_OUT_QTY")
    lines.append(ensure_formula(client, "数量校验", build_qty_check_expr(out_fid), dry_run))

    for line in lines:
        print(line)

    print("\n## 视图")
    if not dry_run:
        fields = {f["field_name"]: f for f in client.list_fields(WH)}
        out_fid = fields["应出数量"]["field_id"]
        patch_formula(client, fields["数量校验"]["field_id"], "数量校验", build_qty_check_expr(out_fid), dry_run)

    vid_out = ensure_view(client, VIEW_OUT_FORM, dry_run)
    vid_in = ensure_view(client, VIEW_IN_FORM, dry_run)
    vid_ledger = ensure_view(client, VIEW_LEDGER, dry_run)
    if not dry_run and isinstance(vid_out, str) and not vid_out.startswith("dry"):
        print(patch_view_columns(client, vid_out, LEDGER_KEEP, dry_run))
        print(patch_view_filter_outbound(client, vid_out, dry_run))
    elif dry_run:
        print(f"[dry-run] {VIEW_OUT_FORM}")
    if not dry_run and isinstance(vid_in, str) and not vid_in.startswith("dry"):
        print(patch_view_columns(client, vid_in, LEDGER_KEEP, dry_run))
        print(patch_view_filter_inbound(client, vid_in, dry_run))
    elif dry_run:
        print(f"[dry-run] {VIEW_IN_FORM}")
    if not dry_run and isinstance(vid_ledger, str) and not vid_ledger.startswith("dry"):
        print(patch_view_columns(client, vid_ledger, LEDGER_KEEP, dry_run))
    elif dry_run:
        print(f"[dry-run] {VIEW_LEDGER}")

    if not dry_run:
        print("\n## 验收")
        for line in verify(client):
            print(line)

    print("-" * 60)
    print("工作流：")
    print("  出库 → 仓储·出库登记：选关联生产记录(末道已确认) → 填数量/经办人")
    print("  入库 → 仓储·入库登记：选批号(管控表) → 填数量/经办人")
    print(f"  链接: https://kcnfxml9dtzq.feishu.cn/base/{APP}?table={WH}")
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
