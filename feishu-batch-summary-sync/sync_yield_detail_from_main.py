#!/usr/bin/env python3
"""从生产日志主表回填报工产量明细（合格/报废分行）。

规则：
  - 每条主表报工 → 按区域拆 合格行 + 报废行（数量>0）
  - 生产区域优先从批工序键后缀解析，回退主表 per-view 区域列
  - 已存在同报工头+区域+类型则跳过

用法:
  python3 sync_yield_detail_from_main.py --audit
  python3 sync_yield_detail_from_main.py --backfill --dry-run
  python3 sync_yield_detail_from_main.py --backfill
  python3 sync_yield_detail_from_main.py --validate
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict

from remediate_2026_summary import APP, Client, MAIN_TABLE, load_2026_config
from sync_batch_summary import extract_number, extract_text

DETAIL = "tblheKbZ7R9LxtvF"

REGION_FIELDS = {
    "#2030": ("#2030STOPPER-生产区域A", "#2030STOPPER-生产区域B", "#2030STOPPER-生产区域C"),
    "#4050": ("#4050STOPPER-生产区域_输入",),
    "#60": ("#60检查机-生产区域_输入",),
    "#1020": ("#1020PTJ92 -生产区域_输入",),
}


def region_from_main(fields: dict) -> str:
    key = extract_text(fields.get("批工序键"))
    proc = extract_text(fields.get("工序代码"))
    if key and proc and f"-{proc}-" in key:
        return key.split(f"-{proc}-", 1)[1]
    if proc in REGION_FIELDS:
        for fname in REGION_FIELDS[proc]:
            val = extract_text(fields.get(fname))
            if val:
                return val
    return extract_text(fields.get("生产区域")) or ""


def existing_keys(client: Client) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for row in client.list_records(DETAIL):
        f = row.get("fields", {})
        link = f.get("关联报工头")
        if not link or not isinstance(link, list) or not link[0].get("record_ids"):
            continue
        main_id = link[0]["record_ids"][0]
        region = extract_text(f.get("生产区域")) or ""
        ytype = extract_text(f.get("报工类型")) or ""
        keys.add((main_id, region, ytype))
    return keys


def plan_rows(client: Client) -> list[dict]:
    have = existing_keys(client)
    planned: list[dict] = []
    for row in client.list_records(MAIN_TABLE):
        f = row.get("fields", {})
        main_id = row["record_id"]
        region = region_from_main(f)
        for ytype, qty_field in (("合格", "良品数量"), ("报废", "报废数量")):
            qty = extract_number(f.get(qty_field)) or 0
            if qty <= 0:
                continue
            key = (main_id, region, ytype)
            if key in have:
                continue
            planned.append(
                {
                    "main_id": main_id,
                    "batch": extract_text(f.get("批号文本")),
                    "proc": extract_text(f.get("工序代码")),
                    "region": region,
                    "ytype": ytype,
                    "qty": qty,
                }
            )
    return planned


def backfill(client: Client, dry_run: bool) -> list[str]:
    planned = plan_rows(client)
    lines = [f"拟写入 {len(planned)} 行明细"]
    if dry_run:
        for p in planned[:10]:
            lines.append(
                f"  {p['batch']} {p['proc']} {p['region']} {p['ytype']}={p['qty']}"
            )
        return lines

    created = 0
    for p in planned:
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{DETAIL}/records",
            json={
                "fields": {
                    "关联报工头": [p["main_id"]],
                    "生产区域": p["region"],
                    "报工类型": p["ytype"],
                    "数量": p["qty"],
                }
            },
        )
        if resp.get("code") != 0:
            lines.append(f"FAIL {p['batch']}: {resp.get('msg')}")
            continue
        created += 1
    lines.append(f"ok: created {created} detail rows")
    return lines


def validate(client: Client) -> list[str]:
    detail_sum: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: {"合格": 0.0, "报废": 0.0})
    for row in client.list_records(DETAIL):
        f = row.get("fields", {})
        link = f.get("关联报工头")
        if not link or not isinstance(link, list) or not link[0].get("record_ids"):
            continue
        main_id = link[0]["record_ids"][0]
        region = extract_text(f.get("生产区域")) or ""
        ytype = extract_text(f.get("报工类型")) or ""
        qty = extract_number(f.get("数量")) or 0
        if ytype in ("合格", "报废"):
            detail_sum[(main_id, region)][ytype] += qty

    lines: list[str] = []
    mismatches = 0
    for row in client.list_records(MAIN_TABLE):
        f = row.get("fields", {})
        main_id = row["record_id"]
        region = region_from_main(f)
        ok_main = extract_number(f.get("良品数量")) or 0
        scrap_main = extract_number(f.get("报废数量")) or 0
        if ok_main == 0 and scrap_main == 0:
            continue
        got = detail_sum.get((main_id, region), {"合格": 0.0, "报废": 0.0})
        match = got["合格"] == ok_main and got["报废"] == scrap_main
        if not match:
            mismatches += 1
            lines.append(
                f"FAIL {extract_text(f.get('批号文本'))} {extract_text(f.get('工序代码'))} {region}: "
                f"主表 {ok_main}/{scrap_main} 明细 {got['合格']}/{got['报废']}"
            )
    if mismatches == 0:
        lines.append("PASS: 主表良品/报废与明细合计一致")
    else:
        lines.append(f"合计 {mismatches} 行不一致")
    return lines


def run(audit: bool, backfill_flag: bool, validate_flag: bool, dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("sync_yield_detail_from_main")
    print("=" * 60)

    planned = plan_rows(client)
    print(f"主表可拆分明细: {len(planned)} 行（已存在则跳过）")
    for p in planned[:12]:
        print(f"  {p['batch']} {p['proc']} {p['region']} {p['ytype']}={p['qty']}")

    if audit and not backfill_flag and not validate_flag:
        print("=" * 60)
        return 0

    if backfill_flag:
        for line in backfill(client, dry_run):
            if line:
                print(line)
        if not dry_run:
            time.sleep(10)

    if validate_flag or backfill_flag:
        print("\n## 对账")
        for line in validate(client):
            print(line)

    print("=" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--audit", action="store_true")
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.audit and not args.backfill and not args.validate:
        p.error("specify --audit, --backfill, or --validate")
    try:
        return run(args.audit, args.backfill, args.validate, args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
