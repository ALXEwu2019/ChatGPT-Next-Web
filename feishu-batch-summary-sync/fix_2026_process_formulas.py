#!/usr/bin/env python3
"""修复 2026 主表工序/追溯公式（工序名称、工序代码、批工序键、完整追溯号）。

根因：工序标记列 #2030车床自动化-STOPPER 已删除；工序名称公式引用失效导致下游全空。

用法:
  python3 fix_2026_process_formulas.py --dry-run
  python3 fix_2026_process_formulas.py --fix
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
PROC_TABLE = "tblt0I1rLezriVTM"

PRODUCT_NAME = "fldxzxo5Tp"
PROC_NAME_FIELD = "fldN48QWI4"
PROC_CODE_FIELD = "fldwknKvOm"
BATCH_TEXT_FIELD = "fldn9YCUgm"
BATCH_KEY_FIELD = "fldnWH0ZKH"
FULL_TRACE_FIELD = "fldvkctHVc"
MONTH_DAY_FIELD = "fld7P48wOM"
DEVICE_SUFFIX_FIELD = "fldnYmMJlV"
PROC_AREA_AUTO_FIELD = "fldguHnQGf"

# STOPPER
M2030_STOPPER = "fldQncuYR6"
CTRL_STOPPER_2030 = "fldQ7m86rl"
R2030_A = "fldwCQJKV9"
R2030_B = "fldpcw0RNH"
R2030_C = "fldzwiw1T5"
M4050_STOPPER = "fldmeVALU6"
R4050_STOPPER = "fld22XgABz"
M60_STOPPER = "fld0HRCruy"
R60_STOPPER = "fldKXNHi9M"
M70_STOPPER = "fldwEfoLvq"

# 止动块
M2030_ZD = "fld4NnbIfV"
CTRL_ZD_4050 = "fldL9IMguv"
M4050_ZD = "fldWDhWqEH"
M60_ZD = "fldg3CgFwM"
M70_ZD = "fld8SCSOIG"
M80_ZD = "fldeguzZ66"

# PTJ92
M1020_PTJ = "fldsdBrnXH"
CTRL_PTJ_1020 = "fldn15sQzq"
R1020_PTJ = "fldg7t68ZR"
M3040_PTJ = "fld84mJwip"
M50_PTJ = "fldWvyWtNF"


def _ref(field_id: str) -> str:
    return f"bitable::$table[{MAIN}].$field[{field_id}]"


def _any_not_blank(*field_ids: str) -> str:
    if len(field_ids) == 1:
        return f"NOT(ISBLANK({_ref(field_ids[0])}))"
    inner = ",".join(f"NOT(ISBLANK({_ref(fid)}))" for fid in field_ids)
    return f"OR({inner})"


def _product_is(name: str) -> str:
    return f'{_ref(PRODUCT_NAME)}="{name}"'


def build_process_code_expr() -> str:
    """按产品 + 已填标记/区域/管控列推断工序代码（不依赖工序名称）。"""
    p = _ref(PRODUCT_NAME)
    return (
        "IFS("
        f'AND({_product_is("STOPPER")},{_any_not_blank(M70_STOPPER)}),"#70",'
        f'AND({_product_is("STOPPER")},{_any_not_blank(M60_STOPPER, R60_STOPPER)}),"#60",'
        f'AND({_product_is("STOPPER")},{_any_not_blank(M4050_STOPPER, R4050_STOPPER)}),"#4050",'
        f'AND({_product_is("STOPPER")},{_any_not_blank(M2030_STOPPER, CTRL_STOPPER_2030, R2030_A, R2030_B, R2030_C)}),"#2030",'
        f'AND({_product_is("止动块")},{_any_not_blank(M80_ZD)}),"#80",'
        f'AND({_product_is("止动块")},{_any_not_blank(M70_ZD)}),"#70",'
        f'AND({_product_is("止动块")},{_any_not_blank(M60_ZD)}),"#60",'
        f'AND({_product_is("止动块")},{_any_not_blank(M4050_ZD, CTRL_ZD_4050)}),"#4050",'
        f'AND({_product_is("止动块")},{_any_not_blank(M2030_ZD)}),"#2030",'
        f'AND({_product_is("PTJ92")},{_any_not_blank(M50_PTJ)}),"#50",'
        f'AND({_product_is("PTJ92")},{_any_not_blank(M3040_PTJ)}),"#3040",'
        f'AND({_product_is("PTJ92")},{_any_not_blank(M1020_PTJ, CTRL_PTJ_1020, R1020_PTJ)}),"#1020",'
        'TRUE(),"")'
    )


def build_process_name_expr() -> str:
    """由产品 + 工序代码映射工序表标准名称。"""
    code = _ref(PROC_CODE_FIELD)
    return (
        "IFS("
        f'AND({_product_is("STOPPER")},{code}="#2030"),"#2030车床自动化-STOPPER",'
        f'AND({_product_is("STOPPER")},{code}="#4050"),"#4050磨床-STOPPER",'
        f'AND({_product_is("STOPPER")},{code}="#60"),"#60检查机-STOPPER",'
        f'AND({_product_is("STOPPER")},{code}="#70"),"#70出库-STOPPER",'
        f'AND({_product_is("止动块")},{code}="#2030"),"#2030车床自动化-止动块",'
        f'AND({_product_is("止动块")},{code}="#4050"),"#4050磨床-止动块",'
        f'AND({_product_is("止动块")},{code}="#60"),"#60检查机-止动块",'
        f'AND({_product_is("止动块")},{code}="#70"),"#70外观检-止动块",'
        f'AND({_product_is("止动块")},{code}="#80"),"#80出库-止动块",'
        f'AND({_product_is("PTJ92")},{code}="#1020"),"#1020车床自动化-PTJ92",'
        f'AND({_product_is("PTJ92")},{code}="#3040"),"#3040-PTJ92",'
        f'AND({_product_is("PTJ92")},{code}="#50"),"#50-PTJ92",'
        'TRUE(),"")'
    )


def build_region_2030_expr() -> str:
    """#2030 区域：优先区域列，否则空。"""
    return (
        f"IFERROR({_ref(R2030_A)},IFERROR({_ref(R2030_B)},{_ref(R2030_C)}))"
    )


