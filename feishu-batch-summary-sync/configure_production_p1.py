#!/usr/bin/env python3
"""P1 follow-up for production Base: data backfill, status align, field hide."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"
APP_TOKEN = "NiyZbKpKfae9x3sUP64cl9SFnRb"
MAIN_TABLE = "tblSw8eYEpe7y1am"
CTRL_TABLE = "tblyvJJhyq5KoT4F"

# 首道工序 record_id（管控表回填用；全表当前均为 STOPPER 批）
PROC_STOPPER_2030 = "recAV0kYI0r5LS"

HIDE_FIELD_NAMES = {
    "#50-PTJ92",
}


def should_hide_field(name: str) -> bool:
    return name.startswith("生产区域-#") or name in HIDE_FIELD_NAMES


class Client:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    def token(self) -> str:
        if not self._token:
            r = requests.post(
                f"{BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=30,
            )
            r.raise_for_status()
            self._token = r.json()["tenant_access_token"]
        return self._token

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json"}

    def call(self, method: str, path: str, **kwargs) -> dict:
        time.sleep(0.12)
        r = requests.request(method, f"{BASE}{path}", headers=self.headers(), timeout=60, **kwargs)
        return r.json()

    def list_fields(self, table_id: str) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            params: dict = {"page_size": 300}
            if page:
                params["page_token"] = page
            data = self.call("GET", f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields", params=params)
            items.extend(data["data"]["items"])
            if not data["data"].get("has_more"):
                break
            page = data["data"].get("page_token")
        return items

    def list_records(self, table_id: str) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            params: dict = {"page_size": 500}
            if page:
                params["page_token"] = page
            data = self.call("GET", f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records", params=params)
            items.extend(data.get("data", {}).get("items", []))
            if not data.get("data", {}).get("has_more"):
                break
            page = data.get("data", {}).get("page_token")
        return items

    def batch_update(self, table_id: str, records: list[dict]) -> dict:
        return self.call(
            "POST",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/records/batch_update",
            json={"records": records},
        )

    def hide_field(self, table_id: str, field: dict) -> dict:
        body = {
            "field_name": field["field_name"],
            "type": field["type"],
            "is_hidden": True,
        }
        if field.get("property") is not None:
            body["property"] = field["property"]
        return self.call(
            "PUT",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields/{field['field_id']}",
            json=body,
        )

    def delete_field(self, table_id: str, field_id: str) -> dict:
        return self.call(
            "DELETE",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{table_id}/fields/{field_id}",
        )

    def add_status_option(self, field: dict) -> dict:
        options = list(field.get("property", {}).get("options", []))
        if any(o.get("name") == "已确认" for o in options):
            return {"code": 0, "msg": "skip exists"}
        options.append({"name": "已确认", "color": 0})
        body = {
            "field_name": field["field_name"],
            "type": field["type"],
            "property": {"options": options},
        }
        return self.call(
            "PUT",
            f"/bitable/v1/apps/{APP_TOKEN}/tables/{MAIN_TABLE}/fields/{field['field_id']}",
            json=body,
        )


def backfill_control(client: Client, dry_run: bool) -> list[str]:
    rows = client.list_records(CTRL_TABLE)
    updates: list[dict] = []
    lines: list[str] = []
    for row in rows:
        f = row.get("fields", {})
        batch = f.get("批次号")
        if not batch:
            continue
        plan = f.get("计划数量")
        qty = float(plan) if plan not in (None, "") else None
        payload = {
            "record_id": row["record_id"],
            "fields": {
                "批号文本": batch,
                "工序代码": [PROC_STOPPER_2030],
            },
        }
        if qty is not None:
            payload["fields"]["本工序下发数量"] = qty
        updates.append(payload)
        lines.append(f"ctrl {batch}: 批号文本+工序#2030+下发量")

    if dry_run:
        lines.insert(0, f"[dry-run] would update {len(updates)} control rows")
        return lines

    if updates:
        resp = client.batch_update(CTRL_TABLE, updates)
        lines.insert(0, f"control batch_update: {resp.get('msg')} ({len(updates)} rows)")
    return lines


def hide_region_fields(client: Client, dry_run: bool) -> list[str]:
    fields = client.list_fields(MAIN_TABLE)
    lines: list[str] = []
    for field in fields:
        name = field["field_name"]
        if not should_hide_field(name):
            continue
        if field.get("is_hidden"):
            lines.append(f"skip hidden: {name}")
            continue
        if dry_run:
            lines.append(f"[dry-run] hide: {name}")
            continue
        resp = client.hide_field(MAIN_TABLE, field)
        ok = resp.get("code") == 0
        if ok:
            lines.append(f"hidden: {name}")
            continue
        del_resp = client.delete_field(MAIN_TABLE, field["field_id"])
        lines.append(
            f"{'deleted' if del_resp.get('code') == 0 else 'FAIL'}: {name} — {del_resp.get('msg', '')}"
        )
    return lines


def align_status_option(client: Client, dry_run: bool) -> list[str]:
    fields = client.list_fields(MAIN_TABLE)
    status = next(f for f in fields if f["field_name"] == "工序下发状态")
    if dry_run:
        return ["[dry-run] add 已确认 option to 工序下发状态"]
    resp = client.add_status_option(status)
    return [f"工序下发状态: {resp.get('msg')}"]


def run(dry_run: bool = False) -> int:
    cfg_path = Path(__file__).with_name("config.2026.json")
    if cfg_path.exists():
        from remediate_2026_summary import load_2026_config

        cfg = load_2026_config()
    else:
        cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    results: list[str] = []
    results.extend(align_status_option(client, dry_run))
    results.extend(backfill_control(client, dry_run))
    results.extend(hide_region_fields(client, dry_run))

    print("configure_production_p1")
    print("-" * 60)
    for line in results:
        print(line)
    print("-" * 60)
    print("关联筛选须在飞书界面配置：docs/feishu-p1-manual-setup-2026-cn.md")
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
