#!/usr/bin/env python3
"""2026 生产 Base P1：API 可自动化部分 + 飞书 AI 任务清单。

API 执行：
  - 管控表补 生产区域、对账差异/是否超产公式（合格合计由飞书 AI 建查找）
  - 主表 6 个「上道池」只读 grid 视图（供 form 筛选对照）
  - 管控表 2 个「首道池」grid 视图
  - 输出飞书 AI 一键 Prompt（form 关联筛选 + 合格合计查找）

用法:
  python3 remediate_2026_p1.py --dry-run
  python3 remediate_2026_p1.py --fix-all
  python3 remediate_2026_p1.py --print-feishu-ai-prompt
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config

CTRL_TABLE = "tblyvJJhyq5KoT4F"
SUM_TABLE = "tblXonlkdLxrTLXE"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "docs" / "openclaw-2026-p1-feishu-ai-execute-cn.md"

# 产品 record_id
PROD = {
    "STOPPER": "recyB8Z4Hljubu",
    "止动块": "recsxLFXuAXXI0",
    "PTJ92": "recoTeNeaQYuST",
}

# 工序 record_id（带产品后缀，与现网一致）
PROC = {
    ("STOPPER", "#2030"): "recAV0kYI0r5LS",
    ("STOPPER", "#4050"): "recpGjOr9LdIrW",
    ("STOPPER", "#60"): "recoEwR8aH1qZ2",
    ("STOPPER", "#70"): "reczlaor8Rv7vZ",
    ("止动块", "#4050"): "recv94Wg644L3s",
    ("止动块", "#60"): "rectBainbnqqi0",
    ("止动块", "#70"): "recFtCShkvImYO",
    ("止动块", "#80"): "recbaiuSiRHZ0Y",
}

STATUS_CONFIRMED = "opt0pDHwcO"
STATUS_AUDITED = "optdqbYcV3"
CTRL_ISSUED = "optuiw7Px6"  # 批号状态·已下发

# 报工 form → (字段名, 上道工序产品, 上道工序码) ；首道 upstream=None
FORM_SPECS: list[dict] = [
    {
        "form_name": "STOPPER#2030自动化生产日志",
        "view_id": "vew5XS2d4C",
        "field": "关联管控批_STOPPER#2030",
        "kind": "首道",
        "product": "STOPPER",
        "process": "#2030",
    },
    {
        "form_name": "止动块-#4050磨床生产日志",
        "view_id": "vewEah4EhT",
        "field": "关联管控批_止动块#4050",
        "kind": "首道",
        "product": "止动块",
        "process": "#4050",
    },
    {
        "form_name": "STOPPER#4050生产日志",
        "view_id": "vew5Rb9Urh",
        "field": "上道批号_STOPPER#4050",
        "kind": "下道",
        "product": "STOPPER",
        "upstream_process": "#2030",
        "marker": "#2030车床自动化-STOPPER",
    },
    {
        "form_name": "STOPPER#60检测机生产日志",
        "view_id": "vew121aeT9",
        "field": "上道批号_STOPPER#60",
        "kind": "下道",
        "product": "STOPPER",
        "upstream_process": "#4050",
        "marker": "#4050磨床-STOPPER",
    },
    {
        "form_name": "STOPPER#70出库填报单",
        "view_id": "vew2SbrO7V",
        "field": "上道批号_STOPPER#70",
        "kind": "下道",
        "product": "STOPPER",
        "upstream_process": "#60",
        "marker": "#60检查机-STOPPER",
    },
    {
        "form_name": "止动块-#60检测机生产日志",
        "view_id": "vew3B1ivXN",
        "field": "上道批号_止动块#60",
        "kind": "下道",
        "product": "止动块",
        "upstream_process": "#4050",
        "marker": "#4050磨床-止动块",
    },
    {
        "form_name": "止动块-#70外观检生产日志",
        "view_id": "vewbP2DKMa",
        "field": "上道批号_止动块#70",
        "kind": "下道",
        "product": "止动块",
        "upstream_process": "#60",
        "marker": "#60检查机-止动块",
    },
    {
        "form_name": "止动块-#80出库填报单",
        "view_id": "vew5WATrGc",
        "field": "上道批号_止动块#80",
        "kind": "下道",
        "product": "止动块",
        "upstream_process": "#70",
        "marker": "#70外观检-止动块",
    },
]

UPSTREAM_POOL_VIEWS: list[dict] = [
    {
        "name": "P1·上道池 STOPPER#2030→#4050",
        "product": "STOPPER",
        "marker": "#2030车床自动化-STOPPER",
    },
    {
        "name": "P1·上道池 STOPPER#4050→#60",
        "product": "STOPPER",
        "marker": "#4050磨床-STOPPER",
    },
    {
        "name": "P1·上道池 STOPPER#60→#70",
        "product": "STOPPER",
        "marker": "#60检查机-STOPPER",
    },
    {
        "name": "P1·上道池 止动块#4050→#60",
        "product": "止动块",
        "marker": "#4050磨床-止动块",
    },
    {
        "name": "P1·上道池 止动块#60→#70",
        "product": "止动块",
        "marker": "#60检查机-止动块",
    },
    {
        "name": "P1·上道池 止动块#70→#80",
        "product": "止动块",
        "marker": "#70外观检-止动块",
    },
]

CTRL_POOL_VIEWS: list[dict] = [
    {"name": "P1·首道池 STOPPER#2030", "product": "STOPPER", "process": "#2030"},
    {"name": "P1·首道池 止动块#4050", "product": "止动块", "process": "#4050"},
]


def list_views(client: Client, table: str) -> dict[str, str]:
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/views", params=params)["data"]
        items.extend(data["items"])
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return {v["view_name"]: v["view_id"] for v in items}


def ensure_field(client: Client, table: str, spec: dict, dry_run: bool) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(table)}
    name = spec["field_name"]
    if name in fields:
        return f"skip field: {name}"
    if dry_run:
        return f"[dry-run] create {name} type={spec['type']}"
    resp = client.call("POST", f"/bitable/v1/apps/{APP}/tables/{table}/fields", json=spec)
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} {name}: {resp.get('msg', '')}"


def ensure_formula_field(
    client: Client, table: str, name: str, expr: str, dry_run: bool
) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(table)}
    if name in fields:
        fid = fields[name]["field_id"]
        if dry_run:
            return f"[dry-run] update formula {name}"
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{table}/fields/{fid}",
            json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
        )
        ok = resp.get("code") == 0
        return f"{'updated' if ok else 'FAIL'} formula {name}: {resp.get('msg', '')}"
    if dry_run:
        return f"[dry-run] create formula {name}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/fields",
        json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
    )
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} formula {name}: {resp.get('msg', '')}"


def patch_view_filter(
    client: Client,
    table: str,
    view_id: str,
    conditions: list[dict],
    conjunction: str = "and",
    dry_run: bool = False,
) -> str:
    if dry_run:
        return f"[dry-run] filter {view_id} ({len(conditions)} conds)"
    resp = client.call(
        "PATCH",
        f"/bitable/v1/apps/{APP}/tables/{table}/views/{view_id}",
        json={"property": {"filter_info": {"conjunction": conjunction, "conditions": conditions}}},
    )
    ok = resp.get("code") == 0
    return f"{'filter ok' if ok else 'FAIL filter'} {view_id}: {resp.get('msg', '')}"


def ensure_grid_view(
    client: Client, table: str, name: str, existing: dict[str, str], dry_run: bool
) -> tuple[str, str | None]:
    if name in existing:
        return f"skip view: {name}", existing[name]
    if dry_run:
        return f"[dry-run] create view {name}", None
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{table}/views",
        json={"view_name": name, "view_type": "grid"},
    )
    vid = resp.get("data", {}).get("view", {}).get("view_id")
    ok = resp.get("code") == 0
    return f"{'created' if ok else 'FAIL'} view {name}: {resp.get('msg', '')}", vid


def setup_control_schema(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    lines.append(
        ensure_field(
            client,
            CTRL_TABLE,
            {"field_name": "生产区域", "type": 1},
            dry_run,
        )
    )
    fields = {f["field_name"]: f["field_id"] for f in client.list_fields(CTRL_TABLE)}
    if "合格合计" not in fields:
        lines.append("skip formulas: 合格合计 尚未创建（飞书 AI 任务 B 建查找引用后再跑本脚本）")
        return lines

    qf_id = fields["合格合计"]
    qty_id = fields["本工序下发数量"]
    diff_expr = (
        f"bitable::$table[{CTRL_TABLE}].$field[{qf_id}]"
        f"-bitable::$table[{CTRL_TABLE}].$field[{qty_id}]"
    )
    lines.append(ensure_formula_field(client, CTRL_TABLE, "对账差异", diff_expr, dry_run))

    fields = {f["field_name"]: f["field_id"] for f in client.list_fields(CTRL_TABLE)}
    dd_id = fields.get("对账差异", "fldDIFF")
    over_expr = f"bitable::$table[{CTRL_TABLE}].$field[{dd_id}]>0"
    lines.append(ensure_formula_field(client, CTRL_TABLE, "是否超产", over_expr, dry_run))
    return lines


def marker_option_id(client: Client, marker_name: str) -> str:
    fields = {f["field_name"]: f for f in client.list_fields(MAIN_TABLE)}
    field = fields[marker_name]
    opts = field.get("property", {}).get("options", [])
    if not opts:
        raise KeyError(f"no options on {marker_name}")
    # 单选项通常只有一个工序标记值
    for o in opts:
        if o.get("name") == marker_name or len(opts) == 1:
            return o["id"]
    return opts[0]["id"]


def build_upstream_conditions(client: Client, spec: dict) -> list[dict]:
    fields = {f["field_name"]: f for f in client.list_fields(MAIN_TABLE)}
    prod_fid = fields["产品"]["field_id"]
    status_fid = fields["工序下发状态"]["field_id"]
    marker_name = spec["marker"]
    marker_fid = fields[marker_name]["field_id"]
    opt_id = marker_option_id(client, marker_name)
    product_rid = PROD[spec["product"]]
    return [
        {
            "field_id": prod_fid,
            "field_type": 18,
            "operator": "is",
            "value": json.dumps([product_rid]),
        },
        {
            "field_id": marker_fid,
            "field_type": 3,
            "operator": "contains",
            "value": json.dumps([opt_id]),
        },
        {
            "field_id": status_fid,
            "field_type": 3,
            "operator": "is",
            "value": json.dumps([STATUS_CONFIRMED]),
        },
    ]


def build_ctrl_pool_conditions(client: Client, spec: dict) -> list[dict]:
    fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}
    prod_fid = fields["产品"]["field_id"]
    proc_fid = fields["工序代码"]["field_id"]
    st_fid = fields["批号状态"]["field_id"]
    return [
        {
            "field_id": prod_fid,
            "field_type": 18,
            "operator": "is",
            "value": json.dumps([PROD[spec["product"]]]),
        },
        {
            "field_id": proc_fid,
            "field_type": 18,
            "operator": "is",
            "value": json.dumps([PROC[(spec["product"], spec["process"])]]),
        },
        {
            "field_id": st_fid,
            "field_type": 3,
            "operator": "is",
            "value": json.dumps([CTRL_ISSUED]),
        },
    ]


def setup_pool_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    main_views = list_views(client, MAIN_TABLE)
    ctrl_views = list_views(client, CTRL_TABLE)

    for spec in UPSTREAM_POOL_VIEWS:
        msg, vid = ensure_grid_view(client, MAIN_TABLE, spec["name"], main_views, dry_run)
        lines.append(msg)
        if vid:
            main_views[spec["name"]] = vid
        use_vid = vid or main_views.get(spec["name"])
        if use_vid:
            try:
                conds = build_upstream_conditions(client, spec)
                lines.append(patch_view_filter(client, MAIN_TABLE, use_vid, conds, dry_run=dry_run))
            except KeyError as e:
                lines.append(f"FAIL filter {spec['name']}: missing field {e}")

    for spec in CTRL_POOL_VIEWS:
        msg, vid = ensure_grid_view(client, CTRL_TABLE, spec["name"], ctrl_views, dry_run)
        lines.append(msg)
        if vid:
            ctrl_views[spec["name"]] = vid
        use_vid = vid or ctrl_views.get(spec["name"])
        if use_vid:
            conds = build_ctrl_pool_conditions(client, spec)
            lines.append(patch_view_filter(client, CTRL_TABLE, use_vid, conds, dry_run=dry_run))

    return lines


def build_feishu_ai_prompt(client: Client) -> str:
    fields_main = {f["field_name"]: f["field_id"] for f in client.list_fields(MAIN_TABLE)}

    form_lines: list[str] = []
    for s in FORM_SPECS:
        if s["kind"] == "首道":
            form_lines.append(
                f"- **{s['form_name']}** (`{s['view_id']}`) → 字段 **{s['field']}** "
                f"(`{fields_main.get(s['field'], '?')}`)\n"
                f"  - 关联表：入库批次管控表 `{CTRL_TABLE}`\n"
                f"  - 筛选：产品={s['product']}（`{PROD[s['product']]}`）；"
                f"工序={s['process']}（`{PROC[(s['product'], s['process'])]}`）；"
                f"批号状态=**已下发**（option `{CTRL_ISSUED}`）\n"
                f"  - 对照只读视图：**P1·首道池 {s['product']}{s['process']}**"
            )
        else:
            pool_map = {
                ("STOPPER", "#2030"): "P1·上道池 STOPPER#2030→#4050",
                ("STOPPER", "#4050"): "P1·上道池 STOPPER#4050→#60",
                ("STOPPER", "#60"): "P1·上道池 STOPPER#60→#70",
                ("止动块", "#4050"): "P1·上道池 止动块#4050→#60",
                ("止动块", "#60"): "P1·上道池 止动块#60→#70",
                ("止动块", "#70"): "P1·上道池 止动块#70→#80",
            }
            pool = pool_map.get((s["product"], s["upstream_process"]), "上道池视图")
            form_lines.append(
                f"- **{s['form_name']}** (`{s['view_id']}`) → 字段 **{s['field']}** "
                f"(`{fields_main.get(s['field'], '?')}`)\n"
                f"  - 关联表：生产日志主表 `{MAIN_TABLE}`\n"
                f"  - 筛选：产品={s['product']}；上道工序={s['upstream_process']}（marker `{s['marker']}`）；"
                f"工序下发状态=**已确认**或**已审核**（option `{STATUS_CONFIRMED}` / `{STATUS_AUDITED}`）\n"
                f"  - **勿加** 有效合格数量>0\n"
                f"  - 对照只读视图：**{pool}**"
            )

    return f"""# 飞书 AI · 2026 生产 Base P1 执行单（一键粘贴）

