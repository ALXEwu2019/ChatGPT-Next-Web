#!/usr/bin/env python3
"""重建 6 个上道批号关联字段（筛选只能在创建字段时配置）。

飞书限制：form 视图无法改关联筛选；OpenAPI 也不支持写入 link 字段筛选。
本脚本：删除旧字段 → 新建空关联列 → 输出列头创建时的筛选清单（须人工在 UI 点选）。

用法:
  python3 fix_2026_upstream_link_filters.py --dry-run
  python3 fix_2026_upstream_link_filters.py --recreate-fields
  python3 fix_2026_upstream_link_filters.py --print-manual
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config

PROD = {"STOPPER": "recyB8Z4Hljubu", "止动块": "recsxLFXuAXXI0"}
STATUS_CONFIRMED = "opt0pDHwcO"
STATUS_AUDITED = "optdqbYcV3"

UPSTREAM_SPECS = [
    {
        "field": "上道批号_STOPPER#4050",
        "form": "STOPPER#4050生产日志",
        "view_id": "vew5Rb9Urh",
        "product": "STOPPER",
        "upstream": "#2030",
        "marker": "#2030车床自动化-STOPPER",
        "pool": "P1·上道池 STOPPER#2030→#4050",
    },
    {
        "field": "上道批号_STOPPER#60",
        "form": "STOPPER#60检测机生产日志",
        "view_id": "vew121aeT9",
        "product": "STOPPER",
        "upstream": "#4050",
        "marker": "#4050磨床-STOPPER",
        "pool": "P1·上道池 STOPPER#4050→#60",
    },
    {
        "field": "上道批号_STOPPER#70",
        "form": "STOPPER#70出库填报单",
        "view_id": "vew2SbrO7V",
        "product": "STOPPER",
        "upstream": "#60",
        "marker": "#60检查机-STOPPER",
        "pool": "P1·上道池 STOPPER#60→#70",
    },
    {
        "field": "上道批号_止动块#60",
        "form": "止动块-#60检测机生产日志",
        "view_id": "vew3B1ivXN",
        "product": "止动块",
        "upstream": "#4050",
        "marker": "#4050磨床-止动块",
        "pool": "P1·上道池 止动块#4050→#60",
    },
    {
        "field": "上道批号_止动块#70",
        "form": "止动块-#70外观检生产日志",
        "view_id": "vewbP2DKMa",
        "product": "止动块",
        "upstream": "#60",
        "marker": "#60检查机-止动块",
        "pool": "P1·上道池 止动块#60→#70",
    },
    {
        "field": "上道批号_止动块#80",
        "form": "止动块-#80出库填报单",
        "view_id": "vew5WATrGc",
        "product": "止动块",
        "upstream": "#70",
        "marker": "#70外观检-止动块",
        "pool": "P1·上道池 止动块#70→#80",
    },
]


def print_manual() -> None:
    lines = [
        "# 上道批号 6 字段 — 列头重建手册（非表单里改）",
        "",
        "> **重要：** 关联「指定记录」筛选只能在 **创建单向关联字段时** 设置。",
        "> 路径：主表 **表格视图** 列头 `+` → 单向关联 → 可关联范围选 **指定记录** → 添加条件。",
        "> **不要**在表单设计器里找「筛选关联记录」（那里改不了）。",
        "",
        f"主表：`{MAIN_TABLE}` · 关联目标：**本表**（生产日志主表）",
        "",
    ]
    for i, s in enumerate(UPSTREAM_SPECS, 3):
        lines.extend(
            [
                f"## {i}. {s['field']}",
                "",
                f"- 对应表单：**{s['form']}**（`{s['view_id']}`）",
                f"- 若列已存在且无筛选：先 **删除该列** → 再 **新建** 同名单向关联",
                "- 创建向导：",
                "  1. 字段类型：**单向关联**",
                f"  2. 关联表：**生产日志主表**（自己）",
                "  3. 可关联数据范围：**指定记录**",
                "  4. 筛选条件（全部满足）：",
                f"     - **产品** = {s['product']}",
                f"     - **{s['marker']}** 包含 / 等于（该工序标记列有值）",
                "     - **工序下发状态** = 已确认 **或** 已审核",
                "  5. **勿加** 有效合格数量 > 0",
                f"- 对照视图：**{s['pool']}**（可选记录应一致）",
                "",
            ]
        )
    lines.append("完成后运行：`python3 verify_2026_p1_forms.py`")
    text = "\n".join(lines)
    print(text)


def recreate_field(client: Client, name: str, dry_run: bool) -> str:
    fields = client.list_fields(MAIN_TABLE)
    existing = next((f for f in fields if f["field_name"] == name), None)
    if dry_run:
        return f"[dry-run] delete+create {name}"
    if existing:
        fid = existing["field_id"]
        for attempt in range(3):
            resp = client.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{fid}")
            if resp.get("code") == 0:
                break
            time.sleep(2)
        else:
            return f"FAIL delete {name}: {resp.get('msg', '')}"
        time.sleep(0.5)
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields",
        json={
            "field_name": name,
            "type": 18,
            "property": {"table_id": MAIN_TABLE, "multiple": False},
        },
    )
    if resp.get("code") != 0:
        return f"FAIL create {name}: {resp.get('msg', '')}"
    new_id = resp.get("data", {}).get("field", {}).get("field_id", "?")
    return f"recreated {name} ({new_id}) — **请立即在列头编辑此列补筛选**"


def run(recreate: bool, dry_run: bool, manual_only: bool) -> int:
    if manual_only:
        print_manual()
        return 0

    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("fix_2026_upstream_link_filters")
    print("=" * 60)
    if recreate:
        for spec in UPSTREAM_SPECS:
            print(recreate_field(client, spec["field"], dry_run))
        print("\n>>> 接下来请在飞书 **表格列头** 为每个新建列配置「指定记录」筛选（见 --print-manual）")
    else:
        print("未执行重建。使用 --recreate-fields 删除并新建 6 列（筛选须人工补）")
    print_manual()
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--recreate-fields", action="store_true")
    p.add_argument("--print-manual", action="store_true")
    args = p.parse_args()
    try:
        return run(args.recreate_fields, args.dry_run, args.print_manual or not args.recreate_fields)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
