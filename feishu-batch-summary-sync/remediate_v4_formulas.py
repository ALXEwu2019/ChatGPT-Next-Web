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

# 管控表批号文本列；主表关联管控批列
CTRL_BATCH_COL = "fldVkXzRxj"
CTRL_LINK = "fldxfgJtRE"
GENERIC_UP = "fldDnQmyR6"
STOPPER_ROOT = "fldfvRkDZf"
ZHIDONG_ROOT = "fldw7KlgX9"

# 首道 per-view 关联管控批（PTJ92 首道用通用 关联管控批 fldxfgJtRE）
FIRST_CTRL = (CTRL_LINK, STOPPER_ROOT, ZHIDONG_ROOT)

# 下道 per-view 上道批号（按产品根管控列区分）
STOPPER_UPSTREAM_PV = ("fldlSVdUxR", "fldyLk2vMC", "fldICbx5p7")
ZHIDONG_UPSTREAM_PV = ("fldnIvYzdx", "fldvjM58FP", "flds7u3fTQ", "fld8FPWbLM")
PTJ92_UPSTREAM_PV = ("fld09hh79X", "fldaJjkrtj")

# per-view 多跳链：末段为对应产品首道关联管控批列
MULTI_HOP_CHAINS: tuple[tuple[str, ...], ...] = (
    ("fldaJjkrtj", "fld09hh79X", CTRL_LINK),
    ("fldyLk2vMC", "fldlSVdUxR", STOPPER_ROOT),
    ("fldICbx5p7", "fldyLk2vMC", "fldlSVdUxR", STOPPER_ROOT),
    ("fldvjM58FP", "fldnIvYzdx", ZHIDONG_ROOT),
    ("flds7u3fTQ", "fldnIvYzdx", ZHIDONG_ROOT),
    ("flds7u3fTQ", "fldvjM58FP", "fldnIvYzdx", ZHIDONG_ROOT),
    ("fld8FPWbLM", "flds7u3fTQ", "fldvjM58FP", "fldnIvYzdx", ZHIDONG_ROOT),
)


def _ref(field_id: str) -> str:
    return f"bitable::$table[{MAIN}].$field[{field_id}]"


def _ctrl_batch_term(*path: str) -> str:
    """沿关联字段路径读取管控表批号文本。"""
    expr = _ref(path[0])
    for col in path[1:]:
        expr += f".$column[{col}]"
    return expr + f".$column[{CTRL_BATCH_COL}]"


def _generic_hops(n: int) -> str:
    hops = [GENERIC_UP] * n + [CTRL_LINK]
    return _ctrl_batch_term(*hops)


def _pv_one_hop(field_id: str, root: str = CTRL_LINK) -> str:
    return _ctrl_batch_term(field_id, root)


def build_batch_text_expr() -> str:
    """批号文本：首道管控 + 通用上道链 + per-view 上道链。"""
    terms = [_ctrl_batch_term(f) for f in FIRST_CTRL]
    terms.extend(_generic_hops(i) for i in range(1, 5))
    terms.extend(_pv_one_hop(f, STOPPER_ROOT) for f in STOPPER_UPSTREAM_PV)
    terms.extend(_pv_one_hop(f, ZHIDONG_ROOT) for f in ZHIDONG_UPSTREAM_PV)
    terms.extend(_pv_one_hop(f, CTRL_LINK) for f in PTJ92_UPSTREAM_PV)
    terms.extend(_ctrl_batch_term(*chain) for chain in MULTI_HOP_CHAINS)
    return "CONCATENATE(" + ",".join(terms) + ")"


def build_upstream_batch_expr() -> str:
    """生产批号_上道：无首道项，其余与批号文本同构。"""
    terms = [_generic_hops(i) for i in range(1, 5)]
    terms.extend(_pv_one_hop(f, STOPPER_ROOT) for f in STOPPER_UPSTREAM_PV)
    terms.extend(_pv_one_hop(f, ZHIDONG_ROOT) for f in ZHIDONG_UPSTREAM_PV)
    terms.extend(_pv_one_hop(f, CTRL_LINK) for f in PTJ92_UPSTREAM_PV)
    terms.extend(_ctrl_batch_term(*chain) for chain in MULTI_HOP_CHAINS)
    return "CONCATENATE(" + ",".join(terms) + ")"