> Base `NiyZbKpKfae9x3sUP64cl9SFnRb` · P0 已完成，请在本 Base **仅做下列配置**，勿删字段/数据。

---

## 任务 A — 8 个报工 form 的关联筛选（per-view 字段）

打开 **生产日志主表** `tblSw8eYEpe7y1am` → 进入下列 **表单视图** → 点击对应关联字段 → **编辑字段** → **筛选关联记录** → 满足所有条件：

{chr(10).join(form_lines)}

> 说明：首道选 **管控表**；下道选 **主表** 上道已确认行。OpenAPI 无法写入 form 筛选，必须在表单设计器完成。

---

## 任务 B — 管控表「合格合计」查找引用（4 条件）

表：**入库批次管控表** `tblyvJJhyq5KoT4F`

1. 若无列 **合格合计**：新增字段 → 类型 **查找引用**
2. 设置：
   - 关联表：**批工序产量汇总表** `tblXonlkdLxrTLXE`
   - 引用字段：**合格合计**（`fld58R4m10`）
   - 计算方式：**原值**
3. 匹配条件（4 条，全部满足）：

| # | 管控表字段 | 运算符 | 汇总表字段 |
|---|-----------|--------|-----------|
| 1 | 批号文本 (`fldTG0SeXm`) | 等于 | 批号文本 (`fldQGAT11f`) |
| 2 | 产品 (`fldqCtMsEG`) | 等于 | 产品 (`fldNo5CK16`) |
| 3 | 工序代码 (`fldkyrhKt4`) | 等于 | 工序代码 (`fldisD5ip1`) |
| 4 | 生产区域 | 等于 | 生产区域 (`fldduXaag5`) |

