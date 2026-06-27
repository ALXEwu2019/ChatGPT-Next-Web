#!/usr/bin/env python3
"""2026 生产 Base 全面优化编排（阶段 C/D/E + 汇总 sync）。

步骤：
  1. configure_production_p1 — 管控回填、隐藏横向区域列、已确认选项
  2. remediate_production_base — 删禁止字段、8 报工视图列收敛
  3. 主表 已报工 → 已确认（有批号+产量）
  4. sync_batch_summary — 写入汇总表
  5. 验收 audit

用法：
  python3 remediate_2026_comprehensive.py --dry-run
  python3 remediate_2026_comprehensive.py --fix-all
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from remediate_2026_summary import APP, MAIN_TABLE, Client, audit, load_2026_config
from sync_batch_summary import extract_text, run_sync

REPO = Path(__file__).resolve().parent


def bulk_confirm_reported(client: Client, dry_run: bool) -> list[str]:
    """将有效报工行从 已报工 改为 已确认，供汇总脚本聚合。"""
    lines: list[str] = []
    records = client.list_records(MAIN_TABLE)
    updates: list[dict] = []
    for row in records:
        f = row.get("fields", {})
        status = extract_text(f.get("工序下发状态"))
        if status != "已报工":
            continue
        batch = extract_text(f.get("批号文本")) or extract_text(f.get("生产批号"))
        vq = f.get("有效合格数量")
        if not batch:
            continue
        if vq in (None, ""):
            continue
        updates.append(
            {
                "record_id": row["record_id"],
                "fields": {"工序下发状态": "已确认"},
            }
        )
    if not updates:
        return ["skip: 无待确认已报工行"]
    if dry_run:
        return [f"[dry-run] confirm {len(updates)} rows 已报工→已确认"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/batch_update",
        json={"records": updates},
    )
    ok = resp.get("code") == 0
    return [f"{'confirmed' if ok else 'FAIL'} {len(updates)} rows — {resp.get('msg', '')}"]


def run_subprocess(script: str, *extra: str, dry_run: bool = False) -> int:
    cmd = [sys.executable, str(REPO / script)]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend(extra)
    print(f"\n## {script}")
    print("-" * 60)
    result = subprocess.run(cmd, cwd=REPO)
    return result.returncode


def run(
    dry_run: bool,
    skip_p1: bool,
    skip_main: bool,
    skip_confirm: bool,
    skip_sync: bool,
) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_2026_comprehensive — 2026 生产 Base 全面优化")
    print(f"App {APP}")
    print("=" * 60)

    if not skip_p1:
        rc = run_subprocess("configure_production_p1.py", dry_run=dry_run)
        if rc != 0:
            return rc
        rc = run_subprocess("fix_2026_process_formulas.py", dry_run=dry_run)
        if rc != 0:
            return rc

    if not skip_main:
        rc = run_subprocess("remediate_production_base.py", dry_run=dry_run)
        if rc != 0:
            return rc

    if not skip_confirm:
        print("\n## 主表品保确认（已报工→已确认）")
        print("-" * 60)
        for line in bulk_confirm_reported(client, dry_run):
            print(line)

    if not skip_sync and not dry_run:
        print("\n## sync_batch_summary")
        print("-" * 60)
        rows = run_sync(cfg, dry_run=False)
        print(f"聚合写入 {len(rows)} 行")

    print("\n## 汇总表验收")
    print("-" * 60)
    for line in audit(client):
        print(line)

    print("=" * 60)
    print("手工剩余：")
    print("  · 管控表「合格合计」查找引用（docs/feishu-lookup-qualified-total-cn.md）")
    print("  · 8 报工视图关联筛选（docs/feishu-p1-manual-setup-2026-cn.md）")
    print("  · cron: sync_batch_summary.py --config config.2026.json")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="2026 production base comprehensive remediation")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix-all", action="store_true")
    p.add_argument("--skip-p1", action="store_true")
    p.add_argument("--skip-main", action="store_true")
    p.add_argument("--skip-confirm", action="store_true")
    p.add_argument("--skip-sync", action="store_true")
    args = p.parse_args()
    if not args.fix_all and not args.dry_run:
        p.error("specify --fix-all or --dry-run")
    try:
        return run(
            args.dry_run,
            skip_p1=args.skip_p1,
            skip_main=args.skip_main,
            skip_confirm=args.skip_confirm,
            skip_sync=args.skip_sync,
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
