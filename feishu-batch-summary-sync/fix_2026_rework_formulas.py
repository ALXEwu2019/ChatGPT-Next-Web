#!/usr/bin/env python3
"""串联 2026 主表返工/出库工作流公式。

工作流（2026 Base）：
  品保录入不良明细 → 主表工序下发状态=待返工
  班组长在「返工完成清单」填返工后合格/报废 → 不良明细查找引用 → 主表查找引用
  品保确认 → 已确认 → 有效合格/有效报废生效 → 末道出库数量

修复项：
  - 补建「是否有不良」（不良明细 COUNTIF 本行 record_id）
  - 有效合格/有效报废 → P2 分支（有不良且已确认才用返工后数）
  - 返工校验（原 fldgLr0aR6 已失效）
  - 返工余数（仅待返工/待品保确认时计算）
  - 出库数量（#70/#80/#50 且已确认 = 有效合格数量）

用法:
  python3 fix_2026_rework_formulas.py --dry-run
  python3 fix_2026_rework_formulas.py --fix
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_number, extract_text

MAIN = MAIN_TABLE
DEFECT = "tblTk6xVopyoCjOF"

RECORD_ID_FIELD = "fldWbYGT5d"
DEFECT_MAIN_ID_COL = "fld0VBvV9o"
DEFECT_QTY = "fldeSXC388"

REWORK_OK = "fldVh6O4kM"
REWORK_SCRAP = "fldfGVR1m8"
REWORK_REMAINDER = "fldQ4CeV91"
REWORK_STATUS = "fldDoKSl8P"
REWORK_CHECK = "fldJ3SvX7r"
REWORK_QTY = "fldjGmfgKn"
OUTBOUND_QTY = "fldxpUvnJb"
VALID_OK = "fldhSjn8xF"
VALID_SCRAP = "fldLgCNdFq"
STATUS = "fldOUZwxgp"
OK_QTY = "fld5aVV8OD"
SCRAP_QTY = "fld9jmgvMn"
PROC_CODE = "fldwknKvOm"

HAS_DEFECT_NAME = "是否有不良"


def _ref(field_id: str) -> str:
    return f"bitable::$table[{MAIN}].$field[{field_id}]"


def build_has_defect_expr() -> str:
    return (
        f"IF(bitable::$table[{DEFECT}]"
        f".COUNTIF(CurrentValue.$column[{DEFECT_MAIN_ID_COL}]=RECORD_ID())>0,1,0)"
    )


def build_valid_ok_expr(has_defect_id: str) -> str:
    has_def = _ref(has_defect_id)
    status = _ref(STATUS)
    rework_ok = _ref(REWORK_OK)
    ok_qty = _ref(OK_QTY)
    return (
        f"IF({has_def},"
        f'IF({status}="已确认",{rework_ok},""),'
        f"{ok_qty})"
    )


def build_valid_scrap_expr(has_defect_id: str) -> str:
    has_def = _ref(has_defect_id)
    status = _ref(STATUS)
    rework_scrap = _ref(REWORK_SCRAP)
    scrap_qty = _ref(SCRAP_QTY)
    return (
        f"IF({has_def},"
        f'IF({status}="已确认",{rework_scrap},""),'
        f"IF(ISBLANK({scrap_qty}),0,{scrap_qty}))"
    )


def build_rework_remainder_expr() -> str:
    qty = _ref(REWORK_QTY)
    ok = _ref(REWORK_OK)
    scrap = _ref(REWORK_SCRAP)
    status = _ref(STATUS)
    return (
        f"IF({qty}=0,0,"
        f'IF(OR({status}="待返工",{status}="待品保确认"),'
        f"{qty}-{ok}-{scrap},0))"
    )


def build_rework_check_expr() -> str:
    qty = _ref(REWORK_QTY)
    ok = _ref(REWORK_OK)
    scrap = _ref(REWORK_SCRAP)
    defect_sum = (
        f"bitable::$table[{DEFECT}]"
        f".FILTER(CurrentValue.$column[{DEFECT_MAIN_ID_COL}]=RECORD_ID())"
        f".$column[{DEFECT_QTY}].SUM()"
    )
    return (
        f"IF({qty}=0,\"无返工\","
        f"IF({defect_sum}={qty},"
        f"IF({ok}+{scrap}={qty},\"一致\","
        f'IF(AND(ISBLANK({ok}),ISBLANK({scrap})),"待班组长回填","数量不符")),'
        f'\"待品保录入\"))'
    )


def build_outbound_expr(has_defect_id: str) -> str:
    status = _ref(STATUS)
    code = _ref(PROC_CODE)
    valid_ok = _ref(VALID_OK)
    return (
        f'IF(AND({status}="已确认",'
        f'OR({code}="#70",{code}="#80",{code}="#50")),'
        f"{valid_ok},\"\")"
    )


def ensure_has_defect_field(client: Client, dry_run: bool) -> str:
    fields = client.list_fields(MAIN)
    existing = next((f for f in fields if f["field_name"] == HAS_DEFECT_NAME), None)
    expr = build_has_defect_expr()
    if existing:
        fid = existing["field_id"]
        if dry_run:
            return f"[dry-run] patch {HAS_DEFECT_NAME} ({fid})"
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{fid}",
            json={
                "field_name": HAS_DEFECT_NAME,
                "type": 20,
                "property": {"formula_expression": expr},
            },
        )
        ok = resp.get("code") == 0
        return f"{'ok' if ok else 'FAIL'}: patch {HAS_DEFECT_NAME} — {resp.get('msg', '')}"
    if dry_run:
        return f"[dry-run] create {HAS_DEFECT_NAME}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields",
        json={
            "field_name": HAS_DEFECT_NAME,
            "type": 20,
            "property": {"formula_expression": expr},
        },
    )
    ok = resp.get("code") == 0
    fid = resp.get("data", {}).get("field", {}).get("field_id", "?")
    return f"{'created' if ok else 'FAIL'}: {HAS_DEFECT_NAME} id={fid} — {resp.get('msg', '')}"


def resolve_has_defect_id(client: Client) -> str:
    fields = client.list_fields(MAIN)
    f = next((x for x in fields if x["field_name"] == HAS_DEFECT_NAME), None)
    if not f:
        raise RuntimeError(f"主表缺少字段 {HAS_DEFECT_NAME}，请先执行 --fix")
    return f["field_id"]


def patch_formula(client: Client, field_id: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] patch {name} (len={len(expr)})"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{field_id}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def patch_outbound_field(client: Client, expr: str, dry_run: bool) -> str:
    """出库数量原为数字列，改为公式列。"""
    fields = client.list_fields(MAIN)
    field = next((f for f in fields if f["field_id"] == OUTBOUND_QTY), None)
    if not field:
        return "FAIL: 出库数量字段不存在"
    if field["type"] == 20 and dry_run:
        return "[dry-run] patch 出库数量 formula"
    if field["type"] != 20:
        if dry_run:
            return "[dry-run] recreate 出库数量 as formula (was number)"
        client.call(
            "DELETE",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{OUTBOUND_QTY}",
        )
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields",
            json={
                "field_name": "出库数量",
                "type": 20,
                "property": {"formula_expression": expr},
            },
        )
        ok = resp.get("code") == 0
        return f"{'recreated' if ok else 'FAIL'}: 出库数量 — {resp.get('msg', '')}"
    return patch_formula(client, OUTBOUND_QTY, "出库数量", expr, dry_run)


def verify(client: Client) -> list[str]:
    time.sleep(12)
    recs = client.list_records(MAIN)
    lines: list[str] = []
    for fname in (
        "是否有不良",
        "有效合格数量",
        "有效报废数量",
        "返工余数",
        "返工校验",
        "出库数量",
        "返工后合格数",
        "返工状态",
    ):
        vals = [r["fields"].get(fname) for r in recs]
        nonempty = sum(1 for v in vals if v not in (None, "", 0))
        sample = next((v for v in vals if v not in (None, "")), "")
        lines.append(f"{fname}: 非空/非零 {nonempty}/{len(recs)} 样例={sample!r}")

    # 无不良已确认行：有效合格应等于良品数量
    for r in recs:
        f = r["fields"]
        if extract_text(f.get("工序下发状态")) != "已确认":
            continue
        ok_qty = extract_number(f.get("良品数量"))
        valid = extract_number(f.get("有效合格数量"))
        has_def = extract_number(f.get("是否有不良")) or 0
        if has_def == 0 and ok_qty is not None and valid is not None:
            match = valid == ok_qty
            lines.append(
                f"{'PASS' if match else 'FAIL'} 无不良已确认 良品={ok_qty} 有效合格={valid}"
            )
            break
    else:
        lines.append("WARN: 未找到无不良已确认行做对照")

    outbound_procs = {"#70", "#80", "#50"}
    for r in recs:
        f = r["fields"]
        code = extract_text(f.get("工序代码"))
        if code in outbound_procs and extract_text(f.get("工序下发状态")) == "已确认":
            out_q = f.get("出库数量")
            valid = f.get("有效合格数量")
            lines.append(
                f"末道 {code} 出库={out_q!r} 有效合格={valid!r} "
                f"{'PASS' if out_q == valid else 'CHECK'}"
            )
            break
    return lines


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_rework_formulas — 返工/出库串联")
    print("-" * 60)

    print(ensure_has_defect_field(client, dry_run))
    if not dry_run:
        has_defect_id = resolve_has_defect_id(client)
    else:
        has_defect_id = "fld_HAS_DEFECT_DRY"

    patches = [
        (VALID_OK, "有效合格数量", build_valid_ok_expr(has_defect_id)),
        (VALID_SCRAP, "有效报废数量", build_valid_scrap_expr(has_defect_id)),
        (REWORK_REMAINDER, "返工余数", build_rework_remainder_expr()),
        (REWORK_CHECK, "返工校验", build_rework_check_expr()),
    ]
    for fid, name, expr in patches:
        print(patch_formula(client, fid, name, expr, dry_run))

    print(patch_outbound_field(client, build_outbound_expr(has_defect_id), dry_run))

    print("-" * 60)
    print("保留查找引用（不良明细→主表）：返工后合格数、返工后报废数、返工状态")
    print("  班组长在「返工完成清单」回填 → 不良明细镜像 → 主表自动汇总")

    if not dry_run:
        print("-" * 60)
        for line in verify(client):
            print(line)
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
