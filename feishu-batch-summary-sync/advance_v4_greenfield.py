#!/usr/bin/env python3
"""Advance 机加工生产日志 v4 greenfield: trace rules, view hygiene, sync."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"
APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
TRACE = "tblWv5lus3TI8zM3"

from process_registry import CHAINS, PROD, TRACE_RULES, proc_id

COMMON_KEEP = {
    "日志编号", "产品", "产品名称", "工序代码", "工序代码文本", "工序下发状态",
    "合格数量", "报废数量", "返工数量", "返工后合格数", "返工后报废数",
    "有效合格数量", "有效报废数量", "批号文本", "生产批号", "生产批号_上道",
    "完整追溯号", "填报月日", "操作工", "班次", "是否有不良", "是否异常",
    "工位代码", "管控批产品", "管控批工序", "管控批状态",
}

VIEW_KEEP: dict[str, set[str]] = {
    "vewfbrQvsu": COMMON_KEEP | {"关联管控批_STOPPER#2030", "关联管控批", "生产区域"},
    "vew7Diocr5": COMMON_KEEP | {"上道批号_STOPPER#4050", "上道批号", "生产区域"},
    "vewgS0km1u": COMMON_KEEP | {"上道批号_STOPPER#60", "上道批号", "工位代码"},
    "vewqlHptpP": COMMON_KEEP | {"上道批号_STOPPER#70", "上道批号"},
    "vew4kJ8hxX": COMMON_KEEP | {"上道批号_止动块#4050", "上道批号", "生产区域"},
    "vewEMVET4u": COMMON_KEEP | {"上道批号_止动块#60", "上道批号", "工位代码"},
    "vewUWGnXfU": COMMON_KEEP | {"上道批号_止动块#70", "上道批号"},
    "vewEJZrQu5": COMMON_KEEP | {"上道批号_止动块#80", "上道批号"},
}

# 简写重复视图：隐藏（保留带「报工视图」后缀的 4 个）
HIDE_VIEW_IDS = {"vewRy47uJk", "vewsXMq522", "vewxR6vOrR"}


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

    def list_fields(self, table: str) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            params: dict = {"page_size": 300}
            if page:
                params["page_token"] = page
            data = self.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/fields", params=params)["data"]
            items.extend(data["items"])
            if not data.get("has_more"):
                break
            page = data.get("page_token")
        return items

    def count_records(self, table: str) -> int:
        data = self.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/records", params={"page_size": 1})
        return data.get("data", {}).get("total", 0)


def seed_trace_rules(client: Client, dry_run: bool) -> list[str]:
    n = client.count_records(TRACE)
    if n >= 8:
        return [f"skip trace rules: already {n} rows"]
    rows = []
    for name, prod_key, proc_code, need, seg3, note in TRACE_RULES:
        rows.append(
            {
                "fields": {
                    "规则名称": name,
                    "产品": [PROD[prod_key]],
                    "工序代码": [proc_id(prod_key, proc_code)],
                    "需要追溯号": need,
                    "段3来源字段": seg3,
                    "段3说明": note,
                }
            }
        )
    if dry_run:
        return [f"[dry-run] create {len(rows)} trace rules"]
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{TRACE}/records/batch_create",
        json={"records": rows},
    )
    created = len(resp.get("data", {}).get("records", []))
    return [f"trace rules: {resp.get('msg')} ({created} rows)"]


def patch_views(client: Client, dry_run: bool) -> list[str]:
    fields = client.list_fields(MAIN)
    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary = next(f["field_id"] for f in fields if f.get("is_primary"))
    all_ids = [f["field_id"] for f in fields]
    lines: list[str] = []

    for view_id, keep_names in VIEW_KEEP.items():
        keep_ids = {primary}
        for n in keep_names:
            if n in name_to_id:
                keep_ids.add(name_to_id[n])
        hidden = [fid for fid in all_ids if fid not in keep_ids]
        if dry_run:
            lines.append(f"[dry-run] view {view_id}: show {len(keep_ids)} hide {len(hidden)}")
            continue
        resp = client.call(
            "PATCH",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{view_id}",
            json={"property": {"hidden_fields": hidden}},
        )
        ok = resp.get("code") == 0
        lines.append(f"{'view ok' if ok else 'FAIL'}: {view_id} — {resp.get('msg', '')}")
    return lines


def hide_duplicate_views(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for vid in sorted(HIDE_VIEW_IDS):
        if dry_run:
            lines.append(f"[dry-run] delete duplicate view {vid}")
            continue
        resp = client.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{vid}")
        lines.append(f"{'deleted view' if resp.get('code')==0 else 'FAIL'}: {vid}")
    return lines


def run(dry_run: bool, skip_sync: bool) -> int:
    cfg_path = Path(__file__).with_name("config.json")
    cfg = load_config(cfg_path)
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    results: list[str] = []
    results.extend(seed_trace_rules(client, dry_run))
    results.extend(patch_views(client, dry_run))
    results.extend(hide_duplicate_views(client, dry_run))

    print("advance_v4_greenfield")
    print("-" * 60)
    for line in results:
        print(line)
    print("-" * 60)

    if not dry_run and not skip_sync:
        from sync_batch_summary import run_sync

        rows = run_sync(cfg, dry_run=False)
        print(f"sync: aggregated {len(rows)} summary rows")

    print("手工剩余：8 视图关联筛选、联动四视图、cron、P2")
    print("文档：docs/v4-wiki-full-execution-cn.md")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-sync", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run, args.skip_sync)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
