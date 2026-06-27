#!/usr/bin/env python3
"""修复 2026 Base 批工序产量汇总表 tblXonlkdLxrTLXE（按 v4 脚本写入方案）。

典型问题（审计结论）：
  - 遗留字段：汇总批号(公式)、关联生产记录、末次更新时间
  - 缺 生产区域
  - 14 行 = 7 行脚本写入 + 7 行旧键重复
  - 主表全「已报工」时脚本无法增量同步

用法：
  FEISHU_BASE_APP_TOKEN=NiyZbKpKfae9x3sUP64cl9SFnRb \\
    python3 remediate_2026_summary.py --audit
  python3 remediate_2026_summary.py --fix-schema --dedupe-rows
  python3 remediate_2026_summary.py --fix-all --sync
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import extract_text, run_sync

APP = "NiyZbKpKfae9x3sUP64cl9SFnRb"
SUM_TABLE = "tblXonlkdLxrTLXE"
MAIN_TABLE = "tblSw8eYEpe7y1am"
BASE = "https://open.feishu.cn/open-apis"

LEGACY_SUM_FIELDS = ("汇总批号", "关联生产记录", "末次更新时间")
REQUIRED_SUM_FIELD = "生产区域"


def load_2026_config() -> dict:
    """加载 config.2026.json；凭证可从 config.local.json / 环境变量读取，但保留 2026 app_token。"""
    path = Path(__file__).with_name("config.2026.json")
    if not path.exists():
        raise FileNotFoundError("缺少 config.2026.json，请从 config.2026.example.json 复制")
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    local = path.with_name("config.local.json")
    if local.exists():
        with local.open(encoding="utf-8") as f:
            local_cfg = json.load(f)
        if isinstance(local_cfg.get("feishu"), dict):
            for k in ("app_id", "app_secret"):
                if local_cfg["feishu"].get(k):
                    cfg.setdefault("feishu", {})[k] = local_cfg["feishu"][k]
    feishu = cfg.setdefault("feishu", {})
    if os.environ.get("FEISHU_APP_ID"):
        feishu["app_id"] = os.environ["FEISHU_APP_ID"]
    if os.environ.get("FEISHU_APP_SECRET"):
        feishu["app_secret"] = os.environ["FEISHU_APP_SECRET"]
    if os.environ.get("FEISHU_BASE_APP_TOKEN"):
        feishu["base_app_token"] = os.environ["FEISHU_BASE_APP_TOKEN"]
    feishu["base_app_token"] = APP
    return cfg


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

    def list_records(self, table: str) -> list[dict]:
        items: list[dict] = []
        page = None
        while True:
            params: dict = {"page_size": 500}
            if page:
                params["page_token"] = page
            data = self.call("GET", f"/bitable/v1/apps/{APP}/tables/{table}/records", params=params)["data"]
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page = data.get("page_token")
        return items

    def hide_field(self, table: str, field: dict) -> dict:
        body = {
            "field_name": field["field_name"],
            "type": field["type"],
            "is_hidden": True,
        }
        if field.get("property") is not None:
            body["property"] = field["property"]
        return self.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{table}/fields/{field['field_id']}",
            json=body,
        )

    def delete_field(self, table: str, field_id: str) -> dict:
        return self.call("DELETE", f"/bitable/v1/apps/{APP}/tables/{table}/fields/{field_id}")

    def create_field(self, table: str, body: dict) -> dict:
        return self.call("POST", f"/bitable/v1/apps/{APP}/tables/{table}/fields", json=body)

    def delete_records(self, table: str, record_ids: list[str]) -> dict:
        return self.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{table}/records/batch_delete",
            json={"records": record_ids},
        )


def audit(client: Client) -> list[str]:
    lines: list[str] = []
    fields = {f["field_name"]: f for f in client.list_fields(SUM_TABLE)}
    records = client.list_records(SUM_TABLE)
    main = client.list_records(MAIN_TABLE)

    lines.append(f"汇总表字段 {len(fields)} 个，数据 {len(records)} 行")
    if REQUIRED_SUM_FIELD not in fields:
        lines.append(f"[FAIL] 缺字段 {REQUIRED_SUM_FIELD}")
    for name in LEGACY_SUM_FIELDS:
        f = fields.get(name)
        if f and not f.get("is_hidden"):
            t = f.get("type")
            lines.append(f"[FAIL] 遗留字段仍可见: {name} (type={t})")

    with_sync = [r for r in records if extract_text(r.get("fields", {}).get("同步批次号"))]
    without_sync = [r for r in records if not extract_text(r.get("fields", {}).get("同步批次号"))]
    lines.append(f"脚本行 {len(with_sync)} · 旧行 {len(without_sync)}")

    status: dict[str, int] = {}
    for r in main:
        st = extract_text(r.get("fields", {}).get("工序下发状态")) or "(空)"
        status[st] = status.get(st, 0) + 1
    lines.append(f"主表状态分布: {status}")
    if status.get("已确认", 0) + status.get("已审核", 0) == 0:
        lines.append("[WARN] 主表无已确认/已审核记录，sync 不会写入新数据")

    bad_keys = [extract_text(r["fields"].get("批工序键")) for r in records if str(extract_text(r["fields"].get("批工序键"))).endswith("-")]
    if bad_keys:
        lines.append(f"[WARN] 批工序键末尾缺区域: {bad_keys}")
    return lines


def fix_schema(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    fields = {f["field_name"]: f for f in client.list_fields(SUM_TABLE)}

    if REQUIRED_SUM_FIELD not in fields:
        if dry_run:
            lines.append(f"[dry-run] create {REQUIRED_SUM_FIELD}")
        else:
            resp = client.create_field(SUM_TABLE, {"field_name": REQUIRED_SUM_FIELD, "type": 1})
            ok = resp.get("code") == 0
            lines.append(f"{'created' if ok else 'FAIL'}: {REQUIRED_SUM_FIELD} — {resp.get('msg', '')}")

    for name in LEGACY_SUM_FIELDS:
        f = fields.get(name)
        if not f or f.get("is_hidden"):
            lines.append(f"skip: {name}")
            continue
        if dry_run:
            lines.append(f"[dry-run] hide/delete {name}")
            continue
        resp = client.hide_field(SUM_TABLE, f)
        if resp.get("code") == 0 and f.get("type") != 20:
            lines.append(f"hidden: {name}")
            continue
        del_resp = client.delete_field(SUM_TABLE, f["field_id"])
        lines.append(
            f"{'deleted' if del_resp.get('code') == 0 else 'FAIL'}: {name} — {del_resp.get('msg', '')}"
        )
    return lines


def dedupe_rows(client: Client, dry_run: bool) -> list[str]:
    """删除无「同步批次号」的重复行（保留脚本写入行）。"""
    records = client.list_records(SUM_TABLE)
    with_sync = [r for r in records if extract_text(r.get("fields", {}).get("同步批次号"))]
    without_sync = [r for r in records if not extract_text(r.get("fields", {}).get("同步批次号"))]

    if not without_sync:
        return ["skip: 无旧重复行"]

    # 仅当存在脚本行时才删旧行，避免误删全部数据
    if not with_sync:
        return ["skip: 无脚本写入行作对照，请人工确认后再删"]

    to_delete = [r["record_id"] for r in without_sync]
    if dry_run:
        return [f"[dry-run] delete {len(to_delete)} legacy rows"]
    resp = client.delete_records(SUM_TABLE, to_delete)
    ok = resp.get("code") == 0
    return [f"{'deleted' if ok else 'FAIL'} {len(to_delete)} legacy rows — {resp.get('msg', '')}"]


def backfill_production_areas(client: Client, dry_run: bool) -> list[str]:
    """从批工序键回填 生产区域；修正 #4050 残缺键。"""
    lines: list[str] = []
    for it in client.list_records(SUM_TABLE):
        f = it.get("fields", {})
        proc = extract_text(f.get("工序代码"))
        key = extract_text(f.get("批工序键"))
        area = extract_text(f.get("生产区域"))
        rid = it["record_id"]
        updates: dict[str, str] = {}

        if proc == "#2030" and key and not area:
            suffix = key.rsplit("-", 1)[-1]
            if suffix in ("A", "B", "C"):
                updates["生产区域"] = suffix
        elif proc == "#4050":
            if key.endswith("-") or key.endswith("#4050") or "MG" not in key:
                mg = area or "MG02"
                updates["生产区域"] = mg
                updates["批工序键"] = f"{extract_text(f.get('批号文本'))}-#4050-{mg}"
            elif not area and "-MG" in key:
                updates["生产区域"] = key.split("-MG", 1)[-1]

        if not updates:
            continue
        if dry_run:
            lines.append(f"[dry-run] backfill {rid}: {updates}")
            continue
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{SUM_TABLE}/records/{rid}",
            json={"fields": updates},
        )
        ok = resp.get("code") == 0
        lines.append(f"{'backfill' if ok else 'FAIL'} {rid}: {updates} — {resp.get('msg', '')}")
    if not lines:
        lines.append("skip: 生产区域已齐全")
    return lines


