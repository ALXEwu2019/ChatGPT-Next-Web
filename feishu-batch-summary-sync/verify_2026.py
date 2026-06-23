#!/usr/bin/env python3
"""2026 Base v4 optimization acceptance checks (read-only)."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

from sync_batch_summary import extract_text, load_config

BASE = "https://open.feishu.cn/open-apis"
APP_PRODUCTION = "NiyZbKpKfae9x3sUP64cl9SFnRb"
MAIN_TABLE = "tblSw8eYEpe7y1am"

FORBIDDEN_FIELDS = [
    "#4050选择上道汇总",
    "#60选择上道汇总",
    "车床简化批号",
    "#4050汇总合格合计",
    "#4050汇总批号",
    "#4050本汇总剩余可用数",
    "#4050数量校验",
    "#60汇总批号",
    "汇总批工序键",
]

MISTAKEN_ADDED_FIELDS = [
    "关联管控批_STOPPER#2030",
    "关联管控批_止动块#4050",
    "上道批号_STOPPER#4050",
    "上道批号_STOPPER#60",
    "上道批号_STOPPER#70",
    "上道批号_止动块#60",
    "上道批号_止动块#70",
    "上道批号_止动块#80",
]

LEGACY_BATCH_FIELDS = [
    "生产批号-输入",
    "（磨床）上道生产记录",
    "（检测）上道生产记录",
]

DEPRECATED_VIEW_MARKERS = (
    "-#40报工",
    "-#50检测",
    "PTJ92-#50",
)


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def api_get(cfg: dict, path: str, params: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {token(cfg)}"}
    r = requests.get(f"{BASE}{path}", headers=h, params=params or {}, timeout=60)
    return r.json()


def list_records(cfg: dict, table_id: str) -> list[dict]:
    app = cfg["feishu"]["base_app_token"]
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 500}
        if page:
            params["page_token"] = page
        data = api_get(cfg, f"/bitable/v1/apps/{app}/tables/{table_id}/records", params)["data"]
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def list_fields(cfg: dict, table_id: str) -> list[dict]:
    app = cfg["feishu"]["base_app_token"]
    data = api_get(
        cfg, f"/bitable/v1/apps/{app}/tables/{table_id}/fields", {"page_size": 300}
    )
    return data.get("data", {}).get("items", [])


def list_views(cfg: dict, table_id: str) -> list[dict]:
    app = cfg["feishu"]["base_app_token"]
    data = api_get(
        cfg, f"/bitable/v1/apps/{app}/tables/{table_id}/views", {"page_size": 100}
    )
    return data.get("data", {}).get("items", [])


def main() -> int:
    cfg_path = Path(__file__).with_name("config.2026.json")
    if not cfg_path.exists():
        print("FAIL: config.2026.json missing (copy from config.2026.example.json)")
        return 1
    cfg = load_config(cfg_path)
    if cfg["feishu"]["base_app_token"] != APP_PRODUCTION:
        print(f"WARN: config token != 生产 Base ({APP_PRODUCTION})")

    tables = cfg["tables"]
    checks: list[tuple[str, bool, str]] = []

    fields = list_fields(cfg, MAIN_TABLE)
    field_names = {f["field_name"] for f in fields}
    visible_forbidden = [
        f["field_name"]
        for f in fields
        if f["field_name"] in FORBIDDEN_FIELDS and not f.get("is_hidden")
    ]
    checks.append(
        ("主表可见字段≤55（瘦身进行中）", len([f for f in fields if not f.get("is_hidden")]) <= 55,
         f"API共{len(fields)}个（含隐藏）"),
    )
    checks.append(
        ("无v4禁止字段（可见）",
         len(visible_forbidden) == 0,
         "仍可见: " + ", ".join(visible_forbidden) if visible_forbidden else "已隐藏或删除"),
    )

    required = ["批号文本", "有效合格数量", "有效报废数量", "工序下发状态", "完整追溯号"]
    missing = [n for n in required if n not in field_names]
    checks.append(
        ("主表核心字段齐全", len(missing) == 0, "缺失: " + ", ".join(missing) if missing else "OK"),
    )

    mistaken = [n for n in MISTAKEN_ADDED_FIELDS if n in field_names]
    checks.append(
        ("无误加 per-view 字段",
         len(mistaken) == 0,
         "应删除: " + ", ".join(mistaken) if mistaken else "OK"),
    )

    legacy = [n for n in LEGACY_BATCH_FIELDS if n in field_names]
    checks.append(
        ("旧库批号字段齐全",
         len(legacy) == 3,
         f"已有: {', '.join(legacy)}"),
    )

    per_view = [n for n in field_names if n.startswith("关联管控批_") or n.startswith("上道批号_")]
    if not mistaken:
        checks.append(("无冗余 per-view 字段", len(per_view) == 0, f"残留 {len(per_view)} 个"))

    views = list_views(cfg, MAIN_TABLE)
    deprecated_visible = [
        v["view_name"]
        for v in views
        if any(m in v.get("view_name", "") for m in DEPRECATED_VIEW_MARKERS)
    ]
    checks.append(
        ("#40/#50视图已隐藏或删除",
         len(deprecated_visible) == 0,
         f"仍可见: {deprecated_visible}" if deprecated_visible else "OK"),
    )

    linkage = list_records(cfg, tables.get("defect_linkage", "tblYlVXydRLMzPeG"))
    checks.append(("联动规则≥137行", len(linkage) >= 137, f"{len(linkage)}行"))

    reasons = list_records(cfg, tables.get("defect_reason", "tblBqYPtdnIVh6Ml"))
    checks.append(("不良原因库≥45条", len(reasons) >= 45, f"{len(reasons)}条"))

    main_rows = list_records(cfg, tables["production_log"])
    confirmed = [
        r
        for r in main_rows
        if extract_text(r.get("fields", {}).get("工序下发状态")) in ("已确认", "已审核")
    ]
    reported = [
        r for r in main_rows if extract_text(r.get("fields", {}).get("工序下发状态")) == "已报工"
    ]
    checks.append(
        ("主表有已确认记录(汇总用)",
         len(confirmed) > 0,
         f"已确认/已审核 {len(confirmed)} 条；仍已报工 {len(reported)} 条待品保确认"),
    )

    summary = list_records(cfg, tables["batch_summary"])
    checks.append(("汇总表有数据", len(summary) > 0, f"{len(summary)}行"))

    proc_fields = list_fields(cfg, cfg["link_tables"]["process"]["table_id"])
    proc_recs = list_records(cfg, cfg["link_tables"]["process"]["table_id"])
    checks.append(
        ("工序表≤10行（去产品后缀后）", len(proc_recs) <= 10, f"当前{len(proc_recs)}行"),
    )

    print("2026 Base v4 优化验收")
    print("-" * 50)
    all_ok = True
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {name} — {detail}")
        all_ok = all_ok and ok

    print("-" * 50)
    print("优化文档: docs/machining-production-log-2026-optimization-cn.md")
    print("飞书AI Prompt: docs/openclaw-2026-optimization-prompt-cn.md")
    manual = [
        "飞书界面：8 报工视图关联筛选",
        "管控表：批号文本 + 合格合计查找",
        "cron: sync_batch_summary.py --config config.2026.json",
    ]
    print("仍需人工：")
    for m in manual:
        print(f"  - {m}")

    return 0 if all_ok else 2


if __name__ == "__main__":
    sys.exit(main())