def build_batch_key_expr() -> str:
    batch = _ref(BATCH_TEXT_FIELD)
    code = _ref(PROC_CODE_FIELD)
    r2030 = build_region_2030_expr()
    r4050 = f"IFERROR({_ref(R4050_STOPPER)},{_ref(PROC_AREA_AUTO_FIELD)})"
    return (
        "IFS("
        f'ISBLANK({batch}),"",'
        f'ISBLANK({code}),"",'
        f'{code}="#2030",CONCATENATE({batch},"-",{code},"-",{r2030}),'
        f'{code}="#4050",CONCATENATE({batch},"-",{code},"-",{r4050}),'
        f'TRUE(),CONCATENATE({batch},"-",{code})'
        ")"
    )


def build_full_trace_expr() -> str:
    """完整追溯号：批号-月日-区域/工位后缀（与现网逻辑一致，引用已校验字段）。"""
    batch = _ref(BATCH_TEXT_FIELD)
    month = _ref(MONTH_DAY_FIELD)
    code = _ref(PROC_CODE_FIELD)
    suffix = _ref(DEVICE_SUFFIX_FIELD)
    r2030 = build_region_2030_expr()
    r4050 = _ref(R4050_STOPPER)
    r60 = _ref(R60_STOPPER)
    r1020 = _ref(R1020_PTJ)
    trace_suffix = (
        f"IF(ISBLANK({suffix}),"
        f"IFS({code}=\"#2030\",{r2030},{code}=\"#4050\",{r4050},{code}=\"#60\",{r60},{code}=\"#1020\",{r1020},TRUE(),\"\"),"
        f"{suffix})"
    )
    return (
        f"IF(OR(ISBLANK({batch}),ISBLANK({month}),ISBLANK({code})),\"\","
        f"IF(OR({code}=\"#3040-50\",{code}=\"#3040\",{code}=\"#50\",{code}=\"#1020\",{code}=\"#70\",{code}=\"#80\"),"
        f"CONCATENATE({batch},\"-\",{month}),"
        f"IF(ISBLANK({trace_suffix}),\"\","
        f"CONCATENATE({batch},\"-\",{month},\"-\",{trace_suffix}))))"
    )


def build_production_area_expr() -> str:
    batch = _ref(BATCH_TEXT_FIELD)
    return (
        f'IF(CONTAINTEXT({batch},"-A"),"A",'
        f'IF(CONTAINTEXT({batch},"-B"),"B",'
        f'IF(OR(CONTAINTEXT({batch},"-C"),CONTAINTEXT({batch},"-D")),"C","")))'
    )


def patch_field(client: Client, field_id: str, name: str, expr: str, dry_run: bool) -> str:
    if dry_run:
        return f"[dry-run] patch {name} (len={len(expr)})"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{field_id}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}"


def verify(client: Client) -> list[str]:
    time.sleep(12)
    recs = client.list_records(MAIN_TABLE)
    lines: list[str] = []
    for fname in ("工序代码", "工序名称", "批工序键", "完整追溯号"):
        vals = [extract_text(r["fields"].get(fname)) for r in recs]
        nonempty = sum(1 for v in vals if v)
        sample = next((v for v in vals if v), "")
        lines.append(f"{fname} 非空: {nonempty}/{len(recs)} 样例={sample!r}")
    return lines


def run(dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_process_formulas")
    print("-" * 60)

    patches = [
        (PROC_CODE_FIELD, "工序代码", build_process_code_expr()),
        (PROC_NAME_FIELD, "工序名称", build_process_name_expr()),
        (PROC_AREA_AUTO_FIELD, "生产区域", build_production_area_expr()),
        (BATCH_KEY_FIELD, "批工序键", build_batch_key_expr()),
        (FULL_TRACE_FIELD, "完整追溯号", build_full_trace_expr()),
    ]
    for fid, name, expr in patches:
        print(patch_field(client, fid, name, expr, dry_run))

    if not dry_run:
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
