#!/usr/bin/env python3
"""2026 生产 Base P0 阻断修复。

1. 工序下发状态补「已确认」
2. 批号文本公式改引用 生产批号-手动输入栏（回退关联管控批_*）
3. 误链汇总/管控的上道批号字段 delete+recreate → 主表
4. 已报工且有批号+产量 → 已确认
5. 汇总表 sync

用法:
  python3 remediate_2026_p0.py --dry-run
  python3 remediate_2026_p0.py --fix-all
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, audit, load_2026_config
from sync_batch_summary import extract_text, run_sync

CTRL_TABLE = "tblyvJJhyq5KoT4F"
SUM_TABLE = "tblXonlkdLxrTLXE"

BATCH_TEXT_FIELD = "fldn9YCUgm"
MANUAL_BATCH_FIELD = "fldZXaX1dj"
LEGACY_CTRL_LINK = "fldQSSF2kt"
CTRL_BATCH_TEXT_COL = "fldTG0SeXm"
CTRL_STOPPER_2030 = "fldQ7m86rl"
CTRL_ZDK_4050 = "fldL9IMguv"

UPSTREAM_FIELDS = (
    "上道批号_STOPPER#4050",
    "上道批号_STOPPER#60",
    "上道批号_止动块#60",
    "上道批号_止动块#70",
    "上道批号_止动块#80",
    "上道批号_PTJ92#3040",
    "上道批号_PTJ92#50",
)


def build_batch_text_expr() -> str:
    """优先 生产批号-手动输入栏，其次 per-view 管控字段，最后 关联管控批次。"""
    main = MAIN_TABLE
    return (
        f"IF(NOT(ISBLANK(bitable::$table[{main}].$field[{MANUAL_BATCH_FIELD}])),"
        f"bitable::$table[{main}].$field[{MANUAL_BATCH_FIELD}].$column[{CTRL_BATCH_TEXT_COL}],"
        f"IF(NOT(ISBLANK(bitable::$table[{main}].$field[{CTRL_STOPPER_2030}])),"
        f"bitable::$table[{main}].$field[{CTRL_STOPPER_2030}].$column[{CTRL_BATCH_TEXT_COL}],"
        f"IF(NOT(ISBLANK(bitable::$table[{main}].$field[{CTRL_ZDK_4050}])),"
        f"bitable::$table[{main}].$field[{CTRL_ZDK_4050}].$column[{CTRL_BATCH_TEXT_COL}],"
        f"IF(NOT(ISBLANK(bitable::$table[{main}].$field[{LEGACY_CTRL_LINK}])),"
        f"bitable::$table[{main}].$field[{LEGACY_CTRL_LINK}].$column[{CTRL_BATCH_TEXT_COL}],"
        f'""))))'
    )


def add_status_confirmed(client: Client, dry_run: bool) -> list[str]:
    fields = client.list_fields(MAIN_TABLE)
    status = next(f for f in fields if f["field_name"] == "工序下发状态")
    opts = [o["name"] for o in status.get("property", {}).get("options", [])]
    if "已确认" in opts:
        return ["skip: 已确认选项已存在"]
    if dry_run:
        return ["[dry-run] add 已确认 to 工序下发状态"]
    options = list(status.get("property", {}).get("options", []))
    options.append({"name": "已确认", "color": 0})
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{status['field_id']}",
        json={
            "field_name": status["field_name"],
            "type": status["type"],
            "property": {"options": options},
        },
    )
    ok = resp.get("code") == 0
    return [f"{'ok' if ok else 'FAIL'}: 已确认选项 — {resp.get('msg', '')}"]


def patch_batch_text_formula(client: Client, dry_run: bool) -> list[str]:
    expr = build_batch_text_expr()
    if dry_run:
        return [f"[dry-run] patch 批号文本 formula (len={len(expr)})"]
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{BATCH_TEXT_FIELD}",
        json={
            "field_name": "批号文本",
            "type": 20,
            "property": {"formula_expression": expr},
        },
    )
    return [f"{'ok' if resp.get('code')==0 else 'FAIL'}: 批号文本 — {resp.get('msg','')}"]


def recreate_upstream_link(client: Client, name: str, dry_run: bool) -> str:
    fields = client.list_fields(MAIN_TABLE)
    existing = next((f for f in fields if f["field_name"] == name), None)
    if not existing:
        if dry_run:
            return f"[dry-run] create {name} → MAIN"
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields",
            json={
                "field_name": name,
                "type": 18,
                "property": {"table_id": MAIN_TABLE, "multiple": False},
            },
        )
        return f"{'created' if resp.get('code')==0 else 'FAIL'}: {name} — {resp.get('msg','')}"

    tgt = (existing.get("property") or {}).get("table_id")
    if tgt == MAIN_TABLE:
        return f"skip ok: {name} → MAIN"

    if dry_run:
        return f"[dry-run] recreate {name} ({tgt} → {MAIN_TABLE})"

    fid = existing["field_id"]
    for attempt in range(3):
        del_resp = client.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{fid}")
        if del_resp.get("code") == 0:
            break
        if attempt < 2:
            time.sleep(3)
    if del_resp.get("code") != 0:
        return f"FAIL delete {name}: {del_resp.get('msg', '')}"
    time.sleep(0.5)
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields",
        json={
            "field_name": name,
            "type": 18,
            "property": {"table_id": MAIN_TABLE, "multiple": False},
        },
    )
    new_id = resp.get("data", {}).get("field", {}).get("field_id", "?")
    return f"recreated: {name} ({fid}→{new_id})"


def fix_upstream_fields(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for name in UPSTREAM_FIELDS:
        lines.append(recreate_upstream_link(client, name, dry_run))
    return lines


def backfill_control_batch_text(client: Client, dry_run: bool) -> list[str]:
    updates: list[dict] = []
    for row in client.list_records(CTRL_TABLE):
        f = row.get("fields", {})
        bt = extract_text(f.get("批号文本"))
        bn = extract_text(f.get("批次号"))
        if not bt and bn:
            updates.append({"record_id": row["record_id"], "fields": {"批号文本": bn}})
    if not updates:
        return ["skip: 管控表批号文本已齐"]
    if dry_run:
        return [f"[dry-run] backfill 管控批号文本 {len(updates)} 行"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/records/batch_update",
        json={"records": updates},
    )
    ok = resp.get("code") == 0
    return [f"{'ok' if ok else 'FAIL'}: 管控批号文本回填 {len(updates)} 行 — {resp.get('msg', '')}"]


def wait_formulas(seconds: int = 10) -> None:
    if seconds > 0:
        print(f"  (等待公式重算 {seconds}s…)")

        time.sleep(seconds)


def bulk_confirm_reported(client: Client, dry_run: bool) -> list[str]:
    records = client.list_records(MAIN_TABLE)
    updates: list[dict] = []
    for row in records:
        f = row.get("fields", {})
        if extract_text(f.get("工序下发状态")) != "已报工":
            continue
        batch = extract_text(f.get("批号文本"))
        if not batch:
            manual = f.get("生产批号-手动输入栏")
            if isinstance(manual, list) and manual and manual[0].get("text"):
                batch = manual[0]["text"]
            elif isinstance(manual, list) and manual and manual[0].get("text_arr"):
                batch = (manual[0].get("text_arr") or [""])[0]
        if not batch:
            continue
        vq = f.get("有效合格数量")
        if vq in (None, ""):
            continue
        updates.append({"record_id": row["record_id"], "fields": {"工序下发状态": "已确认"}})

    if not updates:
        return ["skip: 无符合条件的已报工行"]
    if dry_run:
        return [f"[dry-run] 已报工→已确认 {len(updates)} 行"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/batch_update",
        json={"records": updates},
    )
    ok = resp.get("code") == 0
    return [f"{'confirmed' if ok else 'FAIL'} {len(updates)} rows — {resp.get('msg', '')}"]


def verify_p0(client: Client) -> list[str]:
    fields = {f["field_name"]: f for f in client.list_fields(MAIN_TABLE)}
    lines: list[str] = []

    st = fields.get("工序下发状态", {})
    opts = [o["name"] for o in (st.get("property") or {}).get("options", [])]
    lines.append(f"{'PASS' if '已确认' in opts else 'FAIL'}: 已确认状态选项")

    wrong = [
        n
        for n in UPSTREAM_FIELDS
        if (fields.get(n, {}).get("property") or {}).get("table_id") not in (None, MAIN_TABLE)
    ]
    lines.append(f"{'PASS' if not wrong else 'FAIL'}: 上道批号关联主表 ({wrong or '全部正确'})")

    recs = client.list_records(MAIN_TABLE)
    bt_ok = sum(1 for r in recs if extract_text(r["fields"].get("批号文本")))
    lines.append(f"{'PASS' if bt_ok > len(recs)//2 else 'FAIL'}: 批号文本非空 {bt_ok}/{len(recs)}")

    confirmed = sum(
        1
        for r in recs
        if extract_text(r["fields"].get("工序下发状态")) in ("已确认", "已审核")
    )
    lines.append(f"{'PASS' if confirmed > 0 else 'FAIL'}: 可汇总行 {confirmed}/{len(recs)}")

    return lines


def run(dry_run: bool, skip_sync: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_2026_p0 — P0 阻断修复")
    print(f"App {APP}")
    print("=" * 60)

    steps = [
        ("1. 补已确认状态", lambda: add_status_confirmed(client, dry_run)),
        ("2. 修批号文本公式", lambda: patch_batch_text_formula(client, dry_run)),
        ("3. 管控批号文本回填", lambda: backfill_control_batch_text(client, dry_run)),
        ("4. 重建上道批号关联", lambda: fix_upstream_fields(client, dry_run)),
    ]
    for title, fn in steps:
        print(f"\n## {title}")
        for line in fn():
            print(line)

    if not dry_run:
        wait_formulas(12)

    print("\n## 5. 已报工→已确认")
    for line in bulk_confirm_reported(client, dry_run):
        print(line)

    if not dry_run and not skip_sync:
        print("\n## 6. sync_batch_summary")
        rows = run_sync(cfg, dry_run=False)
        print(f"聚合写入 {len(rows)} 行")

        print("\n## 7. 汇总表验收")
        for line in audit(client):
            print(line)

    print("\n## P0 验收")
    if not dry_run:
        for line in verify_p0(client):
            print(line)
    else:
        print("(dry-run 跳过线上验收)")

    print("=" * 60)
    print("P1 仍需手工：8 报工 form 关联筛选、管控表合格合计查找")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="2026 production base P0 remediation")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix-all", action="store_true")
    p.add_argument("--skip-sync", action="store_true")
    args = p.parse_args()
    if not args.fix_all and not args.dry_run:
        p.error("specify --fix-all or --dry-run")
    try:
        return run(args.dry_run, args.skip_sync)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
