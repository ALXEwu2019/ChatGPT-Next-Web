#!/usr/bin/env python3
"""按 2026 Base 不良明细表 + 返工完成清单，修复并创建 V4 Wiki 对应结构。

源：机加工车间生产日志管理系统（新） NiyZbKpKfae9x3sUP64cl9SFnRb
目标：机加工生产日志 V4 Wiki HiqNwQnxniKGEGketZBcEC9Sn3d

用法：
  python3 sync_defect_rework_from_2026.py              # 审计 + 修复 + 视图 + 验收
  python3 sync_defect_rework_from_2026.py --audit-only   # 只读对照源/目标字段
  python3 sync_defect_rework_from_2026.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from advance_v4_extensions import patch_view_columns
from advance_v4_greenfield import Client
from defect_rework_schema import (
    DEFECT_ENSURE_FIELDS,
    DEFECT_FORMULA_FIELDS,
    DUPLICATE_SUFFIX,
    LEADER_DEFECT_KEEP,
    LEADER_MAIN_KEEP,
    MAIN_REWORK_FIELDS,
    MAIN_STATUS_OPTIONS,
    QA_DEFECT_KEEP,
    QA_MAIN_KEEP,
    SRC_APP,
    SRC_DEFECT,
    SRC_REWORK,
    SRC_TO_V4_DEFECT,
    SRC_TO_V4_MAIN,
    V4_APP,
    V4_DEFECT,
    V4_MAIN,
    V4_VIEWS,
)
from remediate_defect_leader_view import (
    clean_bad_disposition_records,
    ensure_number_field,
    ensure_single_select,
    fix_disposition_field,
    patch_leader_view_filter,
)
from setup_defect_workflow import (
    FORM_DEFECT_QA,
    FORM_LEADER_REWORK,
    FORM_QA_CONFIRM,
    ensure_form_view,
    ensure_reported_pool_view,
    fix_defect_mirror_fields,
    patch_link_filter_reported,
    print_urls,
)
from setup_role_entrypoints import option_triplet, patch_view_filter
from sync_batch_summary import feishu_credentials_ok, load_config

WIKI = f"https://kcnfxml9dtzq.feishu.cn/wiki/{V4_APP}"

# 主表工序下发状态 option_id（动态解析优先，此为回退文档值）
STATUS_PENDING_REWORK = "optsYMqMN1"
STATUS_PENDING_QA = "optghoBanu"


def field_map(client: Client, app: str, table: str) -> dict[str, dict]:
    """临时切换 app 读取字段（Client 默认 V4_APP）。"""
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 300}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{app}/tables/{table}/fields", params=params)["data"]
        items.extend(data["items"])
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return {f["field_name"]: f for f in items}


def audit_tables(client: Client) -> list[str]:
    lines: list[str] = []
    lines.append("## 源 → V4 字段对照审计")
    src_defect = field_map(client, SRC_APP, SRC_DEFECT)
    src_rework = field_map(client, SRC_APP, SRC_REWORK)
    v4_defect = field_map(client, V4_APP, V4_DEFECT)
    v4_main = field_map(client, V4_APP, V4_MAIN)

    lines.append(f"源不良明细 {SRC_DEFECT}: {len(src_defect)} 字段")
    lines.append(f"源返工完成 {SRC_REWORK}: {len(src_rework)} 字段")
    lines.append(f"V4不良明细 {V4_DEFECT}: {len(v4_defect)} 字段")
    lines.append(f"V4主表(返工回填) {V4_MAIN}: {len(v4_main)} 字段")

    for src_name, v4_name in SRC_TO_V4_DEFECT.items():
        src_ok = src_name in src_defect
        v4_ok = v4_name in v4_defect
        mark = "OK" if src_ok and v4_ok else ("SRC?" if not src_ok else "V4缺")
        lines.append(f"  [{mark}] {src_name} → {v4_name}")

    for src_name, note in SRC_TO_V4_MAIN.items():
        src_ok = src_name in src_rework or src_name in src_defect
        v4_ok = src_name in v4_main if note != "（主表行本身）" else True
        mark = "OK" if src_ok and v4_ok else "CHECK"
        lines.append(f"  [{mark}] 返工清单·{src_name} → {note}")

    missing = [n for n in DEFECT_ENSURE_FIELDS if n not in v4_defect]
    if missing:
        lines.append(f"V4不良明细待补字段: {missing}")
    else:
        lines.append("V4不良明细核心字段: 齐全")

    missing_main = [n for n in MAIN_REWORK_FIELDS if n not in v4_main]
    if missing_main:
        lines.append(f"V4主表返工字段待补: {missing_main}")
    else:
        lines.append("V4主表返工字段: 齐全")

    dupes = [n for n in v4_defect if DUPLICATE_SUFFIX in n]
    if dupes:
        lines.append(f"警告·重复导入字段（建议飞书手删）: {dupes}")

    for name in DEFECT_FORMULA_FIELDS:
        f = v4_defect.get(name)
        if not f:
            lines.append(f"警告·缺公式字段: {name}")
        elif f.get("type") != 20:
            lines.append(f"警告·{name} 类型={f.get('type')}，应为公式(20)")

    return lines


def ensure_defect_fields(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    existing = field_map(client, V4_APP, V4_DEFECT)

    for name, spec in DEFECT_ENSURE_FIELDS.items():
        ftype = spec["type"]
        if name in existing:
            cur = existing[name]
            if cur["type"] == ftype:
                lines.append(f"skip field: {name}")
                continue
            if ftype == 3 and cur["type"] == 3:
                # 单选：刷新选项
                opts = [{"name": o} for o in spec.get("options", [])]
                if dry_run:
                    lines.append(f"[dry-run] fix options {name}")
                    continue
                resp = client.call(
                    "PUT",
                    f"/bitable/v1/apps/{V4_APP}/tables/{V4_DEFECT}/fields/{cur['field_id']}",
                    json={"field_name": name, "type": 3, "property": {"options": opts}},
                )
                lines.append(f"{'ok' if resp.get('code')==0 else 'FAIL'} options {name}")
                continue
            lines.append(f"warn field {name}: type {cur['type']} != {ftype} (需手调)")

        body: dict = {"field_name": name, "type": ftype, "property": {}}
        if ftype == 2:
            body["property"] = {"formatter": spec.get("formatter", "0")}
        elif ftype == 3:
            body["property"] = {"options": [{"name": o} for o in spec["options"]]}
        elif ftype == 18:
            body["property"] = {
                "table_id": spec["link_table"],
                "multiple": spec.get("multiple", False),
            }
        elif ftype == 1001:
            body["property"] = {"auto_serial": {"type": "auto_increment_number"}}

        if dry_run:
            lines.append(f"[dry-run] create {name} (type {ftype})")
            continue
        resp = client.call(
            "POST", f"/bitable/v1/apps/{V4_APP}/tables/{V4_DEFECT}/fields", json=body
        )
        ok = resp.get("code") == 0
        fid = resp.get("data", {}).get("field", {}).get("field_id", "")
        lines.append(f"{'created' if ok else 'FAIL'} {name} ({fid}): {resp.get('msg', '')}")

    # 实收不良数量与不良数量：若仅一方有值，用公式同步（可选轻量）
    names = {f["field_name"] for f in client.list_fields(V4_DEFECT)}
    if "不良数量" not in names:
        lines.append(ensure_number_field(client, "不良数量", dry_run))
    if "实收不良数量" not in names:
        lines.append(ensure_number_field(client, "实收不良数量", dry_run))

    return lines


def ensure_main_rework_fields(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    existing = field_map(client, V4_APP, V4_MAIN)

    for name, spec in MAIN_REWORK_FIELDS.items():
        if name in existing:
            lines.append(f"skip main field: {name}")
            continue
        ftype = spec["type"]
        body: dict = {"field_name": name, "type": ftype, "property": {}}
        if ftype == 2:
            body["property"] = {"formatter": spec.get("formatter", "0")}
        elif ftype == 3 and name == "工序下发状态":
            body["property"] = {"options": [{"name": o} for o in MAIN_STATUS_OPTIONS]}
        if dry_run:
            lines.append(f"[dry-run] create main {name}")
            continue
        resp = client.call(
            "POST", f"/bitable/v1/apps/{V4_APP}/tables/{V4_MAIN}/fields", json=body
        )
        ok = resp.get("code") == 0
        lines.append(f"{'created' if ok else 'FAIL'} main {name}: {resp.get('msg', '')}")
    return lines


def setup_views_and_filters(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.append(patch_view_columns(client, V4_DEFECT, V4_VIEWS["品保·不良填报"], QA_DEFECT_KEEP, dry_run))
    lines.append(patch_view_columns(client, V4_DEFECT, V4_VIEWS["班组长·待返工"], LEADER_DEFECT_KEEP, dry_run))
    lines.append(patch_view_columns(client, V4_MAIN, V4_VIEWS["班组长·返工回填"], LEADER_MAIN_KEEP, dry_run))
    lines.append(patch_view_columns(client, V4_MAIN, V4_VIEWS["品保·待确认"], QA_MAIN_KEEP, dry_run))

    # 班组长·待返工：处置类型=返工 + 状态=待返工
    lines.append(patch_leader_view_filter(client, dry_run))

    # 主表：待返工 / 待品保确认
    status_fid = next(
        f["field_id"] for f in client.list_fields(V4_MAIN) if f["field_name"] == "工序下发状态"
    )
    try:
        _, _, pending_rw = option_triplet(client.list_fields(V4_MAIN), "工序下发状态", "待返工")
        lines.append(
            patch_view_filter(client, V4_MAIN, V4_VIEWS["班组长·返工回填"], status_fid, pending_rw, dry_run)
        )
    except RuntimeError:
        lines.append(
            patch_view_filter(
                client, V4_MAIN, V4_VIEWS["班组长·返工回填"],
                status_fid, STATUS_PENDING_REWORK, dry_run,
            )
        )
    try:
        _, _, pending_qa = option_triplet(client.list_fields(V4_MAIN), "工序下发状态", "待品保确认")
        lines.append(
            patch_view_filter(client, V4_MAIN, V4_VIEWS["品保·待确认"], status_fid, pending_qa, dry_run)
        )
    except RuntimeError:
        lines.append(
            patch_view_filter(
                client, V4_MAIN, V4_VIEWS["品保·待确认"],
                status_fid, STATUS_PENDING_QA, dry_run,
            )
        )
    return lines


def verify_views(client: Client) -> list[str]:
    lines: list[str] = []
    lines.append("## 视图验收")
    for vname, vid in V4_VIEWS.items():
        if not vid:
            continue
        table = V4_DEFECT if "不良" in vname or "待返工" in vname else V4_MAIN
        resp = client.call("GET", f"/bitable/v1/apps/{V4_APP}/tables/{table}/views/{vid}")
        v = resp.get("data", {}).get("view", {})
        if not v:
            lines.append(f"FAIL 视图不存在: {vname} ({vid})")
            continue
        fi = v.get("property", {}).get("filter_info") or {}
        n = len(fi.get("conditions") or [])
        lines.append(f"PASS {vname} ({vid}) type={v.get('view_type')} filters={n}")
    return lines


def run(audit_only: bool, dry_run: bool, skip_e2e: bool, config_path: Path) -> int:
    cfg = load_config(config_path)
    if not feishu_credentials_ok(cfg):
        print("ERROR: 请配置飞书凭证（任选其一）：")
        print("  1) config.json 或 config.local.json 中 feishu.app_id / app_secret")
        print("  2) 环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET")
        print("  模板: cp config.v4.wiki.example.json config.json")
        print("  或:   cp config.local.example.json config.local.json  # 仅凭证，可不入库")
        return 1

    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("sync_defect_rework_from_2026 — 不良明细 + 返工完成 → V4")
    print(f"源: {SRC_APP}  目标: {V4_APP}")
    print("-" * 60)

    all_lines: list[str] = []
    all_lines.extend(audit_tables(client))
    if audit_only:
        for line in all_lines:
            print(line)
        return 0

    print("\n## 1 补齐 V4 不良明细字段（对齐源库）")
    all_lines.extend(ensure_defect_fields(client, dry_run))
    all_lines.append(fix_disposition_field(client, dry_run))
    fid, _ = ensure_single_select(client, "状态", ["待返工", "已返工", "已确认"], dry_run)
    all_lines.append(f"ok 状态 field_id={fid}")

    print("## 2 补齐 V4 主表返工字段（源自返工完成清单）")
    all_lines.extend(ensure_main_rework_fields(client, dry_run))

    print("## 3 公式镜像 + 关联筛选 + 可记不良池")
    all_lines.extend(fix_defect_mirror_fields(client, dry_run))
    all_lines.append(patch_link_filter_reported(client, dry_run))
    all_lines.append(ensure_reported_pool_view(client, dry_run))

    print("## 4 表格视图列 + 筛选")
    all_lines.extend(setup_views_and_filters(client, dry_run))
    all_lines.extend(clean_bad_disposition_records(client, dry_run))

    print("## 5 表单视图（对齐源三张表单）")
    from defect_rework_schema import DEFECT_FORM_KEEP, LEADER_FORM_KEEP, QA_FORM_KEEP

    view_ids: dict[str, str] = {k: v for k, v in V4_VIEWS.items() if v}
    for table, fname, keep_set in [
        (V4_DEFECT, FORM_DEFECT_QA, DEFECT_FORM_KEEP),
        (V4_MAIN, FORM_LEADER_REWORK, LEADER_FORM_KEEP),
        (V4_MAIN, FORM_QA_CONFIRM, QA_FORM_KEEP),
    ]:
        msg, vid = ensure_form_view(client, table, fname, keep_set, dry_run)
        all_lines.append(msg)
        if vid:
            view_ids[fname] = vid

    if not dry_run:
        all_lines.extend(verify_views(client))

    for line in all_lines:
        print(line)

    print_urls({k: v for k, v in view_ids.items() if v})
    print("-" * 60)
    print("架构说明：V4 不单独建「返工完成清单」表；班组长在 **主表** 填返工后合格/报废。")
    print("源 vewDhjhzdx → V4 班组长·返工回填表单；源 vew7embFn1 → V4 品保·待确认表单。")
    print(f"班组长·待返工: {WIKI}?table={V4_DEFECT}&view={V4_VIEWS['班组长·待返工']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="按 2026 不良/返工表修复创建 V4")
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    p.add_argument("--audit-only", action="store_true", help="只审计源与 V4 字段差异")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-e2e", action="store_true")
    args = p.parse_args()
    try:
        return run(args.audit_only, args.dry_run, args.skip_e2e, args.config)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
