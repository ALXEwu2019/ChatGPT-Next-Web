#!/usr/bin/env python3
"""Index column (日志编号) for upstream link picker — without breaking batch formulas.

Root cause of #CIRCLE / red errors:
  Primary column must NOT reference other formula fields on the SAME row
  (批号文本 / 生产批号 / 工序代码文本).

Wrong (breaks the table):
  日志编号 = 生产批号
  日志编号 = CONCATENATE(批号文本, "-", 工序代码文本)

Correct:
  Inline the same link-traversal logic as 批号文本 (control/upstream .$column paths),
  plus process code via 工序代码.$column[工序表.工序代码] — never $field[fldD86odYI].
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from advance_v4_greenfield import Client
from remediate_v4_formulas import build_batch_text_expr, patch_formulas
from sync_batch_summary import feishu_credentials_ok, load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
LOG_NO = "fldGXpl2l5"
PROC_LINK = "fldMxRQhnU"
PROC_CODE_COL = "fldpfZYfbH"  # 工序表 · 工序代码（文本）

AUTO_SERIAL_PROP = {
    "auto_serial": {
        "type": "custom",
        "options": [
            {"type": "created_time", "value": "yyyyMMdd"},
            {"type": "system_number", "value": "3"},
        ],
    }
}


def build_safe_index_expr() -> str:
    """批号链路内联 + 工序代码（走关联列，不引用本行公式列）。"""
    batch_inner = build_batch_text_expr()[len("CONCATENATE(") : -1]
    proc = f"bitable::$table[{MAIN}].$field[{PROC_LINK}].$column[{PROC_CODE_COL}]"
    return f'CONCATENATE({batch_inner},"-",{proc})'


SAFE_INDEX_EXPR = build_safe_index_expr()


def get_field(client: Client, field_id: str) -> dict | None:
    for f in client.list_fields(MAIN):
        if f["field_id"] == field_id:
            return f
    return None


def apply_safe_index(client: Client, dry_run: bool) -> str:
    f = get_field(client, LOG_NO)
    if not f:
        return "FAIL: 日志编号 field missing"
    if dry_run:
        return f"[dry-run] set 日志编号 formula (len={len(SAFE_INDEX_EXPR)})"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{LOG_NO}",
        json={
            "field_name": "日志编号",
            "type": 20,
            "property": {"formula_expression": SAFE_INDEX_EXPR},
        },
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: 日志编号 index formula — {resp.get('msg', '')}"


def restore_autonumber(client: Client, dry_run: bool) -> str:
    f = get_field(client, LOG_NO)
    if not f:
        return "FAIL: 日志编号 field missing"
    if f.get("type") == 1005:
        return "skip: 日志编号 already auto-number"
    if dry_run:
        return "[dry-run] restore 日志编号 as auto-number (type 1005)"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{LOG_NO}",
        json={"field_name": "日志编号", "type": 1005, "property": AUTO_SERIAL_PROP},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'}: restore auto-number — {resp.get('msg', '')}"


def verify_samples(client: Client) -> list[str]:
    import time

    time.sleep(10)
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 30})

    def t(v):
        if v is None:
            return None
        if isinstance(v, list) and v:
            if isinstance(v[0], dict):
                return v[0].get("text")
            return v[0]
        return v

    lines: list[str] = []
    ok_n = fail_n = 0
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        batch = t(f.get("批号文本"))
        prod_batch = t(f.get("生产批号"))
        log_no = t(f.get("日志编号"))
        trace = t(f.get("完整追溯号"))
        proc = t(f.get("工序代码"))
        if not batch and not prod_batch:
            continue
        ok = batch == prod_batch and batch is not None
        if ok:
            ok_n += 1
        else:
            fail_n += 1
        if len(lines) < 6:
            lines.append(
                f"{'PASS' if ok else 'FAIL'} {proc} 批号={batch!r} 生产批号={prod_batch!r} "
                f"日志编号={log_no!r} 追溯={trace!r}"
            )
    lines.append(f"summary: {ok_n} ok, {fail_n} fail (rows with batch)")
    return lines


def run(restore: bool, apply_index: bool, refresh_formulas: bool, dry_run: bool, verify: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    if not feishu_credentials_ok(cfg):
        print("ERROR: 请配置飞书凭证")
        return 1
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_index_column — 修复索引列 / 批号公式红叹号")
    print("-" * 60)
    print(f"安全索引公式长度: {len(SAFE_INDEX_EXPR)} 字符")
    print("规则: 索引列只走关联字段 .$column 路径，不引用本行 批号文本/生产批号")
    print("-" * 60)

    if restore:
        print(restore_autonumber(client, dry_run))
    if refresh_formulas:
        print("刷新 批号文本 / 生产批号 / 完整追溯号 等公式：")
        for line in patch_formulas(client, dry_run):
            print(line)
    if apply_index:
        print(apply_safe_index(client, dry_run))

    if verify and not dry_run:
        print("-" * 60)
        for line in verify_samples(client):
            print(line)

    print("-" * 60)
    print("推荐恢复顺序（若整表红叹号）：")
    print("  1. python3 remediate_index_column.py --restore-autonumber --refresh-formulas")
    print("  2. 浏览器强刷页面，确认 批号文本 已恢复")
    print("  3. 上道选批请用表单「上道批号 + 生产批号只读」，勿再把首列改成公式")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--restore-autonumber", action="store_true")
    p.add_argument(
        "--apply-safe-index",
        action="store_true",
        help="已禁用：本表首列改公式会打垮批号/追溯公式，请勿使用",
    )
    p.add_argument("--refresh-formulas", action="store_true")
    p.add_argument("--fix-all", action="store_true", help="= --restore-autonumber --refresh-formulas")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    args = p.parse_args()
    if args.fix_all:
        args.restore_autonumber = True
        args.refresh_formulas = True
    if args.apply_safe_index:
        print("ERROR: --apply-safe-index 已禁用。本表批号为复杂公式链，首列改公式会导致整表计算失败。")
        print("请使用表单：上道批号（选记录）+ 生产批号（只读核对）。")
        return 1
    if not any((args.restore_autonumber, args.refresh_formulas)):
        p.error("specify --fix-all or --restore-autonumber / --refresh-formulas")
    return run(
        args.restore_autonumber,
        False,
        args.refresh_formulas,
        args.dry_run,
        verify=not args.no_verify,
    )


if __name__ == "__main__":
    sys.exit(main())
