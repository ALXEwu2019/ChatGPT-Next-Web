#!/usr/bin/env python3
"""Seed and verify end-to-end workflow: operator → defect → leader → QA for 3 products."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from advance_v4_greenfield import Client
from process_registry import (
    CHAINS,
    FIRST_CTRL_FIELD,
    PROD,
    UPSTREAM_FIELD,
    proc_id,
    upstream_code,
)
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"
DEFECT = "tblMtQ4aEwlzuhWs"
REASON = "tblvX8KSv73TluVk"

BATCH = {
    "STOPPER": "S-WF-E2E",
    "ZHIDONG": "Z-WF-E2E",
    "PTJ92": "P-WF-E2E",
}

# 各产品首道 / 下道填报字段
REGION_BY_CODE = {
    "#2030": "A1",
    "#4050": "MG02",
    "#60": None,
    "#70": None,
    "#80": None,
    "#1020": None,
    "#3040": None,
    "#50": None,
}
STATION_BY_CODE = {"#60": "J1", "#1020": "J1"}


def extract_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        if isinstance(value[0], dict):
            return value[0].get("text")
        return str(value[0])
    return str(value) if value != "" else None


def find_control(client: Client, batch_text: str) -> str | None:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{CTRL}/records", params={"page_size": 500})
    for it in data.get("data", {}).get("items", []):
        if extract_text(it.get("fields", {}).get("批号文本")) == batch_text:
            return it["record_id"]
    return None


def ensure_control(
    client: Client,
    batch_text: str,
    product: str,
    proc_code: str,
    dry_run: bool,
) -> str | None:
    existing = find_control(client, batch_text)
    if existing:
        return existing
    row = {
        "fields": {
            "批号文本": batch_text,
            "产品": [PROD[product]],
            "工序代码": [proc_id(product, proc_code)],
            "状态": "已下发",
            "本工序下发数量": 500,
        }
    }
    if dry_run:
        return f"dry-{batch_text}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{CTRL}/records", json=row)
    if resp.get("code") != 0:
        raise RuntimeError(f"create control {batch_text}: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def first_reason(client: Client, disposition: str) -> str:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{REASON}/records", params={"page_size": 50})
    for it in data.get("data", {}).get("items", []):
        if it.get("fields", {}).get("处置类型") == disposition:
            return it["record_id"]
    raise RuntimeError(f"no defect reason with 处置类型={disposition}")


def create_report(
    client: Client,
    *,
    product: str,
    proc_code: str,
    control_id: str | None = None,
    control_field: str | None = None,
    upstream_id: str | None = None,
    upstream_field: str | None = None,
    region: str | None = None,
    station: str | None = None,
    ok_qty: int,
    scrap_qty: int,
    dry_run: bool,
) -> str | None:
    fields: dict = {
        "产品": [PROD[product]],
        "工序代码": [proc_id(product, proc_code)],
        "合格数量": ok_qty,
        "报废数量": scrap_qty,
        "工序下发状态": "已报工",
    }
    if control_id and control_field:
        fields[control_field] = [control_id]
    if upstream_id and upstream_field:
        fields[upstream_field] = [upstream_id]
    if region:
        fields["生产区域"] = region
    if station:
        fields["工位代码"] = station
    if dry_run:
        return f"dry-report-{product}-{proc_code}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", json={"fields": fields})
    if resp.get("code") != 0:
        raise RuntimeError(f"create report {product}{proc_code}: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def patch_main(client: Client, record_id: str, fields: dict, dry_run: bool) -> None:
    if dry_run:
        return
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/records/{record_id}",
        json={"fields": fields},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"patch main {record_id}: {resp.get('msg')}")


def create_defect(
    client: Client,
    main_id: str,
    qty: int,
    reason_id: str,
    disposition: str,
    dry_run: bool,
) -> str | None:
    row = {
        "fields": {
            "关联生产记录": [main_id],
            "不良数量": qty,
            "不良原因": [reason_id],
            "处置类型": disposition,
            "状态": "待返工",
        }
    }
    if dry_run:
        return f"dry-defect-{main_id}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{DEFECT}/records", json=row)
    if resp.get("code") != 0:
        raise RuntimeError(f"create defect: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def get_main_fields(client: Client, record_id: str) -> dict:
    resp = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records/{record_id}")
    return resp.get("data", {}).get("record", {}).get("fields", {})


def run_defect_chain(
    client: Client,
    main_id: str,
    *,
    rework_ok: int,
    rework_scrap: int,
    dry_run: bool,
) -> list[str]:
    lines: list[str] = []
    patch_main(client, main_id, {"工序下发状态": "待返工"}, dry_run)
    lines.append("1 品保记不良 → 主表 待返工")
    patch_main(
        client,
        main_id,
        {
            "返工后合格数": rework_ok,
            "返工后报废数": rework_scrap,
            "工序下发状态": "待品保确认",
        },
        dry_run,
    )
    lines.append(f"2 班组长回填 返工合格={rework_ok} 返工报废={rework_scrap} → 待品保确认")
    patch_main(client, main_id, {"工序下发状态": "已确认"}, dry_run)
    lines.append("3 品保确认 → 已确认")
    return lines


def verify_main(client: Client, record_id: str, expect: dict) -> list[str]:
    time.sleep(6)
    f = get_main_fields(client, record_id)
    lines: list[str] = []
    for key, val in expect.items():
        got = f.get(key)
        if key in ("批号文本", "生产批号", "工序代码"):
            got = extract_text(got)
        ok = got == val
        lines.append(f"{'PASS' if ok else 'FAIL'} {key}={got!r} 期望={val!r}")
    return lines


def seed_product_chain(
    client: Client,
    product: str,
    *,
    ctrl_id: str | None,
    with_defect_on_first: bool,
    reason_rw: str | None,
    dry_run: bool,
) -> dict[str, str]:
    """沿 CHAINS[product] 逐道报工并确认，返回 {工序代码: record_id}。"""
    chain = CHAINS[product]
    batch = BATCH[product]
    ids: dict[str, str] = {}
    prev_id: str | None = None

    for i, code in enumerate(chain):
        is_first = upstream_code(product, code) is None
        ctrl_field = FIRST_CTRL_FIELD.get((product, code)) if is_first else None
        up_field = UPSTREAM_FIELD.get((product, code)) if not is_first else None
        region = REGION_BY_CODE.get(code) if code in ("#2030", "#4050") else None
        station = STATION_BY_CODE.get(code)

        rid = create_report(
            client,
            product=product,
            proc_code=code,
            control_id=ctrl_id if is_first else None,
            control_field=ctrl_field,
            upstream_id=prev_id,
            upstream_field=up_field,
            region=region,
            station=station,
            ok_qty=100 - i * 5,
            scrap_qty=2,
            dry_run=dry_run,
        )
        if not rid:
            continue
        ids[code] = rid
        print(f"  {product} {code} 报工 {rid}")

        if with_defect_on_first and i == 0 and reason_rw and not dry_run:
            create_defect(client, rid, 5, reason_rw, "返工", dry_run)
            for line in run_defect_chain(client, rid, rework_ok=90, rework_scrap=10, dry_run=dry_run):
                print(f"    {line}")
        elif not dry_run:
            patch_main(client, rid, {"工序下发状态": "已确认"}, dry_run)
            print(f"    → 已确认")

        prev_id = rid if not dry_run else f"dry-prev-{code}"

    if not dry_run and ids:
        last_code = chain[-1]
        last_id = ids[last_code]
        print(f"  验收 {product} 末道 {last_code}:")
        for line in verify_main(
            client,
            last_id,
            {
                "工序下发状态": "已确认",
                "批号文本": batch,
                "工序代码": last_code,
            },
        ):
            print(f"    {line}")

    return ids


def run(dry_run: bool, full_chain: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("seed_workflow_e2e — 三产品报工 + 返工报废闭环")
    print("-" * 60)

    first_codes = {p: CHAINS[p][0] for p in CHAINS}
    ctrl_s = ensure_control(client, BATCH["STOPPER"], "STOPPER", first_codes["STOPPER"], dry_run)
    ctrl_z = ensure_control(client, BATCH["ZHIDONG"], "ZHIDONG", first_codes["ZHIDONG"], dry_run)
    ctrl_p = ensure_control(client, BATCH["PTJ92"], "PTJ92", first_codes["PTJ92"], dry_run)
    print(f"管控批 STOPPER={ctrl_s} 止动块={ctrl_z} PTJ92={ctrl_p}")

    reason_rw = first_reason(client, "返工") if not dry_run else None

    if full_chain:
        print("\n全链跑通（STOPPER 4道 / 止动块 5道 / PTJ92 3道）")
        seed_product_chain(
            client, "STOPPER", ctrl_id=ctrl_s if not dry_run else None,
            with_defect_on_first=True, reason_rw=reason_rw, dry_run=dry_run,
        )
        seed_product_chain(
            client, "ZHIDONG", ctrl_id=ctrl_z if not dry_run else None,
            with_defect_on_first=False, reason_rw=None, dry_run=dry_run,
        )
        seed_product_chain(
            client, "PTJ92", ctrl_id=ctrl_p if not dry_run else None,
            with_defect_on_first=False, reason_rw=None, dry_run=dry_run,
        )
    else:
        # 兼容旧模式：仅首道 + 单步下道示例
        stopper_id = create_report(
            client,
            product="STOPPER",
            proc_code="#2030",
            control_id=ctrl_s if not dry_run else None,
            control_field="关联管控批_STOPPER#2030",
            region="A1",
            ok_qty=100,
            scrap_qty=5,
            dry_run=dry_run,
        )
        print(f"STOPPER #2030 报工 {stopper_id}")
        if not dry_run and stopper_id and reason_rw:
            create_defect(client, stopper_id, 5, reason_rw, "返工", dry_run)
            for line in run_defect_chain(client, stopper_id, rework_ok=90, rework_scrap=10, dry_run=dry_run):
                print(f"  {line}")

    if not dry_run:
        from sync_batch_summary import run_sync

        rows = run_sync(cfg, dry_run=False)
        print(f"\nsync: {len(rows)} summary rows")

    print("-" * 60)
    print("流程说明：")
    print("  操作工 → 各产品报工视图填单（首道选管控批，下道选上道已确认批）")
    print("  品保   → 品保·不良填报（关联报工记录）")
    print("  班组长 → 班组长·返工回填（主表 待返工）")
    print("  品保   → 品保·待确认（改 已确认）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--full-chain", action="store_true", help="三产品全工序链报工验收")
    args = p.parse_args()
    try:
        return run(args.dry_run, args.full_chain)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