# field_id -> (field_name, formula_expression)
FORMULAS: dict[str, tuple[str, str]] = {
  "fldD86odYI": ("批号文本", build_batch_text_expr()),
  "fldvMRl868": (
    "生产批号",
    "bitable::$table[tblXr4h68tqh2HDy].$field[fldD86odYI]",
  ),
  "fldncziHl9": ("生产批号_上道", build_upstream_batch_expr()),
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


def has_upstream_link(fields: dict, field_name: str) -> bool:
    v = fields.get(field_name)
    return bool(v and isinstance(v, list) and v[0].get("record_ids"))


PV_UPSTREAM_NAMES = (
    "上道批号_STOPPER#4050",
    "上道批号_STOPPER#60",
    "上道批号_STOPPER#70",
    "上道批号_止动块#4050",
    "上道批号_止动块#60",
    "上道批号_止动块#70",
    "上道批号_止动块#80",
    "上道批号_PTJ92#3040",
    "上道批号_PTJ92#50",
)


def dedupe_upstream_links(client: Client, dry_run: bool) -> list[str]:
    """若已填 per-view 上道批号，清空通用上道批号，避免批号公式 CONCATENATE 重复拼接。"""
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 500})
    lines: list[str] = []
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        if not has_upstream_link(f, "上道批号"):
            continue
        if not any(has_upstream_link(f, name) for name in PV_UPSTREAM_NAMES):
            continue
        rid = it["record_id"]
        if dry_run:
            lines.append(f"[dry-run] clear 上道批号 on {rid}")
            continue
        resp = client.call(
            "PUT",
            f"/bitable/v1/apps/{APP}/tables/{MAIN}/records/{rid}",
            json={"fields": {"上道批号": None}},
        )
        ok = resp.get("code") == 0
        lines.append(f"{'cleared' if ok else 'FAIL'} 上道批号 on {rid}: {resp.get('msg', '')}")
    if not lines:
        lines.append("skip: no dual-filled upstream rows")
    return lines


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
    """Spot-check S-TEST-A / P-TEST-A chains after formula recalc."""
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

    ptj_rows = [
        it for it in items
        if extract_text(it.get("fields", {}).get("工序代码")) in ("#1020", "#3040", "#50")
        and extract_text(it.get("fields", {}).get("批号文本"))
    ]
    if not ptj_rows:
        checks.append("WARN: no PTJ92 rows with 批号文本 (table may be empty)")
    else:
        for it in ptj_rows:
            f = it["fields"]
            proc = extract_text(f.get("工序代码"))
            batch = extract_text(f.get("批号文本"))
            up_pv = any(has_upstream_link(f, n) for n in PV_UPSTREAM_NAMES)
            if proc in ("#3040", "#50") and up_pv:
                ok = bool(batch)
                checks.append(
                    f"{'PASS' if ok else 'FAIL'} PTJ92 {proc} per-view上道 批号={batch!r}"
                )
            elif proc == "#1020":
                ok = bool(batch)
                checks.append(f"{'PASS' if ok else 'FAIL'} PTJ92 #1020 首道 批号={batch!r}")

    dup = [
        extract_text(it.get("fields", {}).get("批号文本"))
        for it in items
        if extract_text(it.get("fields", {}).get("批号文本", "")) and "S-TEST-AS-TEST-A" in str(
            extract_text(it.get("fields", {}).get("批号文本"))
        )
    ]
    checks.append(f"{'PASS' if not dup else 'FAIL'} 无批号重复拼接 (found {len(dup)})")
    return checks


def run(dry_run: bool, verify: bool, dedupe_upstream: bool) -> int:
    cfg = load_config(Path(__file__).with_name("config.json"))
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("remediate_v4_formulas — 生产日志主表公式修复")
    print("-" * 60)
    if dedupe_upstream:
        print("去重：清空与 per-view 上道重复的通用上道批号")
        for line in dedupe_upstream_links(client, dry_run):
            print(line)
        print("-" * 60)
    for line in patch_formulas(client, dry_run):
        print(line)

    if verify and not dry_run:
        print("-" * 60)
        print("抽样验收 (S-TEST-A / P-TEST-A):")
        for line in verify_samples(client):
            print(line)

    print("-" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Fix v4 greenfield production log formulas")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-verify", action="store_true")
    p.add_argument(
        "--dedupe-upstream",
        action="store_true",
        help="清空与 per-view 上道重复的通用上道批号，避免批号 CONCATENATE 重复",
    )
    args = p.parse_args()
    try:
        return run(args.dry_run, verify=not args.no_verify, dedupe_upstream=args.dedupe_upstream)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
