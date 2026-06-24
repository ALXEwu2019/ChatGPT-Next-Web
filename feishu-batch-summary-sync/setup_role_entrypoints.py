#!/usr/bin/env python3
"""Configure operator / team-leader / QA entry views for v4 greenfield."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from advance_v4_greenfield import Client
from advance_v4_extensions import patch_view_columns
from sync_batch_summary import load_config

APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
DEFECT = "tblMtQ4aEwlzuhWs"
WIKI = "https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d"

# 工序下发状态 option_id（API 实测）
STATUS_PENDING_REWORK = "optsYMqMN1"  # 待返工
STATUS_PENDING_QA = "optghoBanu"  # 待品保确认

# 不良明细·状态
DEFECT_STATUS_PENDING = "optSHJVG5d"  # 待返工

# 操作工：只保留扫码/填单必要列（公式只读列尽量隐藏）
OPERATOR_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "生产批号",
    "合格数量",
    "报废数量",
    "操作工",
    "班次",
    "生产区域",
    "工位代码",
}

OPERATOR_VIEW_KEEP: dict[str, set[str]] = {
    **{vid: OPERATOR_KEEP | extra for vid, extra in {
        "vewfbrQvsu": {"关联管控批_STOPPER#2030", "关联管控批"},
        "vew7Diocr5": {"上道批号_STOPPER#4050"},
        "vewgS0km1u": {"上道批号_STOPPER#60"},
        "vewqlHptpP": {"上道批号_STOPPER#70"},
        "vew4kJ8hxX": {"关联管控批_止动块#4050", "关联管控批"},
        "vewEMVET4u": {"上道批号_止动块#60"},
        "vewUWGnXfU": {"上道批号_止动块#70"},
        "vewEJZrQu5": {"上道批号_止动块#80"},
        "vew2SeSRgG": {"关联管控批", "工位代码"},
        "vewDNLBqX5": {"上道批号_PTJ92#3040"},
        "vewhTfcmic": {"上道批号_PTJ92#50"},
    }.items()},
}

LEADER_MAIN_VIEW = "vewQhe4OjQ"  # 班组长·返工回填
LEADER_MAIN_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "工序下发状态",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "是否有不良",
}

QA_MAIN_VIEW = "vewECvrwqs"  # 品保·待确认
QA_MAIN_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "工序下发状态",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "有效合格数量",
    "有效报废数量",
    "是否有不良",
}

DEFECT_QA_VIEW = "vewGh4QxtW"  # 品保·不良填报
DEFECT_QA_KEEP = {
    "明细编号",
    "关联生产记录",
    "生产批号",
    "完整追溯号",
    "不良数量",
    "不良原因",
    "处置类型",
    "状态",
}

DEFECT_LEADER_VIEW = "vewy8lBInU"  # 班组长·待返工
DEFECT_LEADER_KEEP = {
    "明细编号",
    "关联生产记录",
    "生产批号",
    "不良数量",
    "不良原因",
    "处置类型",
    "状态",
    "返工后合格数",
    "返工后报废数",
}

# 三角色入口清单（文档/验收输出）
ENTRYPOINTS = [
    ("操作工", "STOPPER·#2030报工视图", MAIN, "vewfbrQvsu"),
    ("操作工", "STOPPER·#4050报工视图", MAIN, "vew7Diocr5"),
    ("操作工", "STOPPER·#60报工视图", MAIN, "vewgS0km1u"),
    ("操作工", "STOPPER·#70报工视图", MAIN, "vewqlHptpP"),
    ("操作工", "止动块·#4050报工", MAIN, "vew4kJ8hxX"),
    ("操作工", "止动块·#60 报工视图", MAIN, "vewEMVET4u"),
    ("操作工", "止动块·#70 报工视图", MAIN, "vewUWGnXfU"),
    ("操作工", "止动块·#80 报工视图", MAIN, "vewEJZrQu5"),
    ("操作工", "PTJ92·#1020报工", MAIN, "vew2SeSRgG"),
    ("操作工", "PTJ92·#3040报工", MAIN, "vewDNLBqX5"),
    ("操作工", "PTJ92·#50报工", MAIN, "vewhTfcmic"),
    ("班组长", "班组长·返工回填", MAIN, LEADER_MAIN_VIEW),
    ("班组长", "班组长·待返工", DEFECT, DEFECT_LEADER_VIEW),
    ("品保", "品保·不良填报", DEFECT, DEFECT_QA_VIEW),
    ("品保", "品保·待确认", MAIN, QA_MAIN_VIEW),
]


def patch_view_filter(
    client: Client,
    table: str,
    view_id: str,
    field_id: str,
    option_id: str,
    dry_run: bool,
) -> str:
    body = {
        "property": {
            "filter_info": {
                "conjunction": "and",
                "conditions": [
                    {
                        "field_id": field_id,
                        "operator": "is",
                        "value": json.dumps([option_id]),
                    }
                ],
            }
        }
    }
    if dry_run:
        return f"[dry-run] filter {view_id} {field_id}={option_id}"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{table}/views/{view_id}",
        json=body,
    )
    ok = resp.get("code") == 0
    return f"{'filter ok' if ok else 'FAIL filter'} {view_id}: {resp.get('msg', '')}"


def setup_operator_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for view_id, keep in OPERATOR_VIEW_KEEP.items():
        lines.append(patch_view_columns(client, MAIN, view_id, keep, dry_run))
    return lines


def setup_leader_qa_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.append(patch_view_columns(client, MAIN, LEADER_MAIN_VIEW, LEADER_MAIN_KEEP, dry_run))
    lines.append(patch_view_columns(client, MAIN, QA_MAIN_VIEW, QA_MAIN_KEEP, dry_run))
    lines.append(patch_view_columns(client, DEFECT, DEFECT_QA_VIEW, DEFECT_QA_KEEP, dry_run))
    lines.append(patch_view_columns(client, DEFECT, DEFECT_LEADER_VIEW, DEFECT_LEADER_KEEP, dry_run))

    status_fid = next(
        f["field_id"] for f in client.list_fields(MAIN) if f["field_name"] == "工序下发状态"
    )
    defect_status_fid = next(
        f["field_id"] for f in client.list_fields(DEFECT) if f["field_name"] == "状态"
    )
    lines.append(
        patch_view_filter(client, MAIN, LEADER_MAIN_VIEW, status_fid, STATUS_PENDING_REWORK, dry_run)
    )
    # 品保·待确认 filter already set in Feishu; re-apply for idempotency
    lines.append(
        patch_view_filter(client, MAIN, QA_MAIN_VIEW, status_fid, STATUS_PENDING_QA, dry_run)
    )
    lines.append(
        patch_view_filter(
            client, DEFECT, DEFECT_LEADER_VIEW, defect_status_fid, DEFECT_STATUS_PENDING, dry_run
        )
    )
    return lines


def print_entry_urls() -> None:
    print("\n角色入口链接（可复制到飞书文档/工位二维码说明）")
    print("-" * 60)
    for role, name, table, vid in ENTRYPOINTS:
        url = f"{WIKI}?table={table}&view={vid}"
        print(f"[{role}] {name}")
        print(f"  {url}")


def run(dry_run: bool, operators_only: bool, roles_only: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("setup_role_entrypoints — 三角色入口视图")
    print("-" * 60)

    if not roles_only:
        print("## 操作工报工视图（列收敛）")
        for line in setup_operator_views(client, dry_run):
            print(line)

    if not operators_only:
        print("## 班组长 / 品保视图（列收敛 + 筛选）")
        for line in setup_leader_qa_views(client, dry_run):
            print(line)

    print("-" * 60)
    print_entry_urls()
    print("-" * 60)
    print("扫码填单：请在飞书界面将各「操作工」表格视图复制为「表单视图」并生成二维码。")
    print("列顺序：在表单设计器中把选批→生产批号→区域/工位→数量→操作工 拖到最前。")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Setup operator/leader/QA entry views")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--operators-only", action="store_true")
    p.add_argument("--roles-only", action="store_true", help="only leader/QA views")
    args = p.parse_args()
    try:
        return run(args.dry_run, args.operators_only, args.roles_only)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
