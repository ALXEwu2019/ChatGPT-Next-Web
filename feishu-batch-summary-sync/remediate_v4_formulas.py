#!/usr/bin/env python3
"""Remediate 机加工生产日志 v4 greenfield formula fields on production log main table."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

from process_registry import UPSTREAM_FIELD
from sync_batch_summary import feishu_credentials_ok, load_config

BASE = "https://open.feishu.cn/open-apis"
APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
MAIN = "tblXr4h68tqh2HDy"
TRACE = "tblWv5lus3TI8zM3"
DEFECT = "tblMtQ4aEwlzuhWs"
FLD_DEFECT_LINK = "fldcqqWphC"

# 管控表批号文本列；主表关联管控批列（稳定 id，一般不重建）
CTRL_BATCH_COL = "fldVkXzRxj"
CTRL_LINK = "fldxfgJtRE"
GENERIC_UP = "fldDnQmyR6"
STOPPER_ROOT = "fldfvRkDZf"
ZHIDONG_ROOT = "fldw7KlgX9"

# 按字段名解析 id，避免 PTJ92 上道字段重建后公式引用失效
CTRL_LINK_NAME = "关联管控批"
STOPPER_ROOT_NAME = "关联管控批_STOPPER#2030"
ZHIDONG_ROOT_NAME = "关联管控批_止动块#2030"
GENERIC_UP_NAME = "上道批号"

FIRST_CTRL_NAMES = (CTRL_LINK_NAME, STOPPER_ROOT_NAME, ZHIDONG_ROOT_NAME)

STOPPER_UPSTREAM_PV_NAMES = tuple(
    UPSTREAM_FIELD[("STOPPER", c)] for c in ("#4050", "#60", "#70")
)
ZHIDONG_UPSTREAM_PV_NAMES = tuple(
    UPSTREAM_FIELD[("ZHIDONG", c)] for c in ("#4050", "#60", "#70", "#80")
)
PTJ92_UPSTREAM_PV_NAMES = tuple(
    UPSTREAM_FIELD[("PTJ92", c)] for c in ("#3040", "#50")
)

# per-view 多跳链（字段名）；末段为对应产品首道关联管控批列
MULTI_HOP_CHAIN_NAMES: tuple[tuple[str, ...], ...] = (
    (UPSTREAM_FIELD[("PTJ92", "#50")], UPSTREAM_FIELD[("PTJ92", "#3040")], CTRL_LINK_NAME),
    (UPSTREAM_FIELD[("STOPPER", "#60")], UPSTREAM_FIELD[("STOPPER", "#4050")], STOPPER_ROOT_NAME),
    (
        UPSTREAM_FIELD[("STOPPER", "#70")],
        UPSTREAM_FIELD[("STOPPER", "#60")],
        UPSTREAM_FIELD[("STOPPER", "#4050")],
        STOPPER_ROOT_NAME,
    ),
    (UPSTREAM_FIELD[("ZHIDONG", "#60")], UPSTREAM_FIELD[("ZHIDONG", "#4050")], ZHIDONG_ROOT_NAME),
    (UPSTREAM_FIELD[("ZHIDONG", "#70")], UPSTREAM_FIELD[("ZHIDONG", "#4050")], ZHIDONG_ROOT_NAME),
    (
        UPSTREAM_FIELD[("ZHIDONG", "#70")],
        UPSTREAM_FIELD[("ZHIDONG", "#60")],
        UPSTREAM_FIELD[("ZHIDONG", "#4050")],
        ZHIDONG_ROOT_NAME,
    ),
    (
        UPSTREAM_FIELD[("ZHIDONG", "#80")],
        UPSTREAM_FIELD[("ZHIDONG", "#70")],
        UPSTREAM_FIELD[("ZHIDONG", "#60")],
        UPSTREAM_FIELD[("ZHIDONG", "#4050")],
        ZHIDONG_ROOT_NAME,
    ),
)

UPSTREAM_FIELD_NAMES = frozenset(
    {GENERIC_UP_NAME, *FIRST_CTRL_NAMES, *STOPPER_UPSTREAM_PV_NAMES, *ZHIDONG_UPSTREAM_PV_NAMES, *PTJ92_UPSTREAM_PV_NAMES}
    | {name for chain in MULTI_HOP_CHAIN_NAMES for name in chain}
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


def _fid(name: str, name_to_id: dict[str, str]) -> str:
    field_id = name_to_id.get(name)
    if not field_id:
        raise KeyError(f"主表缺少字段: {name}")
    return field_id


def fetch_upstream_field_ids(client: "Client") -> dict[str, str]:
    """从飞书 API 按字段名解析上道/首道关联列 id。"""
    name_to_id = {f["field_name"]: f["field_id"] for f in client.list_fields(MAIN)}
    missing = sorted(n for n in UPSTREAM_FIELD_NAMES if n not in name_to_id)
    if missing:
        raise RuntimeError(f"主表缺少批号公式依赖字段: {', '.join(missing)}")
    return name_to_id


def build_batch_text_expr(name_to_id: dict[str, str]) -> str:
    """批号文本：首道管控 + 通用上道链 + per-view 上道链。"""
    first_ctrl = (_fid(n, name_to_id) for n in FIRST_CTRL_NAMES)
    stopper_pv = (_fid(n, name_to_id) for n in STOPPER_UPSTREAM_PV_NAMES)
    zhidong_pv = (_fid(n, name_to_id) for n in ZHIDONG_UPSTREAM_PV_NAMES)
    ptj92_pv = (_fid(n, name_to_id) for n in PTJ92_UPSTREAM_PV_NAMES)
    multi = (
        tuple(_fid(n, name_to_id) for n in chain)
        for chain in MULTI_HOP_CHAIN_NAMES
    )

    terms = [_ctrl_batch_term(f) for f in first_ctrl]
    terms.extend(_generic_hops(i) for i in range(1, 5))
    terms.extend(_pv_one_hop(f, STOPPER_ROOT) for f in stopper_pv)
    terms.extend(_pv_one_hop(f, ZHIDONG_ROOT) for f in zhidong_pv)
    terms.extend(_pv_one_hop(f, CTRL_LINK) for f in ptj92_pv)
    terms.extend(_ctrl_batch_term(*chain) for chain in multi)
    return "CONCATENATE(" + ",".join(terms) + ")"


def build_upstream_batch_expr(name_to_id: dict[str, str]) -> str:
    """生产批号_上道：无首道项，其余与批号文本同构。"""
    stopper_pv = (_fid(n, name_to_id) for n in STOPPER_UPSTREAM_PV_NAMES)
    zhidong_pv = (_fid(n, name_to_id) for n in ZHIDONG_UPSTREAM_PV_NAMES)
    ptj92_pv = (_fid(n, name_to_id) for n in PTJ92_UPSTREAM_PV_NAMES)
    multi = (
        tuple(_fid(n, name_to_id) for n in chain)
        for chain in MULTI_HOP_CHAIN_NAMES
    )

    terms = [_generic_hops(i) for i in range(1, 5)]
    terms.extend(_pv_one_hop(f, STOPPER_ROOT) for f in stopper_pv)
    terms.extend(_pv_one_hop(f, ZHIDONG_ROOT) for f in zhidong_pv)
    terms.extend(_pv_one_hop(f, CTRL_LINK) for f in ptj92_pv)
    terms.extend(_ctrl_batch_term(*chain) for chain in multi)
    return "CONCATENATE(" + ",".join(terms) + ")"


def build_formulas(name_to_id: dict[str, str]) -> dict[str, tuple[str, str]]:
    """field_id -> (field_name, formula_expression)"""
    batch_text = build_batch_text_expr(name_to_id)
    upstream_batch = build_upstream_batch_expr(name_to_id)
    return {
        "fldD86odYI": ("批号文本", batch_text),
        "fldvMRl868": (
            "生产批号",
            "bitable::$table[tblXr4h68tqh2HDy].$field[fldD86odYI]",
        ),
        "fldncziHl9": ("生产批号_上道", upstream_batch),
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
        # 是否有不良：按不良明细关联本行 record_id，勿引用日志编号（索引列）
        "fldLiSoY4f": (
            "是否有不良",
            f"IF(bitable::$table[{DEFECT}].COUNTIF(CurrentValue.$column[{FLD_DEFECT_LINK}]=RECORD_ID())>0,1,0)",
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


def patch_formulas(client: Client, dry_run: bool, formulas: dict[str, tuple[str, str]] | None = None) -> list[str]:
    if formulas is None:
        formulas = build_formulas(fetch_upstream_field_ids(client))
    lines: list[str] = []
    for field_id, (name, expr) in formulas.items():
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
    if not feishu_credentials_ok(cfg):
        print("ERROR: 请配置飞书凭证")
        return 1
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    name_to_id = fetch_upstream_field_ids(client)
    ptj3040 = name_to_id.get(UPSTREAM_FIELD[("PTJ92", "#3040")])
    ptj50 = name_to_id.get(UPSTREAM_FIELD[("PTJ92", "#50")])
    print(f"PTJ92 上道字段 id: #3040={ptj3040} #50={ptj50}")

    print("remediate_v4_formulas — 生产日志主表公式修复")
    print("-" * 60)
    if dedupe_upstream:
        print("去重：清空与 per-view 上道重复的通用上道批号")
        for line in dedupe_upstream_links(client, dry_run):
            print(line)
        print("-" * 60)
    for line in patch_formulas(client, dry_run, build_formulas(name_to_id)):
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
