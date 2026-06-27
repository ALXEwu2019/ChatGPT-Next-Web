#!/usr/bin/env python3
"""V4 compliance audit for production Base (legacy 95-field)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from sync_batch_summary import load_config

APP = "NiyZbKpKfae9x3sUP64cl9SFnRb"
GREEN = "CHNKbTKTCaWbQis1vVXcsLvsnDh"
MAIN = "tblSw8eYEpe7y1am"
GREEN_MAIN = "tblXr4h68tqh2HDy"
BASE = "https://open.feishu.cn/open-apis"

V4_FORBIDDEN = {
    "#4050汇总批号", "#4050汇总合格合计", "#4050本汇总剩余可用数", "#4050数量校验",
    "#4050本汇总剩余可用数 (1)", "#4050数量校验 (1)", "#60汇总批号", "#60汇总合格合计",
    "#4050选择上道汇总", "#60选择上道汇总", "车床简化批号", "汇总批工序键",
}

# 误加的 v4 绿场字段（与旧库 生产批号-输入 / 上道生产记录 重复）
MISTAKEN_ADDED = {
    "关联管控批_STOPPER#2030", "关联管控批_止动块#4050",
    "上道批号_STOPPER#4050", "上道批号_STOPPER#60", "上道批号_STOPPER#70",
    "上道批号_止动块#60", "上道批号_止动块#70", "上道批号_止动块#80",
}

LEGACY_BATCH_MAP = {
    "STOPPER #2030": "生产批号-输入 → 入库批次管控表",
    "STOPPER #4050": "（磨床）上道生产记录 → 主表(#2030 已确认行)",
    "STOPPER #60": "（检测）上道生产记录 → 主表(#4050 已确认行)",
    "STOPPER #70": "（检测）上道生产记录 → 主表(#60 已确认行)",
    "止动块 #4050": "生产批号-输入 → 入库批次管控表",
    "止动块 #60": "（磨床）上道生产记录",
    "止动块 #70": "（检测）上道生产记录",
    "止动块 #80": "（检测）上道生产记录",
}


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def list_fields(cfg: dict, app: str, table: str) -> list[dict]:
    h = {"Authorization": f"Bearer {token(cfg)}"}
    items: list[dict] = []
    page = None
    while True:
        params: dict = {"page_size": 300}
        if page:
            params["page_token"] = page
        data = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/fields", headers=h, params=params, timeout=60
        ).json()["data"]
        items.extend(data["items"])
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return items


def main() -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    pf = list_fields(cfg, APP, MAIN)
    gf = list_fields(cfg, GREEN, GREEN_MAIN)
    pnames = {f["field_name"] for f in pf}
    gnames = {f["field_name"] for f in gf}

    issues: list[tuple[str, str, str]] = []

    issues.append(("架构", "严重", f"主表 {len(pf)} 字段 vs v4 绿场 {len(gf)} 字段，属旧库叠加改造"))
    if any(n in pnames for n in MISTAKEN_ADDED):
        issues.append(("字段", "严重", "存在误加的 per-view 字段，与 生产批号-输入/上道生产记录 三轨并行"))
    for n in V4_FORBIDDEN:
        if n in pnames and not any(f["field_name"] == n and f.get("is_hidden") for f in pf):
            issues.append(("字段", "高", f"禁止字段仍可见: {n}"))
    if not any(f["field_name"] == "工序代码" and f["type"] == 18 for f in pf):
        issues.append(("字段", "高", "工序代码为公式(20)非关联(18)，下道筛选难与 v4 一致"))
    status = next(f for f in pf if f["field_name"] == "工序下发状态")
    opts = [o["name"] for o in status.get("property", {}).get("options", [])]
    if "已确认" not in opts:
        issues.append(("状态", "高", "缺「已确认」；v4 汇总仅认 已确认/已审核"))
    if "生产批号-输入" in pnames and any(n in pnames for n in MISTAKEN_ADDED):
        issues.append(("流程", "严重", "首道应只用 生产批号-输入，不应再填 关联管控批_*"))

    print("=" * 60)
    print("生产 Base v4 合规审计", APP)
    print("=" * 60)
    print(f"\n字段: PROD {len(pf)} | GREEN {len(gf)} | 多余 {len(pnames - gnames)}")
    print("\n## 问题清单\n")
    print("| 层级 | 严重度 | 说明 |")
    print("| --- | --- | --- |")
    for layer, sev, msg in issues:
        print(f"| {layer} | {sev} | {msg} |")

    print("\n## 旧库正确批号来源（v4 语义映射）\n")
    print("| 报工 | 应使用字段 |")
    print("| --- | --- |")
    for k, v in LEGACY_BATCH_MAP.items():
        print(f"| {k} | {v} |")

    print("\n## 结论")
    print("- 不宜在旧库上叠加绿场 per-view 字段；应沿用 生产批号-输入 + （磨床/检测）上道生产记录")
    print("- 短期：删除误加字段 + 各视图 hidden_fields 收敛 + 汇总脚本")
    print("- 长期：迁移至绿场 Base CHNKbTKTCaWbQis1vVXcsLvsnDh")
    return 1 if any(s == "严重" for _, s, _ in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
