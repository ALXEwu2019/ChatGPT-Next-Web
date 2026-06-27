#!/usr/bin/env python3
"""2026 主表「产品 1」公式：合并 per-view 产品标记列（与批号文本同构）。

用法:
  python3 fix_2026_product_field.py --dry-run
  python3 fix_2026_product_field.py --fix
  python3 fix_2026_product_field.py --fix --backfill-markers
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
PRODUCT_ONE = "fldzeIITrZ"  # 产品 1
PRODUCT_NAME_LOOKUP = "fldxzxo5Tp"  # 产品名称文本
PRODUCT_LINK = "fldrmvZbgA"  # 产品（关联，表单可逐步弃用）

MARKERS = (
    "fldizlyUHP",  # 产品-STOPPER
    "fldTDRnrQO",  # 产品-止动块
    "fld1kbdAGl",  # 产品-PTJ92
)

MARKER_BY_PRODUCT = {
    "STOPPER": ("产品-STOPPER", "STOPPER"),
    "止动块": ("产品-止动块", "止动块"),
    "PTJ92": ("产品-PTJ92", "PTJ92"),
}


def _ref(fid: str) -> str:
    return f"bitable::$table[{MAIN}].$field[{fid}]"


def build_product_one_expr() -> str:
    terms = ",".join(_ref(fid) for fid in MARKERS)
    return f"CONCATENATE({terms})"


def build_product_name_expr() -> str:
    return _ref(PRODUCT_ONE)


def patch_field(client: Client, fid: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] patch {name} (len={len(expr)})"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{fid}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def backfill_markers(client: Client, dry_run: bool) -> list[str]:
    """按现网「产品」关联或 产品 1 文本，回填 per-view 产品标记列。"""
    updates: list[dict] = []
    for row in client.list_records(MAIN_TABLE):
        f = row.get("fields", {})
        prod = extract_text(f.get("产品 1")) or extract_text(f.get("产品名称文本")) or extract_text(f.get("产品"))
        if prod not in MARKER_BY_PRODUCT:
            continue
        col, val = MARKER_BY_PRODUCT[prod]
        if extract_text(f.get(col)) == val:
            continue
        updates.append({"record_id": row["record_id"], "fields": {col: val}})

    if not updates:
        return ["skip: 产品标记列已齐"]
    if dry_run:
        return [f"[dry-run] backfill 产品标记 {len(updates)} 行"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/batch_update",
        json={"records": updates},
    )
    ok = resp.get("code") == 0
    return [f"{'ok' if ok else 'FAIL'}: 产品标记回填 {len(updates)} 行 — {resp.get('msg', '')}"]


def verify(client: Client) -> list[str]:
    time.sleep(10)
    recs = client.list_records(MAIN_TABLE)
    lines = [f"主表 {len(recs)} 行"]
    for fname in ("产品 1", "产品名称文本", "产品"):
        n = sum(1 for r in recs if extract_text(r["fields"].get(fname)))
        lines.append(f"  {fname} 有值: {n}/{len(recs)}")
    mismatch = 0
    for r in recs:
        f = r["fields"]
        p1 = extract_text(f.get("产品 1"))
        pl = extract_text(f.get("产品"))
        if p1 and pl and p1 != pl:
            mismatch += 1
    lines.append(f"  产品1 vs 产品关联 不一致: {mismatch}")
    return lines


def run(fix: bool, dry_run: bool, backfill: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_product_field")
    print("-" * 60)
    if backfill:
        for line in backfill_markers(client, dry_run):
            print(line)
    if fix or dry_run:
        print(patch_field(client, PRODUCT_ONE, "产品 1", build_product_one_expr(), dry_run))
        print(patch_field(client, PRODUCT_NAME_LOOKUP, "产品名称文本", build_product_name_expr(), dry_run))
    if fix and not dry_run:
        for line in verify(client):
            print(line)
    print("-" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--backfill-markers", action="store_true")
    args = p.parse_args()
    if not args.fix and not args.dry_run and not args.backfill_markers:
        p.error("specify --fix, --dry-run, or --backfill-markers")
    try:
        return run(args.fix, args.dry_run, args.backfill_markers)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