> #2030 行管控表 **生产区域** 可留空；#4050 止动块 MG02/MG03 行须填生产区域与汇总一致。

4. 保存后检查管控表 `S-260617-A` 等行是否出现合格合计数字。

---

## 任务 C — 公式列

在管控表确认存在（任务 B 完成后）：
- **对账差异** = `合格合计 - 本工序下发数量`
- **是否超产** = `对账差异 > 0`

完成后在服务器执行：`python3 remediate_2026_p1.py --fix-all`（自动补公式）

---

## 任务 D — 验收

1. 打开 **P1·首道池** / **P1·上道池** 视图，确认与 form 筛选一致
2. 管理视图 `vewQqWVrxH` 看管控对账
3. 汇总 cron：`sync_batch_summary.py --config config.2026.json`（每天 8/12/20 点）

---

## 禁止

- 勿新建汇总公式列（`#4050汇总*` 等）
- 勿把「已报工」计入汇总（仅 **已确认/已审核**）
- 勿删除 per-view 字段

*生成：`remediate_2026_p1.py`*
"""


def write_prompt(client: Client) -> Path:
    PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROMPT_PATH.write_text(build_feishu_ai_prompt(client) + "\n", encoding="utf-8")
    return PROMPT_PATH


def run(dry_run: bool, prompt_only: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    if prompt_only:
        path = write_prompt(client)
        print(build_feishu_ai_prompt(client))
        print(f"\n已写入 {path}")
        return 0

    print("remediate_2026_p1")
    print("=" * 60)

    print("\n## 管控表 schema")
    for line in setup_control_schema(client, dry_run):
        print(line)

    print("\n## 上道池 / 首道池视图")
    for line in setup_pool_views(client, dry_run):
        print(line)

    path = write_prompt(client)
    print(f"\n## 飞书 AI 执行单\n已写入 {path}")
    print("请在飞书多维表格 AI 助手粘贴该文件全文完成任务 A/B。")

    print("=" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix-all", action="store_true")
    p.add_argument("--print-feishu-ai-prompt", action="store_true")
    args = p.parse_args()
    if not any((args.dry_run, args.fix_all, args.print_feishu_ai_prompt)):
        p.error("specify --fix-all, --dry-run, or --print-feishu-ai-prompt")
    try:
        return run(args.dry_run, args.print_feishu_ai_prompt)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
