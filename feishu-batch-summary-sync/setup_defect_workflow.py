#!/usr/bin/env python3
"""Port 2026-base defect/rework forms into V4 wiki 不良明细表 + wire relationships."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from advance_v4_extensions import patch_view_columns
from advance_v4_greenfield import Client
from setup_role_entrypoints import (
    DEFECT_LEADER_KEEP,
    DEFECT_QA_KEEP,
    LEADER_MAIN_KEEP,
    QA_MAIN_KEEP,
    setup_leader_qa_views,
)
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
DEFECT = "tblMtQ4aEwlzuhWs"
REASON = "tblvX8KSv73TluVk"
WIKI = "https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d"

# 源 base（NiyZb…）表单对照
# vewKLH2HSb 品保·不良明细录入 → 品保·不良录入表单
# vewDhjhzdx 班组长·返工完成登记 → 班组长·返工回填表单
# vew7embFn1 品保·确认完成单     → 品保·待确认表单

DEFECT_QA_GRID = "vewGh4QxtW"
DEFECT_LEADER_GRID = "vewy8lBInU"
LEADER_MAIN_GRID = "vewQhe4OjQ"
QA_MAIN_GRID = "vewECvrwqs"

FORM_DEFECT_QA = "品保·不良录入表单"
FORM_LEADER_REWORK = "班组长·返工回填表单"
FORM_QA_CONFIRM = "品保·待确认表单"

# field ids（V4 实测）
FLD_DEFECT_LINK = "fldcqqWphC"
FLD_MAIN_BATCH = "fldvMRl868"
FLD_MAIN_TRACE = "fldYty1rzM"
FLD_MAIN_PRODUCT = "fldSUoQi47"
FLD_MAIN_PROC_TEXT = "fldLgbv109"
FLD_MAIN_STATUS = "fld1PUlkCs"
FLD_DEFECT_BATCH = "fldnh32U9v"
FLD_DEFECT_TRACE = "fldhWhLl3l"
FLD_DEFECT_STATUS = "fld2C1GSch"
FLD_DEFECT_QTY = "fldlzD0RBI"
FLD_DEFECT_REASON = "fldQ6StFTu"
FLD_DEFECT_DISP = "fldV5zsmwE"

STATUS_REPORTED = "optF4iy56X"  # 已报工
STATUS_PENDING_REWORK = "optsYMqMN1"
STATUS_PENDING_QA = "optghoBanu"
STATUS_CONFIRMED = "optifE7dfZ"
DEFECT_PENDING = "optSHJVG5d"

# 品保表单字段顺序（对齐源 vewKLH2HSb）
DEFECT_FORM_KEEP = {
    "关联生产记录",
    "生产批号",
    "完整追溯号",
    "不良数量",
    "不良原因",
    "处置类型",
}

LEADER_FORM_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
}

QA_FORM_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "批号文本",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "工序下发状态",
}


def _ref(table: str, field: str) -> str:
    return f"bitable::$table[{table}].$field[{field}]"


def ensure_field(client: Client, table: str, name: str, body: dict, dry_run: bool) -> str:
    if any(f["field_name"] == name for f in client.list_fields(table)):
        return f"skip field: {name}"
    if dry_run:
        return f"[dry-run] create {name}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{table}/fields", json=body)
    ok = resp.get("code") == 0
    fid = resp.get("data", {}).get("field", {}).get("field_id", "")
    return f"{'created' if ok else 'FAIL'} {name} ({fid}): {resp.get('msg', '')}"


def patch_formula_field(
    client: Client, table: str, field_id: str, name: str, expr: str, dry_run: bool
) -> str:
    if dry_run:
        return f"[dry-run] formula {name}"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields/{field_id}",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'} formula {name}: {resp.get('msg', '')}"


def fix_defect_mirror_fields(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.append(
        patch_formula_field(
            client,
            DEFECT,
            FLD_DEFECT_BATCH,
            "生产批号",
            f"{_ref(DEFECT, FLD_DEFECT_LINK)}.$column[{FLD_MAIN_BATCH}]",
            dry_run,
        )
    )
    lines.append(
        patch_formula_field(
            client,
            DEFECT,
            FLD_DEFECT_TRACE,
            "完整追溯号",
            f"{_ref(DEFECT, FLD_DEFECT_LINK)}.$column[{FLD_MAIN_TRACE}]",
            dry_run,
        )
    )
    lines.append(
        ensure_field(
            client,
            DEFECT,
            "备注",
            {"field_name": "备注", "type": 1},
            dry_run,
        )
    )
    for name, target in (("产品", FLD_MAIN_PRODUCT), ("工序代码", FLD_MAIN_PROC_TEXT)):
        expr = f"{_ref(DEFECT, FLD_DEFECT_LINK)}.$column[{target}]"
        existing = next((f for f in client.list_fields(DEFECT) if f["field_name"] == name), None)
        if existing:
            lines.append(
                patch_formula_field(client, DEFECT, existing["field_id"], name, expr, dry_run)
            )
        else:
            if dry_run:
                lines.append(f"[dry-run] create formula {name}")
            else:
                resp = client.call(
                    "POST",
                    f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields",
                    json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
                )
                lines.append(f"{'created' if resp.get('code')==0 else 'FAIL'} formula {name}")
    return lines


def patch_link_filter_reported(client: Client, dry_run: bool) -> str:
    """关联生产记录：仅可选「已报工」行（品保记不良时机）。"""
    body = {
        "field_name": "关联生产记录",
        "type": 18,
        "property": {
            "table_id": MAIN,
            "multiple": False,
            "filter_info": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_id": FLD_MAIN_STATUS,
                        "operator": "is",
                        "value": json.dumps([STATUS_REPORTED]),
                    }
                ],
            },
        },
    }
    if dry_run:
        return "[dry-run] link filter 关联生产记录=已报工"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/fields/{FLD_DEFECT_LINK}",
        json=body,
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'} 关联生产记录筛选(已报工): {resp.get('msg', '')}"


def list_views(client: Client, table: str) -> dict[str, str]:
    items = client.call(
        "GET", f"/bitable/v1/apps/{APP}/tables/{table}/views", params={"page_size": 100}
    ).get("data", {}).get("items", [])
    return {v["view_name"]: v["view_id"] for v in items}


def ensure_form_view(
    client: Client, table: str, name: str, keep: set[str], dry_run: bool
) -> tuple[str, str | None]:
    views = list_views(client, table)
    vid = views.get(name)
    if vid:
        return f"skip form exists: {name} ({vid})", vid
    if dry_run:
        return f"[dry-run] create form {name}", None
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/views",
        json={"view_name": name, "view_type": "form"},
    )
    if resp.get("code") != 0:
        return f"FAIL create form {name}: {resp.get('msg', '')}", None
    vid = resp["data"]["view"]["view_id"]
    return (
        f"created form {name} ({vid}) — 请在飞书表单设计器中保留字段: {', '.join(sorted(keep))}",
        vid,
    )


POOL_VIEW = "品保·可记不良池"


def ensure_reported_pool_view(client: Client, dry_run: bool) -> str:
    views = list_views(client, MAIN)
    vid = views.get(POOL_VIEW)
    if not vid:
        if dry_run:
            return f"[dry-run] create {POOL_VIEW}"
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/views",
            json={"view_name": POOL_VIEW, "view_type": "grid"},
        )
        if resp.get("code") != 0:
            return f"FAIL pool view: {resp.get('msg', '')}"
        vid = resp["data"]["view"]["view_id"]
    if dry_run:
        return f"[dry-run] filter {POOL_VIEW}"
    body = {
        "property": {
            "filter_info": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_id": FLD_MAIN_STATUS,
                        "operator": "is",
                        "value": json.dumps([STATUS_REPORTED]),
                    }
                ],
            }
        }
    }
    client.call("PATCH", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{vid}", json=body)
    keep = {"日志编号", "产品", "工序代码", "批号文本", "生产批号", "合格数量", "报废数量", "工序下发状态"}
    patch_view_columns(client, MAIN, vid, keep, dry_run)
    return f"ok pool view {POOL_VIEW} ({vid}) filter=已报工"


def ensure_reported_row(client: Client) -> str | None:
    """找或造一行「已报工」供品保记不良验收。"""
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 100})
    for it in data.get("data", {}).get("items", []):
        if it.get("fields", {}).get("工序下发状态") == "已报工":
            return it["record_id"]
    for it in data.get("data", {}).get("items", []):
        if it.get("fields", {}).get("工序下发状态") == "已确认":
            rid = it["record_id"]
            client.call(
                "PUT",
                f"/bitable/v1/apps/{APP}/tables/{MAIN}/records/{rid}",
                json={"fields": {"工序下发状态": "已报工", "返工后合格数": None, "返工后报废数": None}},
            )
            return rid
    return None


def run_e2e_defect(client: Client, dry_run: bool) -> list[str]:
    """模拟：品保记不良 → 主表待返工 → 班组长回填 → 品保确认。"""
    from seed_workflow_e2e import create_defect, first_reason, get_main_fields, patch_main, run_defect_chain

    lines: list[str] = []
    target = ensure_reported_row(client) if not dry_run else "dry-main"
    if not target:
        lines.append("skip e2e: no main row available")
        return lines
    if dry_run:
        lines.append(f"[dry-run] defect e2e on main {target}")
        return lines

    reason = first_reason(client, "返工")
    defect_id = create_defect(client, target, 3, reason, "返工", dry_run=False)
    lines.append(f"created defect {defect_id} -> main {target}")
    patch_main(client, target, {"工序下发状态": "待返工"}, dry_run=False)
    lines.append("main -> 待返工")
    for line in run_defect_chain(client, target, rework_ok=85, rework_scrap=3, dry_run=False):
        lines.append(f"  {line}")
    f = get_main_fields(client, target)
    lines.append(
        f"verify status={f.get('工序下发状态')} valid_ok={f.get('有效合格数量')} valid_scrap={f.get('有效报废数量')}"
    )
    return lines


def print_urls(view_ids: dict[str, str]) -> None:
    print("\n表单 / 视图入口（V4 Wiki）")
    print("-" * 60)
    mapping = [
        ("品保", "不良录入表单", DEFECT, FORM_DEFECT_QA),
        ("品保", "不良填报(表格)", DEFECT, DEFECT_QA_GRID),
        ("班组长", "待返工(表格)", DEFECT, DEFECT_LEADER_GRID),
        ("班组长", "返工回填表单", MAIN, FORM_LEADER_REWORK),
        ("班组长", "返工回填(表格)", MAIN, LEADER_MAIN_GRID),
        ("品保", "待确认表单", MAIN, FORM_QA_CONFIRM),
        ("品保", "待确认(表格)", MAIN, QA_MAIN_GRID),
    ]
    for role, label, table, key in mapping:
        vid = view_ids.get(key) or key
        print(f"[{role}] {label}")
        print(f"  {WIKI}?table={table}&view={vid}")


def run(dry_run: bool, skip_e2e: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    lines: list[str] = []
    view_ids: dict[str, str] = {}

    print("setup_defect_workflow — 不良明细 / 返工流程写入 V4")
    print("源对照: NiyZb…/不良明细表 vewKLH2HSb + 返工完成清单 vewDhjhzdx/vew7embFn1")
    print("-" * 60)

    print("## 1 不良明细字段与关联镜像")
    lines.extend(fix_defect_mirror_fields(client, dry_run))
    lines.append(patch_link_filter_reported(client, dry_run))
    lines.append(ensure_reported_pool_view(client, dry_run))

    print("## 2 表格视图列收敛 + 筛选")
    lines.extend(setup_leader_qa_views(client, dry_run))

    print("## 3 表单视图（对齐源 base 三张表单）")
    form_specs = [
        (DEFECT, FORM_DEFECT_QA, DEFECT_FORM_KEEP),
        (MAIN, FORM_LEADER_REWORK, LEADER_FORM_KEEP),
        (MAIN, FORM_QA_CONFIRM, QA_FORM_KEEP),
    ]
    view_ids: dict[str, str] = {
        DEFECT_QA_GRID: DEFECT_QA_GRID,
        DEFECT_LEADER_GRID: DEFECT_LEADER_GRID,
        LEADER_MAIN_GRID: LEADER_MAIN_GRID,
        QA_MAIN_GRID: QA_MAIN_GRID,
    }
    for table, fname, keep in form_specs:
        msg, vid = ensure_form_view(client, table, fname, keep, dry_run)
        lines.append(msg)
        if vid:
            view_ids[fname] = vid
    if not dry_run:
        for table in (DEFECT, MAIN):
            for vname, vid in list_views(client, table).items():
                if vname in (FORM_DEFECT_QA, FORM_LEADER_REWORK, FORM_QA_CONFIRM):
                    view_ids[vname] = vid

    if not skip_e2e and not dry_run:
        print("## 4 流程验收")
        lines.extend(run_e2e_defect(client, dry_run))

    for line in lines:
        print(line)

    print_urls(view_ids)
    print("-" * 60)
    print("飞书自动化（须界面确认 4 条规则，API 无法创建）：")
    print("  1 无不良保存 → 已确认")
    print("  2 不良明细关联生产记录 → 主表待返工")
    print("  3 主表填写返工后合格/报废 → 待品保确认")
    print("  4 品保待确认 → 已确认")
    print("不良原因筛选：在表单中为「不良原因」配置关联筛选（产品+工序+处置类型），参考联动规则表")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-e2e", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run, args.skip_e2e)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
