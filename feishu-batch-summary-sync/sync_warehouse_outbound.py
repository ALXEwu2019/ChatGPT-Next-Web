#!/usr/bin/env python3
"""仓库出库：扫描主表末道待出库行，可自动登记出入库流水。

逻辑：
  待出库 = 工序 #70/#80/#50 + 已确认/已审核 + 出库数量>0 + 主表未关联仓库流水

用法:
  python3 sync_warehouse_outbound.py --audit
  python3 sync_warehouse_outbound.py --auto-outbound --dry-run
  python3 sync_warehouse_outbound.py --auto-outbound
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

from fix_2026_warehouse_table import WH, list_pending_outbound
from remediate_2026_summary import APP, Client, load_2026_config

OUTBOUND_TYPE = "出库"


def create_outbound_row(client: Client, main_id: str, qty: float, dry_run: bool) -> str:
    if dry_run:
        return f"dry-wh-{main_id}"
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{WH}/records",
        json={
            "fields": {
                "流水类型": OUTBOUND_TYPE,
                "关联生产记录": [main_id],
                "数量": qty,
                "出入库时间": now_ms,
            }
        },
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create warehouse row: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def run(audit: bool, auto: bool, dry_run: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    pending = list_pending_outbound(client)

    print("sync_warehouse_outbound")
    print("=" * 60)
    print(f"待出库 {len(pending)} 行")
    for row in pending:
        print(f"  {row['batch']} {row['proc']} 应出={row['out_qty']} main={row['record_id']}")

    if audit and not auto:
        print("=" * 60)
        return 0

    created = 0
    for row in pending:
        rid = create_outbound_row(client, row["record_id"], float(row["out_qty"]), dry_run)
        print(f"  {'[dry-run]' if dry_run else 'created'} {row['batch']} → {rid}")
        created += 1

    if not dry_run and created:
        time.sleep(8)
        wh_rows = client.list_records(WH)
        print(f"仓库表现有 {len(wh_rows)} 行")

    print("=" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--audit", action="store_true", help="仅列出待出库")
    p.add_argument("--auto-outbound", action="store_true", help="自动创建出库流水")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not args.audit and not args.auto_outbound:
        p.error("specify --audit or --auto-outbound")
    try:
        return run(args.audit, args.auto_outbound, args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