def run(cfg: dict, audit_only: bool, fix_schema_flag: bool, dedupe: bool, backfill: bool, sync: bool, dry_run: bool) -> int:
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("remediate_2026_summary — 2026 批工序产量汇总表")
    print(f"App {APP}  Table {SUM_TABLE}")
    print("-" * 60)

    for line in audit(client):
        print(line)
    if audit_only:
        return 0

    if fix_schema_flag:
        print("\n## 修复表结构")
        for line in fix_schema(client, dry_run):
            print(line)

    if dedupe:
        print("\n## 清理重复行")
        for line in dedupe_rows(client, dry_run):
            print(line)

    if backfill:
        print("\n## 回填生产区域")
        for line in backfill_production_areas(client, dry_run):
            print(line)

    if sync and not dry_run:
        print("\n## 执行 sync_batch_summary")
        rows = run_sync(cfg, dry_run=False)
        print(f"sync 完成，聚合 {len(rows)} 行")
    elif sync:
        print("\n## [dry-run] sync_batch_summary")
        rows = run_sync(cfg, dry_run=True)
        print(f"将聚合 {len(rows)} 行")

    print("-" * 60)
    print("手工剩余：")
    print("  1. 主表品保确认 → 工序下发状态改为「已确认」")
    print("  2. #4050 报工行补填 生产区域（MG02 等）")
    print("  3. 管控表配置「合格合计」查找 → 汇总表（见 docs/feishu-lookup-qualified-total-cn.md）")
    print("  4. cron: sync_batch_summary.py --config config.2026.json")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Remediate 2026 batch summary table")
    p.add_argument("--audit", action="store_true", help="只读审计")
    p.add_argument("--fix-schema", action="store_true", help="隐藏/删除遗留字段，补生产区域")
    p.add_argument("--dedupe-rows", action="store_true", help="删除无同步批次号的旧重复行")
    p.add_argument("--backfill-areas", action="store_true", help="从批工序键回填生产区域")
    p.add_argument("--sync", action="store_true", help="执行 sync_batch_summary 写入")
    p.add_argument("--fix-all", action="store_true", help="= --fix-schema --dedupe-rows --backfill-areas")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.fix_all:
        args.fix_schema = True
        args.dedupe_rows = True
        args.backfill_areas = True
    if not any((args.audit, args.fix_schema, args.dedupe_rows, args.backfill_areas, args.sync, args.fix_all)):
        args.audit = True
    try:
        cfg = load_2026_config()
        return run(
            cfg,
            args.audit and not args.fix_schema and not args.dedupe_rows and not args.backfill_areas and not args.sync,
            args.fix_schema,
            args.dedupe_rows,
            args.backfill_areas,
            args.sync,
            args.dry_run,
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
