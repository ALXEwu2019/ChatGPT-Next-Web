#!/usr/bin/env python3
"""Apply v4 structural changes to 机加工车间生产日志管理系统（新） via Feishu API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"

# 当前生产 Base（用户链接 2026-06）
APP_TOKEN = "NiyZbKpKfae9x3sUP64cl9SFnRb"
MAIN_TABLE = "tblSw8eYEpe7y1am"
CTRL_TABLE = "tblyvJJhyq5KoT4F"
SUM_TABLE = "tblXonlkdLxrTLXE"

FORBIDDEN_FIELD_NAMES = {
    "#4050选择上道汇总",
    "#60选择上道汇总",
    "车床简化批号",
    "#4050汇总批号",
    "#4050汇总合格合计",
    "#4050本汇总剩余可用数",
    "#4050数量校验",
    "#60汇总批号",
    "#60汇总合格合计",
    "#4050本汇总剩余可用数 (1)",
    "#4050数量校验 (1)",
    "汇总批工序键",
}

# 关联/公式类禁止字段：隐藏失败时尝试 DELETE
FORBIDDEN_DELETE_IF_HIDE_FAILS = {
    "#4050选择上道汇总",
    "#60选择上道汇总",
    "#4050汇总合格合计",
    "#60汇总合格合计",
}

DEPRECATED_VIEW_IDS = {
    "vewutGRS7H",  # STOPPER-#40报工
    "vew9iD0uOM",  # STOPPER-#50检测
    "vew11lWJej",  # PTJ92-#50检测出库
    "vewIhOXmBg",  # 止动块-#40报工
    "vewNTBCgpS",  # 止动块-#50检测
}

PER_VIEW_FIELDS = [
    ("关联管控批_STOPPER#2030", CTRL_TABLE),
    ("关联管控批_止动块#4050", CTRL_TABLE),
    ("上道批号_STOPPER#4050", MAIN_TABLE),
    ("上道批号_STOPPER#60", MAIN_TABLE),
    ("上道批号_STOPPER#70", MAIN_TABLE),
    ("上道批号_止动块#60", MAIN_TABLE),
    ("上道批号_止动块#70", MAIN_TABLE),
    ("上道批号_止动块#80", MAIN_TABLE),
]

CTRL_NEW_FIELDS = [
    {"field_name": "批号文本", "type": 1},
    {
        "field_name": "工序代码",
        "type": 18,
        "property": {"table_id": "tblt0I1rLezriVTM", "multiple": False},
    },
    {"field_name": "本工序下发数量", "type": 2, "property": {"formatter": "0"}},
]

SUM_NEW_FIELDS = [
    {"field_name": "末次同步时间", "type": 5, "property": {"date_formatter": "yyyy/MM/dd HH:mm"}},
    {"field_name": "同步批次号", "type": 1},
]


class Client:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    def token(self) -> str:
        if self._token:
            return self._token
        r = requests.post(
            f"{BASE}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        r.raise_for_status()
        self._token = r.json()["tenant_access_token"]
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        time.sleep(0.12)
        r = requests.request(method, f"{BASE}{path}", headers=self._headers(), timeout=60, **kwargs)
        data = r.json()
        return data

    def list_fields(self, table_id: str) -> list[dict]:
        items: list[dict] = []
        page_token = None
        while True:
            params: dict = {"page_size": 300}
            if page_token:
                params["page_token"] = page_token
            data = self._request(
                "GET", f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields", params=params
            )
            if data.get("code") != 0:
                raise RuntimeError(f"list_fields failed: {data}")
            items.extend(data["data"]["items"])
            if not data["data"].get("has_more"):
                break
            page_token = data["data"].get("page_token")
        return items

    def create_field(self, table_id: str, body: dict) -> dict:
        return self._request(
            "POST", f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields", json=body
        )

    def hide_field(self, table_id: str, field: dict) -> dict:
        body = {
            "field_name": field["field_name"],
            "type": field["type"],
            "is_hidden": True,
        }
        if field.get("property") is not None:
            body["property"] = field["property"]
        return self._request(
            "PUT",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields/{field['field_id']}",
            json=body,
        )

    def delete_field(self, table_id: str, field_id: str) -> dict:
        return self._request(
            "DELETE",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields/{field_id}",
        )

    def delete_view(self, table_id: str, view_id: str) -> dict:
        return self._request(
            "DELETE",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/views/{view_id}",
        )


def ensure_link_field(client: Client, table_id: str, existing: dict[str, dict], name: str, link_table: str) -> str:
    if name in existing:
        return f"skip exists: {name}"
    resp = client.create_field(
        table_id,
        {
            "field_name": name,
            "type": 18,
            "property": {"table_id": link_table, "multiple": False},
        },
    )
    if resp.get("code") == 0:
        return f"created: {name}"
    return f"FAIL {name}: {resp.get('msg')} ({resp.get('code')})"


def ensure_simple_field(client: Client, table_id: str, existing: set[str], spec: dict) -> str:
    name = spec["field_name"]
    if name in existing:
        return f"skip exists: {name}"
    resp = client.create_field(table_id, spec)
    if resp.get("code") == 0:
        return f"created: {name}"
    return f"FAIL {name}: {resp.get('msg')} ({resp.get('code')})"


def run(dry_run: bool = False) -> int:
    cfg_path = Path(__file__).with_name("config.json")
    cfg = load_config(cfg_path)
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    results: list[str] = []

    main_fields = client.list_fields(MAIN_TABLE)
    main_by_name = {f["field_name"]: f for f in main_fields}
    ctrl_fields = client.list_fields(CTRL_TABLE)
    ctrl_names = {f["field_name"] for f in ctrl_fields}
    sum_fields = client.list_fields(SUM_TABLE)
    sum_names = {f["field_name"] for f in sum_fields}

    results.append(f"主表字段数: {len(main_fields)}")

    for name, link_table in PER_VIEW_FIELDS:
        if dry_run:
            action = "would create" if name not in main_by_name else "exists"
            results.append(f"[dry-run] {action}: {name}")
            continue
        results.append(ensure_link_field(client, MAIN_TABLE, main_by_name, name, link_table))
        if name not in main_by_name:
            main_by_name[name] = {}

    for fname in sorted(FORBIDDEN_FIELD_NAMES):
        field = main_by_name.get(fname)
        if not field:
            results.append(f"skip missing forbidden: {fname}")
            continue
        if dry_run:
            results.append(f"[dry-run] would hide: {fname}")
            continue
        resp = client.hide_field(MAIN_TABLE, field)
        ok = resp.get("code") == 0
        if ok:
            results.append(f"hidden: {fname}")
        elif fname in FORBIDDEN_DELETE_IF_HIDE_FAILS:
            del_resp = client.delete_field(MAIN_TABLE, field["field_id"])
            results.append(
                f"{'deleted' if del_resp.get('code') == 0 else 'FAIL delete'}: {fname} — {del_resp.get('msg', '')}"
            )
        else:
            results.append(f"FAIL hide: {fname} — {resp.get('msg', '')}")

    for view_id in sorted(DEPRECATED_VIEW_IDS):
        if dry_run:
            results.append(f"[dry-run] would delete view: {view_id}")
            continue
        resp = client.delete_view(MAIN_TABLE, view_id)
        ok = resp.get("code") == 0
        results.append(f"{'deleted view' if ok else 'FAIL view'}: {view_id} — {resp.get('msg', '')}")

    for spec in CTRL_NEW_FIELDS:
        if dry_run:
            results.append(
                f"[dry-run] ctrl {'exists' if spec['field_name'] in ctrl_names else 'create'}: {spec['field_name']}"
            )
            continue
        results.append(ensure_simple_field(client, CTRL_TABLE, ctrl_names, spec))
        ctrl_names.add(spec["field_name"])

    for spec in SUM_NEW_FIELDS:
        if dry_run:
            results.append(
                f"[dry-run] sum {'exists' if spec['field_name'] in sum_names else 'create'}: {spec['field_name']}"
            )
            continue
        results.append(ensure_simple_field(client, SUM_TABLE, sum_names, spec))
        sum_names.add(spec["field_name"])

    print("optimize_production_base")
    print("-" * 60)
    for line in results:
        print(line)
    print("-" * 60)
    print("后续需在飞书界面完成：8 报工视图关联筛选、管控表合格合计查找、汇总表产品/工序改关联类型（可选）")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
