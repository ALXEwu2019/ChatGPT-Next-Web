#!/usr/bin/env python3
"""修复 2026 主表 工序名称/工序代码 公式（删除横向区域列后引用失效）。"""

from __future__ import annotations

import argparse
import sys
import time

import requests

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config

# 工序名称 LIST 中仍存在的 per-工序标记列（勿含已删横向区域列）
PROCESS_MARKER_FIELDS = (
    "fldanuNtgL",  # #2030车床自动化-STOPPER
    "fld0HRCruy",  # #60检查机-STOPPER
    "fldwEfoLvq",  # #70出库-STOPPER
    "fld4NnbIfV",  # #2030车床自动化-止动块
    "fldg3CgFwM",  # #60检查机-止动块
    "fld8SCSOIG",  # #70外观检-止动块
    "fldeguzZ66",  # #80出库-止动块
    "fldsdBrnXH",  # #1020车床自动化-PTJ92
    "fld84mJwip",  # #3040-PTJ92
)

PROC_NAME_FIELD = "fldN48QWI4"
PROC_CODE_FIELD = "fldwknKvOm"
PROC_AREA_AUTO_FIELD = "fldguHnQGf"
BATCH_TEXT_FIELD = "fldn9YCUgm"
PROC_TABLE = "tblt0I1rLezriVTM"
PROC_NAME_COL = "fldm2TVT2R"
PROC_CODE_COL = "fldLgPguMy"

RECREATE_MARKERS = (
    ("#4050磨床-STOPPER", ["#4050磨床-STOPPER"]),
    ("#4050磨床-止动块", ["#4050磨床-止动块"]),
)


def build_process_name_expr() -> str:
    refs = ",".join(f"bitable::$table[{MAIN_TABLE}].$field[{fid}]" for fid in PROCESS_MARKER_FIELDS)
    return (
        "ARRAYJOIN("
        f"FILTER(LIST({refs}),NOT(ISBLANK(CurrentValue))),"
        '","'
        ")"
    )


def build_process_code_expr() -> str:
    return (
        f'IFERROR(FIRST(bitable::$table[{PROC_TABLE}].FILTER('
        f"CurrentValue.$column[{PROC_NAME_COL}] = "
        f"bitable::$table[{MAIN_TABLE}].$field[{PROC_NAME_FIELD}]"
        f").$column[{PROC_CODE_COL}]),\"\")"
    )


def recreate_marker_field(client: Client, name: str, options: list[str], dry_run: bool) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(MAIN_TABLE)}
    if name in fields:
        return f"skip exists: {name}"
    if dry_run:
        return f"[dry-run] create {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields",
        json={
            "field_name": name,
            "type": 3,
            "property": {"options": [{"name": o} for o in options]},
        },
    )
    if resp.get("code") != 0:
        return f"FAIL create {name}: {resp.get('msg')}"
    fid = resp.get("data", {}).get("field", {}).get("field_id")
    return f"created: {name} ({fid})"


def build_production_area_expr() -> str:
    """从批号文本末段推断 A/B/C（#2030 合并区）；-D 批次归入 C 区。"""
    batch = f"bitable::$table[{MAIN_TABLE}].$field[{BATCH_TEXT_FIELD}]"
    return (
        f'IF(CONTAINTEXT({batch},"-A"),"A",'
        f'IF(CONTAINTEXT({batch},"-B"),"B",'
        f'IF(OR(CONTAINTEXT({batch},"-C"),CONTAINTEXT({batch},"-D")),"C","")))'
    )


def patch_area_formula(client: Client, dry_run: bool) -> list[str]:
    expr = build_production_area_expr()
    if dry_run:
        return [f"[dry-run] patch 生产区域_自动计算 (len={len(expr)})"]
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{PROC_AREA_AUTO_FIELD}",
        json={
            "field_name": "生产区域_自动计算",
            "type": 20,
            "property": {"formula_expression": expr},
        },
    )
    return [f"{'ok' if resp.get('code')==0 else 'FAIL'}: 生产区域_自动计算 — {resp.get('msg','')}"]


def patch_formulas(client: Client, dry_run: bool) -> list[str]:
    name_expr = build_process_name_expr()
    code_expr = build_process_code_expr()
    lines: list[str] = []
    for fid, fname in ((PROC_NAME_FIELD, "工序名称"), (PROC_CODE_FIELD, "工序代码")):
        if dry_run:
            lines.append(f"[dry-run] patch {fname} (len={len(name_expr if fname=='工序名称' else code_expr)})")
            continue
        expr = name_expr if fname == "工序名称" else code_expr
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{fid}",
            json={"field_name": fname, "type": 20, "property": {"formula_expression": expr}},
        )
        lines.append(f"{'ok' if resp.get('code')==0 else 'FAIL'}: {fname} — {resp.get('msg','')}")
    return lines


def verify(client: Client) -> list[str]:
    time.sleep(8)
    from sync_batch_summary import extract_text

    recs = client.list_records(MAIN_TABLE)
    codes = [extract_text(r["fields"].get("工序代码")) for r in recs]
    areas = [extract_text(r["fields"].get("生产区域")) for r in recs]
    nonempty = sum(1 for c in codes if c)
    areas_ok = sum(1 for a in areas if a)
    return [
        f"工序代码非空: {nonempty}/{len(recs)} 样例={codes[0]!r}",
        f"生产区域非空: {areas_ok}/{len(recs)} 样例={areas[0]!r}",
    ]


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_process_formulas")
    print("-" * 60)
    for name, opts in RECREATE_MARKERS:
        print(recreate_marker_field(client, name, opts, dry_run))
    for line in patch_formulas(client, dry_run):
        print(line)
    for line in patch_area_formula(client, dry_run):
        print(line)
    if not dry_run:
        for line in verify(client):
            print(line)
    print("-" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
