#!/usr/bin/env python3
"""
Remediate production Base per v4 audit.

Strategy (legacy-compatible, NOT greenfield graft):
1. DELETE mistakenly added per-view fields (8)
2. DELETE v4-forbidden formula/summary columns on main table
3. PATCH报工 views: hide irrelevant columns per operation
4. Do NOT replace 生产批号-输入 / （磨床|检测）上道生产记录 workflow
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"
APP = "NiyZbKpKfae9x3sUP64cl9SFnRb"
MAIN = "tblSw8eYEpe7y1am"

DELETE_FIELD_NAMES = {
    # 误加 v4 绿场字段
    "关联管控批_STOPPER#2030",
    "关联管控批_止动块#4050",
    "上道批号_STOPPER#4050",
    "上道批号_STOPPER#60",
    "上道批号_STOPPER#70",
    "上道批号_止动块#60",
    "上道批号_止动块#70",
    "上道批号_止动块#80",
    # v4 禁止
    "#4050汇总批号",
    "#4050本汇总剩余可用数",
    "#4050本汇总剩余可用数 (1)",
    "#4050数量校验",
    "#4050数量校验 (1)",
    "#60汇总批号",
}

# 各报工 grid 视图列收敛（form 视图 OpenAPI 无法 PATCH hidden_fields，需在飞书界面手工）
VIEW_KEEP: dict[str, set[str]] = {
    "vewK5AzZee": {
        "日志编号", "生产批号-输入", "产品", "工序代码", "工序名称", "工序下发状态",
        "生产区域", "生产区域_自动计算", "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "生产批号_自计算", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
    "vewDHfBsiA": {
        "日志编号", "（检测）上道生产记录", "产品", "工序代码", "工序名称", "工序下发状态",
        "生产区域", "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
    "vewTzUcYoa": {
        "日志编号", "生产批号-输入", "产品", "工序代码", "工序名称", "工序下发状态",
        "生产区域", "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
    "vewUARYzDt": {
        "日志编号", "（磨床）上道生产记录", "产品", "工序代码", "工序名称", "工序下发状态",
        "生产区域", "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
    "vewoznLRjG": {
        "日志编号", "（检测）上道生产记录", "产品", "工序代码", "工序名称", "工序下发状态",
        "生产区域", "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
    "vewz80kpKL": {
        "日志编号", "（检测）上道生产记录", "产品", "工序代码", "工序名称", "工序下发状态",
        "良品数量", "报废数量", "有效合格数量", "有效报废数量",
        "批号文本", "生产批号", "完整追溯号", "填报月日", "操作工", "班次", "备注",
    },
}

FORM_VIEW_IDS = frozenset({
    "vew5Rb9Urh", "vew121aeT9", "vew2SbrO7V", "vewEah4EhT",
    "vew3B1ivXN", "vewbP2DKMa", "vew5WATrGc",
})


class Client:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    def tok(self) -> str:
        if not self._token:
            r = requests.post(
                f"{BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=30,
            )
            self._token = r.json()["tenant_access_token"]
        return self._token

    def call(self, method: str, path: str, **kw) -> dict:
        time.sleep(0.12)
        h = {"Authorization": f"Bearer {self.tok()}", "Content-Type": "application/json"}
        return requests.request(method, f"{BASE}{path}", headers=h, timeout=60, **kw).json()

    def list_fields(self) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            params: dict = {"page_size": 300}
            if page:
                params["page_token"] = page
            data = self.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields", params=params)["data"]
            items.extend(data["items"])
            if not data.get("has_more"):
                break
            page = data.get("page_token")
        return items

    def list_views(self) -> list[dict]:
        return self.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views", params={"page_size": 100})[
            "data"
        ]["items"]


def run(dry_run: bool) -> int:
    cfg_path = Path(__file__).with_name("config.2026.json")
    if cfg_path.exists():
        from remediate_2026_summary import load_2026_config

        cfg = load_2026_config()
    else:
        cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    fields = client.list_fields()
    by_name = {f["field_name"]: f for f in fields}
    all_ids = [f["field_id"] for f in fields]
    results: list[str] = []

    for name in sorted(DELETE_FIELD_NAMES):
        field = by_name.get(name)
        if not field:
            results.append(f"skip delete (missing): {name}")
            continue
        if dry_run:
            results.append(f"[dry-run] delete field: {name}")
            continue
        resp = client.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{field['field_id']}")
        ok = resp.get("code") == 0
        results.append(f"{'deleted' if ok else 'FAIL del'}: {name} — {resp.get('msg', '')}")

    # refresh after deletes
    if not dry_run:
        fields = client.list_fields()
        by_name = {f["field_name"]: f for f in fields}
        all_ids = [f["field_id"] for f in fields]

    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary_id = next(f["field_id"] for f in fields if f.get("is_primary"))

    for view_id, keep_names in VIEW_KEEP.items():
        if view_id in FORM_VIEW_IDS:
            results.append(f"skip form view (手工): {view_id}")
            continue
        keep_ids = {primary_id}
        for n in keep_names:
            if n in name_to_id:
                keep_ids.add(name_to_id[n])
        hidden = [fid for fid in all_ids if fid not in keep_ids]
        if dry_run:
            results.append(f"[dry-run] view {view_id}: hide {len(hidden)} cols, show {len(keep_ids)}")
            continue
        resp = client.call(
            "PATCH",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{view_id}",
            json={"property": {"hidden_fields": hidden}},
        )
        ok = resp.get("code") == 0
        results.append(
            f"{'view ok' if ok else 'FAIL view'}: {view_id} hide={len(hidden)} — {resp.get('msg', '')}"
        )

    print("remediate_production_base (v4 legacy-compatible)")
    print("-" * 60)
    for line in results:
        print(line)
    print("-" * 60)
    print("下一步：按 docs/feishu-p1-manual-setup-2026-cn.md 配置")
    print("  生产批号-输入 / （磨床）上道生产记录 / （检测）上道生产记录 的关联筛选")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
