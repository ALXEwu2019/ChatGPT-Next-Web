#!/usr/bin/env python3
"""Fix 不良明细表 + 班组长·待返工 after 2026-base field import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from advance_v4_extensions import patch_view_columns
from advance_v4_greenfield import Client
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
DEFECT = "tblMtQ4aEwlzuhWs"
LEADER_VIEW = "vewy8lBInU"

TASK_PENDING = "optfSvslQY"  # 返工任务状态·待返工（回退筛选用）

LEADER_KEEP = {
    "关联生产记录",
    "生产批号",
    "产品",
    "工序代码",
    "实收不良数量",
    "不良原因",
    "处置类型",
    "不良类型",
    "登记人",
    "通知时间",
    "返工任务状态",
    "返工后合格数",
    "返工后报废数",
    "返工人",
    "确认人",
    "备注",
    "状态",
    "不良数量",
}


def ensure_single_select(
    client: Client, name: str, options: list[str], dry_run: bool
) -> tuple[str, dict[str, str]]:
    """确保单选字段存在且选项正确，返回 (field_id, name->id)。"""
    fields = client.list_fields(DEFECT)
    existing = next((f for f in fields if f["field_name"] == name), None)
    opts_body = [{"name": n} for n in options]
    if existing:
        fid = existing["field_id"]
        if dry_run:
            return fid, {o["name"]: o["id"] for o in existing.get("property", {}).get("options", [])}
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields/{fid}",
            json={"field_name": name, "type": 3, "property": {"options": opts_body}},
        )
        if resp.get("code") != 0:
            raise RuntimeError(f"fix {name}: {resp.get('msg')}")
        mapping = {o["name"]: o["id"] for o in resp["data"]["field"]["property"]["options"]}
        return fid, mapping
    if dry_run:
        return f"dry-{name}", {n: f"dry-{n}" for n in options}
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields",
        json={"field_name": name, "type": 3, "property": {"options": opts_body}},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create {name}: {resp.get('msg')}")
    fid = resp["data"]["field"]["field_id"]
    mapping = {o["name"]: o["id"] for o in resp["data"]["field"]["property"]["options"]}
    return fid, mapping


def ensure_number_field(client: Client, name: str, dry_run: bool) -> str:
    fields = client.list_fields(DEFECT)
    bad = next((f for f in fields if f["field_name"] == name), None)
    if bad and bad["type"] == 2:
        return f"skip number: {name}"
    if bad and bad["type"] != 2:
        if dry_run:
            return f"[dry-run] recreate number {name} (was type {bad['type']})"
        client.call(
            "DELETE",
            f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields/{bad['field_id']}",
        )
    if dry_run:
        return f"[dry-run] create number {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields",
        json={"field_name": name, "type": 2, "property": {"formatter": "0"}},
    )
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} number {name}: {resp.get('msg', '')}"


def fix_disposition_field(client: Client, dry_run: bool) -> str:
    """移除误录入的日期选项，只保留 返工/报废。"""
    _, mapping = ensure_single_select(client, "处置类型", ["返工", "报废"], dry_run)
    return f"ok 处置类型 options: {list(mapping.keys())}"


def ensure_status_field(client: Client, dry_run: bool) -> str:
    fid, _ = ensure_single_select(client, "状态", ["待返工", "已返工", "已确认"], dry_run)
    return fid


def option_triplet(fields: list[dict], field_name: str, option_name: str) -> tuple[str, int, str]:
    field = next((f for f in fields if f["field_name"] == field_name), None)
    if not field:
        raise RuntimeError(f"missing field: {field_name}")
    for opt in field.get("property", {}).get("options", []):
        if opt["name"] == option_name:
            return field["field_id"], field["type"], opt["id"]
    raise RuntimeError(f"missing option {field_name}={option_name}")


def clean_bad_disposition_records(client: Client, dry_run: bool) -> list[str]:
    """把误选为日期的处置类型清空或改为返工。"""
    lines: list[str] = []
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{DEFECT}/records", params={"page_size": 500})
    for it in data.get("data", {}).get("items", []):
        disp = it.get("fields", {}).get("处置类型")
        if disp in ("2026/06/22 15:54", "2026/06/24 21:04"):
            rid = it["record_id"]
            if dry_run:
                lines.append(f"[dry-run] fix disposition on {rid}")
                continue
            resp = client.call(
                "PUT",
                f"/bitable/v1/apps/{APP}/tables/{DEFECT}/records/{rid}",
                json={"fields": {"处置类型": "返工", "返工任务状态": "待返工"}},
            )
            lines.append(f"{'fixed' if resp.get('code')==0 else 'FAIL'} {rid} 处置类型→返工")
    if not lines:
        lines.append("skip: no corrupt disposition rows")
    return lines


def patch_leader_view_filter(client: Client, dry_run: bool) -> str:
    """班组长·待返工：处置类型=返工 且 状态=待返工（对齐源库待返工任务）。"""
    fields = client.list_fields(DEFECT)
    conditions: list[dict] = []
    try:
        disp_fid, disp_type, disp_rework = option_triplet(fields, "处置类型", "返工")
        conditions.append(
            {
                "field_id": disp_fid,
                "field_type": disp_type,
                "operator": "is",
                "value": json.dumps([disp_rework]),
            }
        )
    except RuntimeError:
        pass
    try:
        status_fid, status_type, status_pending = option_triplet(fields, "状态", "待返工")
        conditions.append(
            {
                "field_id": status_fid,
                "field_type": status_type,
                "operator": "is",
                "value": json.dumps([status_pending]),
            }
        )
    except RuntimeError:
        task_f = next((f for f in fields if f["field_name"] == "返工任务状态"), None)
        if task_f:
            conditions.append(
                {
                    "field_id": task_f["field_id"],
                    "field_type": task_f["type"],
                    "operator": "is",
                    "value": json.dumps([TASK_PENDING]),
                }
            )
    if not conditions:
        return f"FAIL filter {LEADER_VIEW}: no filter fields"
    body = {"property": {"filter_info": {"conjunction": "and", "conditions": conditions}}}
    if dry_run:
        return f"[dry-run] filter {LEADER_VIEW}: {conditions}"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/views/{LEADER_VIEW}",
        json=body,
    )
    ok = resp.get("code") == 0
    return f"{'filter ok' if ok else 'FAIL filter'} {LEADER_VIEW}: {resp.get('msg', '')}"


def run(dry_run: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_defect_leader_view — 班组长·待返工")
    print("-" * 60)

    lines: list[str] = []
    lines.append(fix_disposition_field(client, dry_run))
    status_fid = ensure_status_field(client, dry_run)
    lines.append(f"ok 状态 field_id={status_fid}")
    lines.append(ensure_number_field(client, "返工后合格数", dry_run))
    lines.append(ensure_number_field(client, "返工后报废数", dry_run))
  # 不良数量：优先用实收不良数量；若无则建
    if not any(f["field_name"] == "不良数量" for f in client.list_fields(DEFECT)):
        lines.append(ensure_number_field(client, "不良数量", dry_run))
    lines.extend(clean_bad_disposition_records(client, dry_run))
    lines.append(patch_leader_view_filter(client, dry_run))
    lines.append(patch_view_columns(client, DEFECT, LEADER_VIEW, LEADER_KEEP, dry_run))

    for line in lines:
        print(line)

    print("-" * 60)
    print("班组长·待返工 视图列（上→下建议）：")
    print("  关联生产记录 → 生产批号 → 产品 → 工序代码 → 实收不良数量")
    print("  → 不良原因 → 处置类型(返工) → 登记人 → 通知时间 → 返工任务状态")
    print("  → 返工后合格数 → 返工后报废数 → 返工人 → 备注")
    print(f"链接: https://kcnfxml9dtzq.feishu.cn/wiki/{APP}?table={DEFECT}&view={LEADER_VIEW}")
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
