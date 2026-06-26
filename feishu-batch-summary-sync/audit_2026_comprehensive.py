#!/usr/bin/env python3
"""2026 生产 Base 全面审计：表 / 视图 / 表单 / 流程 / v4 对照。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from remediate_2026_summary import APP, Client, load_2026_config
from sync_batch_summary import extract_text

MAIN = "tblSw8eYEpe7y1am"
SUM = "tblXonlkdLxrTLXE"
CONTROL = "tblyvJJhyq5KoT4F"
DEFECT = "tblTk6xVopyoCjOF"
REWORK = "tblINpP7IJ67h4d9"
LINKAGE = "tblABIgbureAlcnU"
REASON = "tblrQW6JouoEEMGn"
TRACE = "tblpmo5ta3EBOGMw"

FIELD_TYPE = {
    1: "文本", 2: "数字", 3: "单选", 4: "多选", 5: "日期", 7: "复选框",
    11: "人员", 13: "电话", 15: "超链接", 17: "附件", 18: "关联", 19: "查找",
    20: "公式", 21: "双向关联", 22: "地理位置", 23: "群组", 1001: "自动编号",
    1002: "创建时间", 1003: "修改时间", 1004: "创建人", 1005: "修改人",
}

VIEW_TYPE = {1: "grid", 2: "kanban", 3: "gallery", 4: "gantt", 5: "form", 6: "calendar"}

FORBIDDEN = {
    "#4050汇总批号", "#4050汇总合格合计", "#4050本汇总剩余可用数", "#4050数量校验",
    "#4050本汇总剩余可用数 (1)", "#4050数量校验 (1)", "#60汇总批号", "#60汇总合格合计",
    "#4050选择上道汇总", "#60选择上道汇总", "车床简化批号", "汇总批工序键",
}

MISTAKEN_PER_VIEW = {
    "关联管控批_STOPPER#2030", "关联管控批_止动块#4050",
    "上道批号_STOPPER#4050", "上道批号_STOPPER#60", "上道批号_STOPPER#70",
    "上道批号_止动块#60", "上道批号_止动块#70", "上道批号_止动块#80",
}

LEGACY_BATCH = {"生产批号-输入", "（磨床）上道生产记录", "（检测）上道生产记录"}

OPERATOR_VIEWS = {
    "vewK5AzZee": ("STOPPER-#2030报工", "首道", "生产批号-输入"),
    "vewEah4EhT": ("止动块-#4050", "首道", "生产批号-输入"),
    "vew5Rb9Urh": ("STOPPER#4050生产日志", "下道", "（磨床）上道生产记录"),
    "vew121aeT9": ("STOPPER#60", "下道", "（检测）上道生产记录"),
    "vew2SbrO7V": ("STOPPER#70", "下道", "（检测）上道生产记录"),
    "vew3B1ivXN": ("止动块#60", "下道", "（磨床）上道生产记录"),
    "vewbP2DKMa": ("止动块#70", "下道", "（检测）上道生产记录"),
    "vew5WATrGc": ("止动块#80", "下道", "（检测）上道生产记录"),
}

DEFECT_FORMS = {
    "vewKLH2HSb": "品保·不良明细录入",
    "vewDhjhzdx": "班组长·返工完成登记",
    "vew7embFn1": "品保·确认完成单",
}


def list_tables(client: Client) -> list[dict]:
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables", params=params)["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def list_views(client: Client, table: str) -> list[dict]:
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/views", params=params)["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def view_detail(client: Client, table: str, view_id: str) -> dict:
    return client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/views/{view_id}").get("data", {})


def count_records(client: Client, table: str) -> int:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/records", params={"page_size": 1})
    return data.get("data", {}).get("total", 0)


def fmt_filter(cond: dict) -> str:
    parts = []
    for c in cond.get("conditions", []):
        field = c.get("field_id", c.get("field_name", "?"))
        op = c.get("operator", "?")
        val = c.get("value", "")
        parts.append(f"{field} {op} {val}")
    return " AND ".join(parts) if parts else "(无)"


def audit_tables(client: Client) -> list[str]:
    lines = ["\n## 1. Base 表清单\n", "| 表名 | table_id | 行数 | 主字段 |", "| --- | --- | ---: | --- |"]
    for t in list_tables(client):
        tid = t["table_id"]
        n = count_records(client, tid)
        lines.append(f"| {t.get('name', '?')} | `{tid}` | {n} | {t.get('revision', '')} |")
    return lines


EXPECTED_UPSTREAM_TARGET = MAIN  # 下道应关联主表已确认行
WRONG_UPSTREAM_TARGETS = {SUM, CONTROL}

def audit_main_fields(client: Client) -> list[str]:
    fields = client.list_fields(MAIN)
    names = {f["field_name"] for f in fields}
    visible = [f for f in fields if not f.get("is_hidden")]
    hidden = [f for f in fields if f.get("is_hidden")]

    lines = [
        f"\n## 2. 主表字段 ({len(fields)} 总 / {len(visible)} 可见 / {len(hidden)} 隐藏)\n",
    ]

    # 批号模型判定
    has_legacy = LEGACY_BATCH & names
    has_per_view = {n for n in names if n.startswith("关联管控批_") or n.startswith("上道批号_")}
    if has_per_view and has_legacy:
        model = "双轨混用（严重）"
    elif has_per_view:
        model = "V4 per-view 模型"
    elif has_legacy:
        model = "旧库三轨模型"
    else:
        model = "未识别批号字段"
    lines.append(f"**批号模型：** {model}")
    lines.append(f"- 旧库三轨: {', '.join(sorted(has_legacy)) or '无'}")
    lines.append(f"- per-view: {len(has_per_view)} 个 ({', '.join(sorted(has_per_view)[:5])}{'…' if len(has_per_view)>5 else ''})")

    forbidden_vis = [f["field_name"] for f in visible if f["field_name"] in FORBIDDEN]
    if forbidden_vis:
        lines.append(f"- [FAIL] 禁止字段仍可见: {', '.join(forbidden_vis)}")

    fmap = {f["field_name"]: f for f in fields}
    mistaken = names & MISTAKEN_PER_VIEW
    if mistaken:
        lines.append(f"- [WARN] 文档标为误加的 per-view: {', '.join(sorted(mistaken))}")

    # 上道批号关联目标
    wrong_links = []
    for f in fields:
        n = f["field_name"]
        if not n.startswith("上道批号_") or f["type"] != 18:
            continue
        tgt = (f.get("property") or {}).get("table_id", "")
        if tgt != EXPECTED_UPSTREAM_TARGET:
            wrong_links.append(f"{n} → `{tgt}`")
    if wrong_links:
        lines.append(f"- [FAIL] 上道批号关联目标错误（应为主表 `{MAIN}`）:")
        for w in wrong_links:
            lines.append(f"  - {w}")

    st = fmap.get("工序下发状态")
    if st:
        opts = [o["name"] for o in (st.get("property") or {}).get("options", [])]
        if "已确认" not in opts:
            lines.append(f"- [FAIL] 工序下发状态缺「已确认」（当前: {', '.join(opts)}）；sync 配置认 已确认/已审核")
        lines.append(f"- 状态选项: {', '.join(opts)}")

    bt = fmap.get("批号文本")
    if bt and bt.get("type") == 20:
        expr = (bt.get("property") or {}).get("formula_expression", "")
        if "关联管控批次" in expr or "fldQSSF2kt" in expr:
            lines.append("- [WARN] `批号文本` 公式依赖 `关联管控批次`；若该列链接为空则多数行批号为空（应改指向 `生产批号-手动输入栏` 或 per-view 管控字段）")

    # 关键字段
    lines.append("\n| 关键字段 | 类型 | 状态 |")
    lines.append("| --- | --- | --- |")
    key_fields = [
        "批号文本", "生产批号", "工序代码", "工序名称", "工序下发状态",
        "有效合格数量", "有效报废数量", "完整追溯号", "生产区域", "生产区域_自动计算",
    ]
    for k in key_fields:
        f = fmap.get(k)
        if not f:
            lines.append(f"| {k} | — | **缺失** |")
            continue
        t = FIELD_TYPE.get(f["type"], str(f["type"]))
        st = "隐藏" if f.get("is_hidden") else "可见"
        if f["type"] == 20 and f.get("property", {}).get("formula"):
            formula = f["property"]["formula"][:60].replace("\n", " ")
            st += f" · `{formula}…`"
        lines.append(f"| {k} | {t} | {st} |")

    return lines


def audit_main_views(client: Client) -> list[str]:
    views = list_views(client, MAIN)
    lines = [
        f"\n## 3. 主表视图 ({len(views)} 个)\n",
        "| 视图名 | view_id | 类型 | 角色 | 批号字段 | 隐藏列数 | 筛选摘要 |",
        "| --- | --- | --- | --- | --- | ---: | --- |",
    ]

    grid_views = []
    form_views = []
    for v in views:
        vid = v["view_id"]
        vname = v.get("view_name", "?")
        vtype = VIEW_TYPE.get(v.get("view_type", 0), str(v.get("view_type")))
        try:
            detail = view_detail(client, MAIN, vid)
        except Exception:
            detail = {}
        hidden = detail.get("property", {}).get("hidden_fields") or []
        filters = detail.get("property", {}).get("filter_info") or {}

        role = "管理/其他"
        batch_field = "—"
        if vid == "vewQqWVrxH":
            role = "管理"
        elif vid in OPERATOR_VIEWS:
            spec = OPERATOR_VIEWS[vid]
            role = f"操作工·{spec[1]}"
            batch_field = spec[2]
        elif "班组长" in vname or "品保" in vname or "返工" in vname:
            role = "班组长/品保"
        elif "PTJ92" in vname or "#40" in vname or "#50" in vname:
            role = "废弃/P2"

        filt_str = fmt_filter(filters) if filters else "(视图级无/未返回)"
        lines.append(
            f"| {vname} | `{vid}` | {vtype} | {role} | {batch_field} | {len(hidden)} | {filt_str[:80]} |"
        )
        if vtype == "grid":
            grid_views.append(v)
        elif vtype == "form":
            form_views.append(v)

    lines.append(f"\n- grid: {len(grid_views)} · form: {len(form_views)}")
    missing_op = [vid for vid in OPERATOR_VIEWS if vid not in {v["view_id"] for v in views}]
    if missing_op:
        lines.append(f"- [FAIL] 缺失报工视图: {missing_op}")

    return lines


def audit_workflow(client: Client) -> list[str]:
    main_recs = client.list_records(MAIN)
    status_cnt = Counter(extract_text(r.get("fields", {}).get("工序下发状态")) for r in main_recs)
    empty_bt = sum(1 for r in main_recs if not extract_text(r.get("fields", {}).get("批号文本")))

    lines = [
        f"\n## 4. 生产报工流程（主表 {len(main_recs)} 行）\n",
        "### 4.1 工序下发状态分布\n",
        "| 状态 | 行数 | 汇总/上道 |",
        "| --- | ---: | --- |",
    ]
    sync_ok = {"已确认", "已审核"}
    for st, cnt in status_cnt.most_common():
        note = "计入汇总、可作上道" if st in sync_ok else "不计汇总（默认）"
        lines.append(f"| {st or '(空)'} | {cnt} | {note} |")
    if empty_bt:
        lines.append(f"\n- [FAIL] `批号文本` 为空: **{empty_bt}/{len(main_recs)}** 行（汇总键无法聚合）")

    # 批号填充率
    fields = {f["field_name"]: f for f in client.list_fields(MAIN)}
    batch_checks = []
    for fname in sorted(LEGACY_BATCH | MISTAKEN_PER_VIEW):
        if fname not in fields:
            continue
        filled = sum(1 for r in main_recs if r.get("fields", {}).get(fname))
        batch_checks.append((fname, filled, len(main_recs)))
    if batch_checks:
        lines.extend(["\n### 4.2 批号字段填充率\n", "| 字段 | 已填 | 总行 |", "| --- | ---: | ---: |"])
        for fname, filled, total in batch_checks:
            lines.append(f"| {fname} | {filled} | {total} |")

    lines.extend([
        "\n### 4.3 标准流程（v4 定稿）\n",
        "```",
        "管控批(已下发) → 首道报工(生产批号-输入) → 已报工",
        "  → 不良登记(可选) → 返工回填 → 品保确认 → 已确认",
        "  → sync_batch_summary → 汇总表",
        "下道: 上道生产记录(已确认/已审核行) → 本道报工 → …",
        "```",
    ])
    return lines


def audit_defect_rework(client: Client) -> list[str]:
    lines = ["\n## 5. 不良 / 返工流程\n"]

    for label, tid in [("不良明细", DEFECT), ("返工完成", REWORK)]:
        fields = client.list_fields(tid)
        recs = client.list_records(tid)
        lines.append(f"### {label} (`{tid}`) — {len(fields)} 字段 / {len(recs)} 行\n")
        status_f = next((f for f in fields if f["field_name"] == "状态"), None)
        if status_f and status_f["type"] == 3:
            opts = [o["name"] for o in status_f.get("property", {}).get("options", [])]
            lines.append(f"- 状态选项: {', '.join(opts)}")
            if recs:
                cnt = Counter(extract_text(r.get("fields", {}).get("状态")) for r in recs)
                lines.append(f"- 分布: {dict(cnt)}")

    # 表单入口
    for table, forms_map in [(DEFECT, DEFECT_FORMS), (REWORK, {})]:
        views = list_views(client, table)
        form_views = [v for v in views if VIEW_TYPE.get(v.get("view_type")) == "form"]
        if form_views or forms_map:
            lines.append(f"\n**{table} 表单视图：**")
            for v in form_views:
                lines.append(f"- {v.get('view_name')} (`{v['view_id']}`)")

    lines.extend([
        "\n### 不良流程状态机（目标）\n",
        "```",
        "品保录入不良 → 待返工 → 班组长返工完成 → 待品保确认 → 已确认",
        "主表: 已报工 → 待返工 → 待品保确认 → 已确认",
        "```",
    ])

    linkage_n = count_records(client, LINKAGE)
    reason_n = count_records(client, REASON)
    lines.append(f"\n- 不良联动规则: {linkage_n} 行 · 不良原因库: {reason_n} 条")
    return lines


def audit_summary_control(client: Client) -> list[str]:
    lines = ["\n## 6. 汇总与管控对账\n"]

    sum_fields = {f["field_name"]: f for f in client.list_fields(SUM)}
    sum_recs = client.list_records(SUM)
    lines.append(f"**汇总表** `{SUM}`: {len(sum_fields)} 字段 / {len(sum_recs)} 行")
    legacy_sum = [n for n in ("汇总批号", "关联生产记录", "末次更新时间") if n in sum_fields]
    if legacy_sum:
        lines.append(f"- [WARN] 遗留字段: {', '.join(legacy_sum)}")
    dup_sync = sum(1 for r in sum_recs if not extract_text(r.get("fields", {}).get("同步批次号")))
    if dup_sync:
        lines.append(f"- [WARN] 无同步批次号: {dup_sync} 行")

    ctrl_fields = {f["field_name"]: f for f in client.list_fields(CONTROL)}
    ctrl_n = count_records(client, CONTROL)
    lines.append(f"\n**管控表** `{CONTROL}`: {len(ctrl_fields)} 字段 / {ctrl_n} 行")
    for want in ("批号文本", "工序代码", "合格合计", "本工序下发数量", "批号状态"):
        st = "✓" if want in ctrl_fields else "**缺**"
        lines.append(f"- {want}: {st}")

    # 主表 vs 汇总对账抽样
    main_ok = [
        r for r in client.list_records(MAIN)
        if extract_text(r.get("fields", {}).get("工序下发状态")) in ("已确认", "已审核")
    ]
    lines.append(f"\n- 主表可汇总行: {len(main_ok)} · 汇总表行: {len(sum_recs)}")

    return lines


def audit_config_tables(client: Client, cfg: dict) -> list[str]:
    lines = ["\n## 7. L0 配置表\n", "| 表 | 行数 | 备注 |", "| --- | ---: | --- |"]

    lt = cfg.get("link_tables", {})
    for label, key in [("产品", "product"), ("工序", "process"), ("管控", "control")]:
        spec = lt.get(key, {})
        tid = spec.get("table_id", "")
        if not tid:
            continue
        n = count_records(client, tid)
        note = ""
        if key == "process" and n > 10:
            note = "工序行数偏多，建议去产品后缀"
        lines.append(f"| {label} | {n} | {note} |")

    trace_n = count_records(client, TRACE)
    lines.append(f"| 产品追溯规则 | {trace_n} | schema 可能与 v4 不一致 |")
    return lines


def optimization_plan(client: Client, cfg: dict) -> list[str]:
    fields = {f["field_name"]: f for f in client.list_fields(MAIN)}
    names = set(fields)
    has_legacy = LEGACY_BATCH & names
    has_per_view = {n for n in names if n.startswith("关联管控批_") or n.startswith("上道批号_")}
    main_recs = client.list_records(MAIN)
    reported = sum(1 for r in main_recs if extract_text(r.get("fields", {}).get("工序下发状态")) == "已报工")

    lines = [
        "\n## 8. 优化方案（P0 / P1 / P2）\n",
        "### P0 — 阻断数据与双轨混用\n",
    ]

    empty_bt = sum(1 for r in main_recs if not extract_text(r.get("fields", {}).get("批号文本")))
    wrong_up = [
        f["field_name"]
        for f in client.list_fields(MAIN)
        if f["field_name"].startswith("上道批号_")
        and f.get("type") == 18
        and (f.get("property") or {}).get("table_id") != MAIN
    ]
    st_field = next(f for f in client.list_fields(MAIN) if f["field_name"] == "工序下发状态")
    st_opts = [o["name"] for o in (st_field.get("property") or {}).get("options", [])]

    p0 = []
    if wrong_up:
        p0.append(
            f"**修复上道批号关联表**：{len(wrong_up)} 个字段误指向汇总表/管控表（应全部指向主表 `{MAIN}` 的已确认行）。"
        )
    if empty_bt > len(main_recs) // 2:
        p0.append(
            f"**修复批号文本公式**：{empty_bt}/{len(main_recs)} 行批号为空；将公式改为引用 `生产批号-手动输入栏` 或有效的 per-view 管控字段，并清理空壳 `关联管控批次` 链接。"
        )
    if "已确认" not in st_opts:
        p0.append("**恢复「已确认」状态选项**（或把 sync 配置改为只认「已审核」）；当前缺选项导致脚本与文档不一致。")
    if has_legacy and has_per_view:
        p0.append("**统一批号模型（二选一）**：现网同时存在旧库三轨与 per-view 字段，操作工易填错列；建议保留 **旧库三轨**（文档已定稿）并删除/隐藏 8 个 per-view 字段，或全量迁移 V4 per-view 并删除三轨字段。")
    elif has_per_view and not has_legacy:
        p0.append(
            "**确认 per-view 定稿**：旧库三轨已移除，现以 per-view + `生产批号-手动输入栏` 为准；需同步更新 P1 手册与 form 筛选（勿再写 `生产批号-输入`/`上道生产记录`）。"
        )
    if reported > 0:
        p0.append(f"**状态收敛**：{reported} 行仍为「已报工」，不计入汇总且不可作上道；品保验收后改「已确认」或「已审核」。")
    forbidden_vis = [n for n in FORBIDDEN if n in names and not fields[n].get("is_hidden")]
    if forbidden_vis:
        p0.append(f"**删除/隐藏禁止汇总列**：{', '.join(forbidden_vis)}")
    proc = fields.get("工序代码", {})
    if proc.get("type") == 20:
        p0.append("**工序代码改关联(18)** 或确保公式 LIST 引用字段存在；否则 sync 聚合键为空。")

    if not p0:
        p0.append("无 P0 阻断项（仍建议复核表单筛选）。")
    for i, item in enumerate(p0, 1):
        lines.append(f"{i}. {item}")

    lines.extend([
        "\n### P1 — 表单 / 视图 / 对账（多需飞书界面）\n",
        "1. **8 个报工 form 视图**：按 **现网 per-view 字段** 配置关联筛选（首道→管控表已下发；下道→**主表**已确认/已审核行）。勿再引用已删除的 `生产批号-输入`/`上道生产记录`。",
        "2. **管理视图** `vewQqWVrxH`：仅保留管控/对账列；隐藏 per-view 与横向区域列。",
        "3. **管控表合格合计**：四条件查找引用汇总表 `合格合计`（见 `docs/feishu-lookup-qualified-total-cn.md`）。",
        "4. **cron**：`sync_batch_summary.py --config config.2026.json` 每 15–30 分钟。",
        "5. **不良三张表单** `vewKLH2HSb` / `vewDhjhzdx` / `vew7embFn1`：核对字段必填与状态联动。",
        "\n### P2 — 结构对齐绿场\n",
        "1. 工序表去产品后缀 → ≤10 行通用码；路线走 `产品工序对照表`。",
        "2. 产品追溯规则表升级（`需要追溯号` + 工序关联）以支撑 `完整追溯号` 公式。",
        "3. PTJ92 / #40 / #50 视图保持隐藏直至 P2 路线启用。",
        "4. 长期：数据稳定后迁移至 Wiki 绿场 Base。",
        "\n### 可 API 自动化 vs 手工\n",
        "| 动作 | 方式 | 脚本 |",
        "| --- | --- | --- |",
        "| 汇总修复/去重 | API | `remediate_2026_summary.py` |",
        "| 主表字段隐藏/公式修复 | API | `remediate_production_base.py`, `fix_2026_process_formulas.py` |",
        "| 已报工→已确认 | API | `remediate_2026_comprehensive.py` |",
        "| form 关联筛选 | **手工** | 飞书界面 |",
        "| 管控合格合计查找 | **手工** | 飞书界面 |",
        "| 自动化/机器人 | 审计外 | 需在飞书「自动化」面板核对 |",
    ])
    return lines


def audit_forms_workflows() -> list[str]:
    return [
        "\n## 9. 表单与角色入口全景\n",
        "### 9.1 生产报工（主表 form）\n",
        "| 表单 | view_id | 工序 | 首道/下道 | 应填批号字段（现网） |",
        "| --- | --- | --- | --- | --- |",
        "| STOPPER#2030自动化生产日志 | `vew5XS2d4C` | #2030 | 首道 | `关联管控批_STOPPER#2030` 或 `生产批号-手动输入栏` |",
        "| 止动块-#4050磨床生产日志 | `vewEah4EhT` | #4050 | 首道 | `关联管控批_止动块#4050` |",
        "| STOPPER#4050生产日志 | `vew5Rb9Urh` | #4050 | 下道 | `上道批号_STOPPER#4050`（**须改关联主表**） |",
        "| STOPPER#60检测机生产日志 | `vew121aeT9` | #60 | 下道 | `上道批号_STOPPER#60` |",
        "| STOPPER#70出库填报单 | `vew2SbrO7V` | #70 | 下道 | `上道批号_STOPPER#70` |",
        "| 止动块-#60检测机生产日志 | `vew3B1ivXN` | #60 | 下道 | `上道批号_止动块#60` |",
        "| 止动块-#70外观检生产日志 | `vewbP2DKMa` | #70 | 下道 | `上道批号_止动块#70` |",
        "| 止动块-#80出库填报单 | `vew5WATrGc` | #80 | 下道 | `上道批号_止动块#80` |",
        "| 操作工扫码报工 | `vewT17PaSC` | 通用 | — | 待定义 |",
        "\n> **文档漂移**：`docs/feishu-p1-manual-setup-2026-cn.md` 仍写 `生产批号-输入`/`上道生产记录`，与现网 schema 不符，P1 须改版。\n",
        "### 9.2 不良 / 返工（独立表 form）\n",
        "| 角色 | 表单 | view_id | 所在表 |",
        "| --- | --- | --- | --- |",
        "| 品保 | 【品保·返工品录入】不良明细录入清单 | `vewKLH2HSb` | 不良明细 |",
        "| 品保 | 【品保·返工完成品录入】返工完成品录入清单 | `vewCsBeIdh` | 不良明细 |",
        "| 班组长 | 【班组长操作】返工完成登记表 | `vewDhjhzdx` | 返工完成 |",
        "| 品保 | 【品保操作】品保确认完成单 | `vew7embFn1` | 返工完成 |",
        "\n### 9.3 管理 / 核对（grid）\n",
        "| 视图 | view_id | 用途 |",
        "| --- | --- | --- |",
        "| 【管理视图】生产批次管控表 | `vewQqWVrxH` | **用户主入口**：批次对账、状态总览 |",
        "| 【班长长】待班组长核审视图 | `vew2Ywj6NI` | 班组长审核 |",
        "| 【总表】审计导出 | `vewhrakZZD` | 导出审计 |",
        "\n## 10. 端到端流程图\n",
        "```mermaid",
        "flowchart LR",
        "  subgraph L1[入库管控]",
        "    C[管控批 已下发]",
        "  end",
        "  subgraph L2[首道报工 form]",
        "    F1[关联管控批_*]",
        "    M[主表行 已报工]",
        "  end",
        "  subgraph L3[不良可选]",
        "    D[不良明细 form]",
        "    R[返工完成 form]",
        "    Q[品保确认]",
        "  end",
        "  subgraph L4[汇总]",
        "    S[sync脚本]",
        "    SUM[批工序产量汇总]",
        "  end",
        "  subgraph L5[下道 form]",
        "    U[上道批号_* 主表已确认行]",
        "    M2[本道报工]",
        "  end",
        "  C --> F1 --> M",
        "  M --> D --> R --> Q",
        "  Q -->|已确认/已审核| S --> SUM",
        "  SUM -.误配.-> U",
        "  U --> M2",
        "```",
        "\n**现网断点（红字逻辑）**：",
        "- 上道批号 7/8 指向汇总表或管控表 → 下道选批逻辑错误",
        "- 批号文本 25/28 为空 → 汇总键断裂",
        "- 缺「已确认」状态 → 与 sync 配置不一致",
        "- 管控表无合格合计查找 → 无法对账剩余可用数",
    ]


def run(client: Client, cfg: dict) -> str:
    sections = []
    sections.extend(audit_tables(client))
    sections.extend(audit_main_fields(client))
    sections.extend(audit_main_views(client))
    sections.extend(audit_workflow(client))
    sections.extend(audit_defect_rework(client))
    sections.extend(audit_summary_control(client))
    sections.extend(audit_config_tables(client, cfg))
    sections.extend(optimization_plan(client, cfg))
    sections.extend(audit_forms_workflows())
    header = [
        "# 2026 生产 Base 全面审计报告",
        f"\n> Base: `{APP}` · 主表 `{MAIN}` · 管理视图 `vewQqWVrxH`",
        f"> 入口: https://kcnfxml9dtzq.feishu.cn/base/{APP}?table={MAIN}&view=vewQqWVrxH",
    ]
    return "\n".join(header + sections)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, help="写入 markdown 文件")
    args = p.parse_args()

    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    report = run(client, cfg)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
        print(f"\n已写入 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
