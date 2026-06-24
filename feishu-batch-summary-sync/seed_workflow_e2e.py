#!/usr/bin/env python3
"""Seed and verify end-to-end workflow: operator → defect → leader → QA for 3 products."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from advance_v4_greenfield import Client
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
CTRL = "tbl6bCLJThyUaD8U"
DEFECT = "tblMtQ4aEwlzuhWs"
REASON = "tblvX8KSv73TluVk"

PROD_STOPPER = "rechKic8YG1cTc"
PROD_ZHIDONG = "recvnmMdIn6lCo"
PROD_PTJ92 = "recvnngInM41nM"

PROC = {
    "#2030": "recC9QvIgUH8oK",
    "#4050": "recs76rS587WRW",
    "#1020": "recy0wR8UdunUU",
}

BATCH = {
    "STOPPER": "S-WF-E2E",
    "ZHIDONG": "Z-WF-E2E",
    "PTJ92": "P-WF-E2E",
}


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
    proc: str,
    dry_run: bool,
) -> str | None:
    existing = find_control(client, batch_text)
    if existing:
        return existing
    row = {
        "fields": {
            "批号文本": batch_text,
            "产品": [product],
            "工序代码": [PROC[proc]],
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
    proc: str,
    control_id: str | None,
    control_field: str,
    region: str | None,
    ok_qty: int,
    scrap_qty: int,
    dry_run: bool,
) -> str | None:
    fields: dict = {
        "产品": [product],
        "工序代码": [PROC[proc]],
        "合格数量": ok_qty,
        "报废数量": scrap_qty,
        "工序下发状态": "已报工",
    }
    if control_id:
        fields[control_field] = [control_id]
    if region:
        fields["生产区域"] = region
    if dry_run:
        return f"dry-report-{product}-{proc}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", json={"fields": fields})
    if resp.get("code") != 0:
        raise RuntimeError(f"create report: {resp.get('msg')}")
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
    """Simulate automation: 待返工 → 班组长回填 → 待品保确认 → 品保确认 → 已确认。"""
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
        if key in ("批号文本", "生产批号"):
            got = extract_text(got)
        ok = got == val
        lines.append(f"{'PASS' if ok else 'FAIL'} {key}={got!r} 期望={val!r}")
    return lines


def run(dry_run: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("seed_workflow_e2e — 三产品报工 + 返工报废闭环")
    print("-" * 60)

    # --- 管控批 ---
    ctrl_s = ensure_control(client, BATCH["STOPPER"], PROD_STOPPER, "#2030", dry_run)
    ctrl_z = ensure_control(client, BATCH["ZHIDONG"], PROD_ZHIDONG, "#4050", dry_run)
    ctrl_p = ensure_control(client, BATCH["PTJ92"], PROD_PTJ92, "#1020", dry_run)
    print(f"管控批 STOPPER={ctrl_s} 止动块={ctrl_z} PTJ92={ctrl_p}")

    reason_rw = first_reason(client, "返工")
    reason_sc = first_reason(client, "报废")

    # --- STOPPER：有不良 + 返工闭环 ---
    stopper_id = create_report(
        client,
        product=PROD_STOPPER,
        proc="#2030",
        control_id=ctrl_s if not dry_run else None,
        control_field="关联管控批_STOPPER#2030",
        region="A1",
        ok_qty=100,
        scrap_qty=5,
        dry_run=dry_run,
    )
    print(f"STOPPER #2030 报工 {stopper_id}")
    if not dry_run and stopper_id:
        create_defect(client, stopper_id, 5, reason_rw, "返工", dry_run)
        for line in run_defect_chain(client, stopper_id, rework_ok=90, rework_scrap=10, dry_run=dry_run):
            print(f"  {line}")
        print("验收 STOPPER 有不良链:")
        for line in verify_main(
            client,
            stopper_id,
            {
                "工序下发状态": "已确认",
                "批号文本": BATCH["STOPPER"],
                "有效合格数量": 90,
                "有效报废数量": 10,
            },
        ):
            print(f"  {line}")

    # --- 止动块：无不良快速确认 ---
    zhidong_id = create_report(
        client,
        product=PROD_ZHIDONG,
        proc="#4050",
        control_id=ctrl_z if not dry_run else None,
        control_field="关联管控批_止动块#4050",
        region="MG02",
        ok_qty=80,
        scrap_qty=2,
        dry_run=dry_run,
    )
    print(f"止动块 #4050 报工 {zhidong_id}")
    if not dry_run and zhidong_id:
        patch_main(client, zhidong_id, {"工序下发状态": "已确认"}, dry_run)
        print("  无不良 → 已确认（模拟自动化）")
        print("验收 止动块 无不良链:")
        for line in verify_main(
            client,
            zhidong_id,
            {
                "工序下发状态": "已确认",
                "批号文本": BATCH["ZHIDONG"],
                "有效合格数量": 80,
                "有效报废数量": 2,
            },
        ):
            print(f"  {line}")

    # --- PTJ92：报废类不良 + 返工回填 ---
    ptj_id = create_report(
        client,
        product=PROD_PTJ92,
        proc="#1020",
        control_id=ctrl_p if not dry_run else None,
        control_field="关联管控批",
        region=None,
        ok_qty=60,
        scrap_qty=8,
        dry_run=dry_run,
    )
    print(f"PTJ92 #1020 报工 {ptj_id}")
    if not dry_run and ptj_id:
        patch_main(client, ptj_id, {"工位代码": "J1"}, dry_run)
        create_defect(client, ptj_id, 8, reason_sc, "报废", dry_run)
        for line in run_defect_chain(client, ptj_id, rework_ok=55, rework_scrap=5, dry_run=dry_run):
            print(f"  {line}")
        print("验收 PTJ92 有不良链:")
        for line in verify_main(
            client,
            ptj_id,
            {
                "工序下发状态": "已确认",
                "批号文本": BATCH["PTJ92"],
                "有效合格数量": 55,
                "有效报废数量": 5,
            },
        ):
            print(f"  {line}")

    if not dry_run:
        from sync_batch_summary import run_sync

        rows = run_sync(cfg, dry_run=False)
        print(f"sync: {len(rows)} summary rows")

    print("-" * 60)
    print("流程说明：")
    print("  操作工 → 各产品报工视图填单")
    print("  品保   → 品保·不良填报（关联报工记录）")
    print("  班组长 → 班组长·返工回填（主表 待返工）")
    print("  品保   → 品保·待确认（改 已确认）")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
