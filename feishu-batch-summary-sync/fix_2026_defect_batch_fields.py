#!/usr/bin/env python3
"""修复 2026 不良明细表 / 返工完成清单 的批号镜像字段。

根因：
  - 不良明细「批号文本」查找引用误用已删除列 fldiDpvDL8，且用日志编号 CONTAIN 关联
  - 缺「生产批号」字段（2026 主表仅有「批号文本」，两列均镜像主表批号文本）
  - 返工完成清单「批号文本」链式引用不良明细的坏公式

修复：
  - 不良明细 批号文本 / 生产批号 → 关联生产记录.$column[主表.批号文本]
  - 返工完成清单 批号文本 → 关联生产记录.$column[主表.批号文本]
  - 生产区域：按工序读取主表 per-view 区域填报（#2030 A/B/C、#4050 MG、#60 J、#1020 J），
    不再只镜像批号后缀 A/B/C 汇总列

用法:
  python3 fix_2026_defect_batch_fields.py --dry-run
  python3 fix_2026_defect_batch_fields.py --fix
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, Client, MAIN_TABLE, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
DEFECT = "tblTk6xVopyoCjOF"
REWORK = "tblINpP7IJ67h4d9"

DEFECT_LINK = "fldYMesO29"
DEFECT_BATCH_TEXT = "fldF0FVlh6"
DEFECT_REGION = "fldVz3W2gH"
MAIN_BATCH_TEXT = "fldn9YCUgm"
MAIN_REGION = "fldguHnQGf"
MAIN_PROC_CODE = "fldwknKvOm"
MAIN_TRACE = "fldvkctHVc"
R2030_A = "fldwCQJKV9"
R2030_B = "fldpcw0RNH"
R2030_C = "fldzwiw1T5"
R4050_IN = "fld22XgABz"
R60_IN = "fldKXNHi9M"
R1020_IN = "fldg7t68ZR"

REWORK_BATCH_TEXT = "fldYKvdvRJ"
REWORK_REGION = "fldGzNLXAH"
REWORK_LINK = "fldZJCYfgv"

PROD_BATCH_NAME = "生产批号"


def _link_expr(table: str, link_field: str, target_col: str) -> str:
    return f"bitable::$table[{table}].$field[{link_field}].$column[{target_col}]"


def build_production_area_expr(table: str, link_field: str) -> str:
    """镜像主表实际填报区域：优先 per-view 输入，回退批号后缀 A/B/C。"""
    link = f"bitable::$table[{table}].$field[{link_field}]"
    code = f"{link}.$column[{MAIN_PROC_CODE}]"
    auto = f"{link}.$column[{MAIN_REGION}]"
    r2030 = (
        f"IF(NOT(ISBLANK({link}.$column[{R2030_A}])),{link}.$column[{R2030_A}],"
        f"IF(NOT(ISBLANK({link}.$column[{R2030_B}])),{link}.$column[{R2030_B}],"
        f'IF(NOT(ISBLANK({link}.$column[{R2030_C}])),{link}.$column[{R2030_C}],"")))'
    )
    return (
        "IFS("
        f'{code}="#2030",IF(NOT(ISBLANK({r2030})),{r2030},{auto}),'
        f'{code}="#4050",IF(NOT(ISBLANK({link}.$column[{R4050_IN}])),{link}.$column[{R4050_IN}],{auto}),'
        f'{code}="#60",IF(NOT(ISBLANK({link}.$column[{R60_IN}])),{link}.$column[{R60_IN}],{auto}),'
        f'{code}="#1020",IF(NOT(ISBLANK({link}.$column[{R1020_IN}])),{link}.$column[{R1020_IN}],{auto}),'
        f"TRUE(),{auto})"
    )


def patch_formula(client: Client, table: str, field_id: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] patch {name} ({field_id})"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields/{field_id}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def ensure_formula_field(
    client: Client, table: str, name: str, expr: str, dry_run: bool
) -> tuple[str, str]:
    fields = client.list_fields(table)
    existing = next((f for f in fields if f["field_name"] == name), None)
    if existing:
        line = patch_formula(client, table, existing["field_id"], name, expr, dry_run)
        return existing["field_id"], line
    if dry_run:
        return f"dry-{name}", f"[dry-run] create {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    fid = resp.get("data", {}).get("field", {}).get("field_id", "?")
    return fid, f"{'created' if ok else 'FAIL'}: {name} id={fid} — {resp.get('msg', '')}"


def verify(client: Client) -> list[str]:
    time.sleep(12)
    lines: list[str] = []
    linked_defects = [
        r for r in client.list_records(DEFECT)
        if r.get("fields", {}).get("主表行ID")
    ]
    lines.append(f"不良明细已关联主表: {len(linked_defects)} 行")
    for row in linked_defects:
        f = row["fields"]
        batch = extract_text(f.get("批号文本"))
        prod_batch = extract_text(f.get(PROD_BATCH_NAME))
        ok = bool(batch) and batch == prod_batch
        region = extract_text(f.get("生产区域"))
        ok = bool(batch) and batch == prod_batch and bool(region)
        lines.append(
            f"{'PASS' if ok else 'FAIL'} {row['record_id']} "
            f"批号={batch!r} 生产批号={prod_batch!r} 生产区域={region!r}"
        )

    rework_rows = client.list_records(REWORK)
    lines.append(f"返工完成清单: {len(rework_rows)} 行")
    for row in rework_rows:
        f = row["fields"]
        batch = extract_text(f.get("批号文本"))
        region = extract_text(f.get("生产区域"))
        ok = bool(batch) and bool(region)
        lines.append(
            f"{'PASS' if ok else 'FAIL'} {row['record_id']} "
            f"批号文本={batch!r} 生产区域={region!r}"
        )
    return lines


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_defect_batch_fields — 不良明细批号镜像")
    print("-" * 60)

    defect_batch_expr = _link_expr(DEFECT, DEFECT_LINK, MAIN_BATCH_TEXT)
    lines = [
        patch_formula(client, DEFECT, DEFECT_BATCH_TEXT, "批号文本", defect_batch_expr, dry_run),
    ]
    _, prod_line = ensure_formula_field(client, DEFECT, PROD_BATCH_NAME, defect_batch_expr, dry_run)
    lines.append(prod_line)
    lines.append(
        patch_formula(
            client,
            DEFECT,
            DEFECT_REGION,
            "生产区域",
            build_production_area_expr(DEFECT, DEFECT_LINK),
            dry_run,
        )
    )

    rework_batch_expr = _link_expr(REWORK, REWORK_LINK, MAIN_BATCH_TEXT)
    lines.append(
        patch_formula(client, REWORK, REWORK_BATCH_TEXT, "批号文本", rework_batch_expr, dry_run)
    )
    lines.append(
        patch_formula(
            client,
            REWORK,
            REWORK_REGION,
            "生产区域",
            build_production_area_expr(REWORK, REWORK_LINK),
            dry_run,
        )
    )

    # 完整追溯号：表单常用，一并镜像
    _, trace_line = ensure_formula_field(
        client, DEFECT, "完整追溯号", _link_expr(DEFECT, DEFECT_LINK, MAIN_TRACE), dry_run
    )
    lines.append(trace_line)

    for line in lines:
        print(line)

    if not dry_run:
        print("-" * 60)
        for line in verify(client):
            print(line)
    print("-" * 60)
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
