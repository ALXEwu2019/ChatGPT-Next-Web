#!/usr/bin/env python3
"""V4 全面修复：锁定列仅保留日志编号自动编号，其余按逻辑优化。

执行顺序：
  1. 审计（修复前）
  2. 恢复日志编号为自动编号 + 重刷批号公式
  3. 上道/管控关联改为单选
  4. 去重通用上道批号 + 重刷公式
  5. 12 工位视图列 + 筛选（process_routes + role_entrypoints）
  6. PTJ92 上道字段
  7. 不良流程视图
  8. 审计（修复后）
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from advance_v4_greenfield import APP, MAIN, VIEW_KEEP, patch_views, Client
from process_registry import FIRST_CTRL_FIELD, OPERATOR_VIEWS, UPSTREAM_FIELD
from remediate_index_column import restore_autonumber
from remediate_v4_formulas import dedupe_upstream_links, patch_formulas
from sync_batch_summary import feishu_credentials_ok, load_config

LINKAGE = "tblUyVVrhKQOu1pO"
ZHIDONG_2030_VIEW = "vewBbCamcQ"

UPSTREAM_LINK_NAMES = {"上道批号", *UPSTREAM_FIELD.values(), *FIRST_CTRL_FIELD.values(), "关联管控批"}


def fix_link_single(client: Client, field: dict, dry_run: bool) -> str:
    name = field["field_name"]
    prop = field.get("property") or {}
    if field.get("type") != 18:
        return f"skip link {name}: type={field.get('type')}"
    if prop.get("multiple") is False:
        return f"skip link {name}: already single"
    body = {
        "field_name": name,
        "type": 18,
        "property": {
            "table_id": prop.get("table_id"),
            "multiple": False,
        },
    }
    if dry_run:
        return f"[dry-run] link {name} → single"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{field['field_id']}",
        json=body,
    )
    ok = resp.get("code") == 0
    return f"{'ok' if ok else 'FAIL'} link {name} single: {resp.get('msg', '')}"


def fix_upstream_links(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for f in client.list_fields(MAIN):
        if f["field_name"] in UPSTREAM_LINK_NAMES:
            lines.append(fix_link_single(client, f, dry_run))
    return lines


def fix_linkage_disposition_options(client: Client, dry_run: bool) -> list[str]:
    """清理联动表默认处置类型脏选项（不改主字段）。"""
    lines: list[str] = []
    fields = client.list_fields(LINKAGE)
    disp = next((f for f in fields if f["field_name"] == "默认处置类型"), None)
    if not disp or disp.get("type") != 3:
        return ["skip linkage 默认处置类型"]
    opts = [{"name": n} for n in ("返工", "报废")]
    if dry_run:
        return ["[dry-run] linkage 默认处置类型 → 返工/报废"]
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{LINKAGE}/fields/{disp['field_id']}",
        json={"field_name": "默认处置类型", "type": 3, "property": {"options": opts}},
    )
    lines.append(f"{'ok' if resp.get('code')==0 else 'FAIL'} linkage 默认处置类型: {resp.get('msg','')}")
    enable = next((f for f in fields if f["field_name"] == "启用状态"), None)
    if enable and enable.get("type") == 3:
        eopts = [{"name": n} for n in ("启用", "停用")]
        resp2 = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{LINKAGE}/fields/{enable['field_id']}",
            json={"field_name": "启用状态", "type": 3, "property": {"options": eopts}},
        )
        lines.append(f"{'ok' if resp2.get('code')==0 else 'FAIL'} linkage 启用状态: {resp2.get('msg','')}")
    return lines


def run_subprocess(script: str, *args: str) -> int:
    cmd = [sys.executable, str(Path(__file__).with_name(script)), *args]
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=Path(__file__).parent)


def run(dry_run: bool, skip_audit: bool, config_path: Path) -> int:
    cfg = load_config(config_path)
    if not feishu_credentials_ok(cfg):
        print("ERROR: 请配置飞书凭证后执行 remediate_v4_comprehensive.py")
        return 1

    if not skip_audit:
        code = run_subprocess("audit_v4_comprehensive.py", "--config", str(config_path))
        if code not in (0, 2):
            return code

    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("\n" + "=" * 60)
    print("## 修复 1：索引列 — 恢复日志编号自动编号（不改批号公式首列）")
    print(restore_autonumber(client, dry_run))

    print("\n## 修复 2：上道/管控关联 → 单选")
    for line in fix_upstream_links(client, dry_run):
        print(line)

    print("\n## 修复 3：去重双填上道 + 重刷批号/有效数公式")
    for line in dedupe_upstream_links(client, dry_run):
        print(line)
    for line in patch_formulas(client, dry_run):
        print(line)

    print("\n## 修复 4：8 核心报工视图列收敛")
    for line in patch_views(client, dry_run):
        print(line)

    print("\n## 修复 5：工序路线 + 12 工位视图筛选/列")
    route_args = ["--dry-run"] if dry_run else []
    run_subprocess("remediate_process_routes.py", *route_args)

    print("\n## 修复 6：三角色入口视图")
    role_args = ["--roles-only"] + (["--dry-run"] if dry_run else [])
    run_subprocess("setup_role_entrypoints.py", *role_args)

    print("\n## 修复 7：PTJ92 上道字段与视图")
    ptj_args = ["--dry-run"] if dry_run else []
    run_subprocess("fix_ptj92_upstream.py", *ptj_args)

    print("\n## 修复 8：不良明细 / 返工视图")
    defect_args = ["--skip-e2e"] + (["--dry-run"] if dry_run else [])
    run_subprocess("sync_defect_rework_from_2026.py", *defect_args)

    print("\n## 修复 9：联动表选项清理")
    for line in fix_linkage_disposition_options(client, dry_run):
        print(line)

    print("\n## 修复 10：班组长·待返工补救")
    leader_args = ["--dry-run"] if dry_run else []
    run_subprocess("remediate_defect_leader_view.py", *leader_args)

    if dry_run:
        print("\n[dry-run] 跳过修复后审计")
        return 0

    print("\n" + "=" * 60)
    print("## 修复后审计")
    return run_subprocess("audit_v4_comprehensive.py", "--config", str(config_path))


def main() -> int:
    p = argparse.ArgumentParser(description="V4 全面修复（日志编号保持自动编号）")
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-audit", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run, args.skip_audit, args.config)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
