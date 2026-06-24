#!/usr/bin/env python3
"""Safe index-column (日志编号) display for upstream link pickers.

Why the naive approach breaks:
- Index = 生产批号  → indirect self-chain (index ↔ 生产批号 mirror of 批号文本)
- Index = CONCATENATE(..., 工序代码) → 工序代码 is a link field, not text → #ERROR cascade

Safe index references only:
- fldD86odYI 批号文本 (source batch formula)
- fldLgbv109 工序代码文本 (text mirror of process link)

Manual prerequisite (Feishu UI, once):
1. Add column「日志编号备份」and copy existing 日志编号 values (or keep auto-number there).
2. Then run this script with --apply-safe-index, OR paste SAFE_INDEX_EXPR in UI.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from advance_v4_greenfield import Client
from remediate_v4_formulas import patch_formulas
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"

LOG_NO = "fldGXpl2l5"  # 日志编号 · primary
BATCH_TEXT = "fldD86odYI"  # 批号文本
PROC_TEXT = "fldLgbv109"  # 工序代码文本

REF = f"bitable::$table[{MAIN}]"

# 勿引用 生产批号 fldvMRl868；勿引用 工序代码 fldMxRQhnU（关联类型）
SAFE_INDEX_EXPR = (
    f'IF({REF}.$field[{BATCH_TEXT}]!="",'
    f'CONCATENATE({REF}.$field[{BATCH_TEXT}],"-",{REF}.$field[{PROC_TEXT}]),'
    f'{REF}.$field[{PROC_TEXT}])'
)

AUTO_SERIAL_PROP = {
    "auto_serial": {
        "type": "custom",
        "options": [
            {"type": "created_time", "value": "yyyyMMdd"},
            {"type": "system_number", "value": "3"},
        ],
    }
}


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
        return f"[dry-run] set 日志编号 formula:\n  {SAFE_INDEX_EXPR}"
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


def refresh_batch_formulas(client: Client, dry_run: bool) -> list[str]:
    return patch_formulas(client, dry_run)


def verify_samples(client: Client) -> list[str]:
    import time

    time.sleep(8)
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 20})
    lines: list[str] = []
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        proc = f.get("工序代码文本")
        if isinstance(proc, list) and proc:
            proc = proc[0].get("text")
        batch = f.get("批号文本")
        if isinstance(batch, list) and batch:
            batch = batch[0].get("text")
        log_no = f.get("日志编号")
        if isinstance(log_no, list) and log_no:
            log_no = log_no[0].get("text")
        if batch or (log_no and str(log_no).startswith("S-") or str(log_no).startswith("Z-") or str(log_no).startswith("P-")):
            ok = batch and log_no and str(batch) in str(log_no)
            lines.append(
                f"{'PASS' if ok else 'WARN'} {it['record_id']} 日志编号={log_no!r} 批号={batch!r} 工序={proc!r}"
            )
            if len(lines) >= 5:
                break
    return lines or ["WARN: no sample rows with batch text"]


def run(restore: bool, apply_index: bool, refresh_formulas: bool, dry_run: bool, verify: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_index_column — 索引列安全显示（上道选批）")
    print("-" * 60)
    print("安全索引公式（复制到飞书亦可）：")
    print(SAFE_INDEX_EXPR)
    print("-" * 60)

    if restore:
        print(restore_autonumber(client, dry_run))
    if apply_index:
        print(apply_safe_index(client, dry_run))
    if refresh_formulas:
        print("刷新 批号文本 / 生产批号 / 完整追溯号 等公式：")
        for line in refresh_batch_formulas(client, dry_run):
            print(line)

    if verify and not dry_run and (apply_index or refresh_formulas):
        print("-" * 60)
        for line in verify_samples(client):
            print(line)

    print("-" * 60)
    print("注意：")
    print("  1. 改索引前请先把原自动编号复制到「日志编号备份」列")
    print("  2. 索引公式只用 批号文本 + 工序代码文本，不要用 生产批号 或 工序代码")
    print("  3. 若仍有红叹号：先 --restore-autonumber，再 --refresh-formulas，最后 --apply-safe-index")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Fix production log index column for link picker display")
    p.add_argument("--restore-autonumber", action="store_true", help="把日志编号恢复为自动编号")
    p.add_argument("--apply-safe-index", action="store_true", help="应用安全索引公式到日志编号列")
    p.add_argument("--refresh-formulas", action="store_true", help="重刷批号/追溯公式列")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    args = p.parse_args()
    if not any((args.restore_autonumber, args.apply_safe_index, args.refresh_formulas)):
        p.error("specify at least one of --restore-autonumber, --apply-safe-index, --refresh-formulas")
    try:
        return run(
            args.restore_autonumber,
            args.apply_safe_index,
            args.refresh_formulas,
            args.dry_run,
            verify=not args.no_verify,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
