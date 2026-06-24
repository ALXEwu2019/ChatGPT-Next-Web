#!/usr/bin/env python3
"""Remediate 机加工生产日志 v4 greenfield formula fields on production log main table."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"
APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
TRACE = "tblWv5lus3TI8zM3"

# field_id -> (field_name, formula_expression)
FORMULAS: dict[str, tuple[str, str]] = {
  # 批号：首道=管控批；下道沿上道链回溯至首道管控（最多 4 跳，覆盖 #80）
  "fldD86odYI": (
    "批号文本",
    "CONCATENATE("
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj]"
    ")",
  ),
  "fldvMRl868": (
    "生产批号",
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldD86odYI]",
  ),
  "fldncziHl9": (
    "生产批号_上道",
    "CONCATENATE("
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldDnQmyR6].$column[fldxfgJtRE].$column[fldVkXzRxj]"
    ")",
  ),
  "fldPVR3fmV": ("填报月日", 'TEXT(NOW(),"MMDD")'),
  "fldYty1rzM": (
    "完整追溯号",
    "IF("
    "bitable::$table[tblWv5lus3TI8zM3].FILTER("
    "CurrentValue.$column[fldhJ5dxmn]=bitable::$table[tblXr4h68tqh2HDy].$field[fldSUoQi47]"
    "&&CurrentValue.$column[fldDSGS9GN]=bitable::$table[tblXr4h68tqh2HDy].$field[fldMxRQhnU]"
    ").$column[fldmuvJhHG].FIRST(),"
    'CONCATENATE(bitable::$table[tblXr4h68tqh2HDy].$field[fldD86odYI],"-",'
    'bitable::$table[tblXr4h68tqh2HDy].$field[fldPVR3fmV],"-",'
    "IF(bitable::$table[tblXr4h68tqh2HDy].$field[fld2QxxYLM]!=\"\","
    "bitable::$table[tblXr4h68tqh2HDy].$field[fld2QxxYLM],"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldDVqakla])),"
    '"")',
  ),
  # P2：未确认返工用空串（飞书 BLANK() 在此表会红叹号）
  "fldRKjpJSm": (
    "有效合格数量",
    "IF(bitable::$table[tblXr4h68tqh2HDy].$field[fldLiSoY4f],"
    "IF(bitable::$table[tblXr4h68tqh2HDy].$field[fld1PUlkCs]=\"已确认\","
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldVZIng0t],\"\"),"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldwGDxytk])",
  ),
  "fldUSjeWlU": (
    "有效报废数量",
    "IF(bitable::$table[tblXr4h68tqh2HDy].$field[fldLiSoY4f],"
    "IF(bitable::$table[tblXr4h68tqh2HDy].$field[fld1PUlkCs]=\"已确认\","
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldh22GgsG],\"\"),"
    "IF(ISBLANK(bitable::$table[tblXr4h68tqh2HDy].$field[fldMdRZMnF]),0,"
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldMdRZMnF]))",
  ),
  "fldxv8LUfr": ("是否异常", '"否"'),
  "fldmAoLguU": (
    "管控批状态",
    "TEXT(bitable::$table[tblXr4h68tqh2HDy].$field[fldxfgJtRE].$column[fldjSaGns4])",
  ),
  "fldFPgPdsh": (
    "管控批产品",
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldxfgJtRE].$column[fldEti7fPN].$column[fldixZUPtx]",
  ),
  "flduTFwjwb": (
    "管控批工序",
    "TEXT(bitable::$table[tblXr4h68tqh2HDy].$field[fldxfgJtRE].$column[fldW6msrvH])",
  ),
}


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


def extract_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, list) and value:
        if isinstance(value[0], dict):
            return value[0].get("text")
        return str(value[0])
    if isinstance(value, (int, float)):
        return str(value)
    return str(value) if value != "" else None


def patch_formulas(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    for field_id, (name, expr) in FORMULAS.items():
        if dry_run:
            lines.append(f"[dry-run] {name} ({field_id})")
            continue
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/fields/{field_id}",
            json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
        )
        ok = resp.get("code") == 0
        lines.append(f"{'ok' if ok else 'FAIL'}: {name} — {resp.get('msg', '')}")
    return lines


def verify_samples(client: Client) -> list[str]:
    """Spot-check S-TEST-A chain after formula recalc."""
    time.sleep(8)
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 500})
    items = data.get("data", {}).get("items", [])
    checks: list[str] = []
    by_proc: dict[str, dict] = {}
    for it in items:
        f = it.get("fields", {})
        proc = extract_text(f.get("工序代码"))
        batch = extract_text(f.get("批号文本"))
        if batch == "S-TEST-A" and proc:
            by_proc.setdefault(proc, f)

    for proc, expect_trace in [("#2030", True), ("#4050", True), ("#60", True), ("#70", False)]:
        row = by_proc.get(proc)
        if not row:
            checks.append(f"WARN: no S-TEST-A row for {proc}")
            continue
        batch = extract_text(row.get("批号文本"))
        trace = extract_text(row.get("完整追溯号"))
        valid = row.get("有效合格数量")
        ok_batch = batch == "S-TEST-A"
        ok_trace = bool(trace) if expect_trace else trace in (None, "")
        checks.append(
            f"{'PASS' if ok_batch else 'FAIL'} {proc} 批号={batch!r} | "
            f"{'PASS' if ok_trace else 'FAIL'} 追溯={'有' if trace else '空'} | 有效合格={valid}"
        )
    return checks


def run(dry_run: bool, verify: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_v4_formulas — 生产日志主表公式修复")
    print("-" * 60)
    for line in patch_formulas(client, dry_run):
        print(line)

    if verify and not dry_run:
        print("-" * 60)
        print("抽样验收 (S-TEST-A):")
        for line in verify_samples(client):
            print(line)

    print("-" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Fix v4 greenfield production log formulas")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    args = p.parse_args()
    try:
        return run(args.dry_run, verify=not args.no_verify)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
