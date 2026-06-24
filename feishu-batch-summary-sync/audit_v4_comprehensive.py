#!/usr/bin/env python3
"""机加工生产日志 V4 全面只读审计（索引列 / 公式链 / 视图 / 联动表）。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from advance_v4_greenfield import APP, MAIN, VIEW_KEEP, Client
from advance_v4_extensions import COMMON_KEEP
from process_registry import FIRST_CTRL_FIELD, OPERATOR_VIEWS, UPSTREAM_FIELD
from remediate_index_column import LOG_NO
from remediate_v4_formulas import FORMULAS
from sync_batch_summary import feishu_credentials_ok, load_config

LINKAGE = "tblUyVVrhKQOu1pO"
DEFECT = "tblMtQ4aEwlzuhWs"
CTRL = "tbl6bCLJThyUaD8U"

BATCH_FIELD_IDS = {"fldD86odYI", "fldvMRl868", "fldncziHl9"}  # 批号文本 / 生产批号 / 生产批号_上道
FORBIDDEN_FORMULA_SUBSTR = ("BLANK(", "fldGXpl2l5")  # 索引列 id 不应出现在其他公式中引用批号环

UPSTREAM_LINK_NAMES = {"上道批号", *UPSTREAM_FIELD.values()}
FIRST_CTRL_NAMES = set(FIRST_CTRL_FIELD.values()) | {"关联管控批"}

PTJ92_VIEW_NAMES = ("PTJ92·#1020报工", "PTJ92·#3040报工", "PTJ92·#50报工")
ZHIDONG_2030_VIEW = "vewBbCamcQ"


@dataclass
class AuditResult:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    warned: list[str] = field(default_factory=list)

    def ok(self, name: str, detail: str = "ok") -> None:
        self.passed.append(f"{name} — {detail}")

    def fail(self, name: str, detail: str) -> None:
        self.failed.append(f"{name} — {detail}")

    def warn(self, name: str, detail: str) -> None:
        self.warned.append(f"{name} — {detail}")

    @property
    def success(self) -> bool:
        return not self.failed


def primary_field(fields: list[dict]) -> dict:
    return next(f for f in fields if f.get("is_primary"))


def formula_expr(f: dict) -> str:
    return (f.get("property") or {}).get("formula_expression") or ""


def link_multiple(f: dict) -> bool | None:
    if f.get("type") != 18:
        return None
    return (f.get("property") or {}).get("multiple")


def audit_index_column(client: Client, res: AuditResult) -> None:
    """索引列（锁定列）：日志编号必须为自动编号，不得为批号公式。"""
    fields = client.list_fields(MAIN)
    pf = primary_field(fields)
    log_f = next((f for f in fields if f["field_id"] == LOG_NO), None)

    if not log_f:
        res.fail("索引列·日志编号", "字段缺失")
        return
    if pf["field_id"] != LOG_NO:
        res.fail("索引列·主字段", f"首列是 {pf['field_name']}({pf['field_id']})，应为日志编号")
    else:
        res.ok("索引列·主字段", "日志编号为首列")

    if log_f.get("type") == 1005:
        res.ok("索引列·类型", "自动编号 type=1005")
    elif log_f.get("type") == 20:
        expr = formula_expr(log_f)
        risky = any(bid in expr for bid in BATCH_FIELD_IDS)
        res.fail(
            "索引列·类型",
            f"日志编号为公式(type=20)，{'含批号列引用(#CIRCLE风险)' if risky else '须恢复自动编号'}",
        )
    else:
        res.fail("索引列·类型", f"type={log_f.get('type')}，应为 1005")

    for f in fields:
        if f["field_id"] == LOG_NO or f.get("type") != 20:
            continue
        expr = formula_expr(f)
        if LOG_NO in expr and f["field_name"] != "日志编号":
            res.fail(f"公式·{f['field_name']}", "引用了日志编号字段，可能形成环")
        if "BLANK(" in expr:
            res.warn(f"公式·{f['field_name']}", "含 BLANK()，飞书可能红叹号")


def audit_canonical_formulas(client: Client, res: AuditResult) -> None:
    fields = {f["field_id"]: f for f in client.list_fields(MAIN)}
    for fid, (name, expected) in FORMULAS.items():
        f = fields.get(fid)
        if not f:
            res.fail(f"公式字段·{name}", f"缺失 field_id={fid}")
            continue
        if f.get("type") != 20:
            res.fail(f"公式字段·{name}", f"type={f.get('type')} 应为 20")
            continue
        got = formula_expr(f)
        if got == expected:
            res.ok(f"公式字段·{name}", "与脚本定稿一致")
        else:
            res.warn(f"公式字段·{name}", "与 remediate_v4_formulas 定稿不一致（可 --fix 重刷）")


def audit_upstream_links(client: Client, res: AuditResult) -> None:
    for f in client.list_fields(MAIN):
        name = f["field_name"]
        if name not in UPSTREAM_LINK_NAMES and name not in FIRST_CTRL_NAMES:
            continue
        if f.get("type") != 18:
            res.fail(f"关联·{name}", f"type={f.get('type')} 应为关联(18)")
            continue
        mult = link_multiple(f)
        target = (f.get("property") or {}).get("table_id")
        if mult is True:
            res.fail(f"关联·{name}", "multiple=true，应改为单选(false)")
        elif mult is False:
            res.ok(f"关联·{name}", f"单选 → {target}")
        else:
            res.warn(f"关联·{name}", f"multiple 未明确: {mult}")


def audit_operator_views(client: Client, res: AuditResult) -> None:
    views = {
        v["view_id"]: v["view_name"]
        for v in client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views", params={"page_size": 100})
        .get("data", {})
        .get("items", [])
    }
    fields = client.list_fields(MAIN)
    name_to_id = {f["field_name"]: f["field_id"] for f in fields}
    primary = primary_field(fields)["field_id"]

    # 8 核心 + PTJ92 + 止动块#2030
    expected_views = set(VIEW_KEEP) | set(OPERATOR_VIEWS) | {ZHIDONG_2030_VIEW}
    for vid in expected_views:
        if vid not in views:
            res.fail(f"视图·{vid}", "不存在")
            continue
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/views/{vid}")
        hidden = set(data.get("data", {}).get("view", {}).get("property", {}).get("hidden_fields") or [])
        fi = data.get("data", {}).get("view", {}).get("property", {}).get("filter_info") or {}
        n_filters = len(fi.get("conditions") or [])
        if vid in VIEW_KEEP:
            keep_names = VIEW_KEEP[vid]
        elif vid == ZHIDONG_2030_VIEW:
            keep_names = COMMON_KEEP | {"关联管控批_止动块#2030", "关联管控批", "生产区域"}
        else:
            product, code = OPERATOR_VIEWS[vid]
            keep_names = COMMON_KEEP.copy()
            fc = FIRST_CTRL_FIELD.get((product, code))
            up = UPSTREAM_FIELD.get((product, code))
            if fc:
                keep_names |= {fc, "关联管控批"}
            if up:
                keep_names |= {up, "上道批号"}
            if code in ("#2030", "#4050") or (product == "ZHIDONG" and code == "#2030"):
                keep_names.add("生产区域")
            if code == "#60" or (product == "PTJ92" and code == "#1020"):
                keep_names.add("工位代码")
        want_visible = {primary}
        for n in keep_names:
            if n in name_to_id:
                want_visible.add(name_to_id[n])
        wrongly_hidden = want_visible & hidden
        if wrongly_hidden:
            names = [f["field_name"] for f in fields if f["field_id"] in wrongly_hidden]
            res.fail(f"视图·{views[vid]}", f"必要列被隐藏: {names}")
        else:
            res.ok(f"视图·{views[vid]}", f"列收敛 OK, filters={n_filters}")


def audit_linkage_primary(client: Client, res: AuditResult) -> None:
    fields = client.list_fields(LINKAGE)
    pf = primary_field(fields)
    if pf["field_name"] in ("规则编号", "明细编号"):
        res.ok("联动表·主字段", pf["field_name"])
    elif pf["field_name"] == "不良类型":
        res.fail("联动表·主字段", "不良类型为主字段（锁死且列表无标题），应改为规则编号")
    else:
        res.warn("联动表·主字段", pf["field_name"])
    dup = [f["field_name"] for f in fields if f["field_name"] in ("不良类型", "默认处置类型")]
    if len(dup) == 2:
        res.warn("联动表·重复列", "同时存在不良类型与默认处置类型，建议删不良类型")


def audit_defect_table(client: Client, res: AuditResult) -> None:
    names = {f["field_name"] for f in client.list_fields(DEFECT)}
    required = {"关联生产记录", "处置类型", "不良数量", "不良原因", "状态"}
    missing = required - names
    if missing:
        res.fail("不良明细表", f"缺字段 {sorted(missing)}")
    else:
        res.ok("不良明细表", "P2 核心字段齐全")
    dupes = [n for n in names if " (1)" in n]
    if dupes:
        res.warn("不良明细表", f"重复导入列: {dupes}")


def audit_sample_batches(client: Client, res: AuditResult) -> None:
    data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN}/records", params={"page_size": 100})
    empty_batch = 0
    dup_concat = 0
    for it in data.get("data", {}).get("items", []):
        f = it.get("fields", {})
        batch = f.get("批号文本")
        if isinstance(batch, list) and batch:
            batch = batch[0].get("text") if isinstance(batch[0], dict) else batch[0]
        if f.get("工序下发状态") and not batch and not f.get("关联管控批") and not f.get("上道批号"):
            continue
        if f.get("合格数量") is not None and not batch:
            empty_batch += 1
        if batch and isinstance(batch, str) and re.search(r"(.+)\1", batch.replace("-", "")):
            if "S-TEST-AS-TEST" in str(batch) or str(batch).count("S-TEST-A") > 1:
                dup_concat += 1
    if empty_batch:
        res.warn("批号抽样", f"{empty_batch} 行有产量但批号文本为空")
    else:
        res.ok("批号抽样", "无空批号行")
    if dup_concat:
        res.fail("批号抽样", f"{dup_concat} 行疑似 CONCATENATE 重复拼接")
    else:
        res.ok("批号去重", "无重复拼接迹象")


def run_audit(client: Client) -> AuditResult:
    res = AuditResult()
    print("## 1 索引列（锁定列）")
    audit_index_column(client, res)
    print("## 2 批号 / 有效数公式")
    audit_canonical_formulas(client, res)
    print("## 3 上道 / 管控关联字段")
    audit_upstream_links(client, res)
    print("## 4 报工视图列收敛")
    audit_operator_views(client, res)
    print("## 5 不良原因联动表主字段")
    audit_linkage_primary(client, res)
    print("## 6 不良明细表")
    audit_defect_table(client, res)
    print("## 7 数据抽样")
    audit_sample_batches(client, res)
    return res


def print_result(res: AuditResult) -> int:
    print("-" * 60)
    for line in res.passed:
        print(f"[PASS] {line}")
    for line in res.warned:
        print(f"[WARN] {line}")
    for line in res.failed:
        print(f"[FAIL] {line}")
    print("-" * 60)
    print(f"合计: PASS {len(res.passed)} | WARN {len(res.warned)} | FAIL {len(res.failed)}")
    return 0 if res.success else 2


def main() -> int:
    p = argparse.ArgumentParser(description="V4 全面只读审计")
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    args = p.parse_args()
    cfg = load_config(args.config)
    if not feishu_credentials_ok(cfg):
        print("ERROR: 请配置飞书凭证（config.json / config.local.json / FEISHU_APP_ID+SECRET）")
        return 1
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("audit_v4_comprehensive — 机加工生产日志 V4 全面审计")
    print(f"app: {APP}  main: {MAIN}")
    print("原则: 日志编号保持自动编号；其余按业务逻辑优化")
    print("-" * 60)
    res = run_audit(client)
    return print_result(res)


if __name__ == "__main__":
    sys.exit(main())
