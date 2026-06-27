#!/usr/bin/env python3
"""管控表对账：从汇总表匹配写入 合格合计 / 对账差异（API 替代查找引用）。

飞书 OpenAPI 无法创建「查找引用」，本脚本在每次 sync 后执行，效果等同四条件查找。

用法:
  python3 sync_control_reconciliation.py --config config.2026.json
  python3 sync_control_reconciliation.py --config config.2026.json --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from remediate_2026_summary import APP, Client, load_2026_config
from sync_batch_summary import extract_text, load_config

CTRL_TABLE = "tblyvJJhyq5KoT4F"
SUM_TABLE = "tblXonlkdLxrTLXE"

PROC_RE = re.compile(r"(#\d+)")


def norm_process(code: str) -> str:
    m = PROC_RE.search(code or "")
    return m.group(1) if m else (code or "").strip()


def ensure_control_fields(client: Client, dry_run: bool) -> list[str]:
    lines: list[str] = []
    fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}

    if "生产区域" not in fields:
        if dry_run:
            lines.append("[dry-run] create 生产区域")
        else:
            r = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields",
                json={"field_name": "生产区域", "type": 1},
            )
            lines.append(f"create 生产区域: {r.get('msg')}")
        fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}

    if "合格合计" not in fields:
        if dry_run:
            lines.append("[dry-run] create 合格合计 (number)")
        else:
            r = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields",
                json={"field_name": "合格合计", "type": 2, "property": {"formatter": "0"}},
            )
            lines.append(f"create 合格合计: {r.get('msg')}")
        fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}

    fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}
    qid = fields["合格合计"]["field_id"]
    qty_id = fields["本工序下发数量"]["field_id"]

    diff_expr = (
        f"bitable::$table[{CTRL_TABLE}].$field[{qid}]"
        f"-bitable::$table[{CTRL_TABLE}].$field[{qty_id}]"
    )
    for name, expr in (("对账差异", diff_expr),):
        if name in fields:
            if dry_run:
                lines.append(f"[dry-run] update formula {name}")
                continue
            r = client.call(
                "PUT",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields/{fields[name]['field_id']}",
                json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
            )
            lines.append(f"update {name}: {r.get('msg')}")
        elif dry_run:
            lines.append(f"[dry-run] create formula {name}")
        else:
            r = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields",
                json={"field_name": name, "type": 20, "property": {"formula_expression": expr}},
            )
            lines.append(f"create {name}: {r.get('msg')}")

    fields = {f["field_name"]: f for f in client.list_fields(CTRL_TABLE)}
    if "对账差异" in fields:
        dd = fields["对账差异"]["field_id"]
        over_expr = f"bitable::$table[{CTRL_TABLE}].$field[{dd}]>0"
        if "是否超产" in fields:
            if not dry_run:
                r = client.call(
                    "PUT",
                    f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields/{fields['是否超产']['field_id']}",
                    json={"field_name": "是否超产", "type": 20, "property": {"formula_expression": over_expr}},
                )
                lines.append(f"update 是否超产: {r.get('msg')}")
        elif dry_run:
            lines.append("[dry-run] create formula 是否超产")
        else:
            r = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/fields",
                json={"field_name": "是否超产", "type": 20, "property": {"formula_expression": over_expr}},
            )
            lines.append(f"create 是否超产: {r.get('msg')}")

    return lines


def build_summary_index(client: Client) -> dict[tuple[str, str, str, str], float]:
    """(批号, 产品, 工序码, 区域) -> 合格合计；区域空串表示无区域维度。"""
    index: dict[tuple[str, str, str, str], float] = defaultdict(float)
    for row in client.list_records(SUM_TABLE):
        f = row.get("fields", {})
        batch = extract_text(f.get("批号文本"))
        product = extract_text(f.get("产品"))
        if product in ("", "{}", "null"):
            continue
        proc = norm_process(extract_text(f.get("工序代码")))
        area = extract_text(f.get("生产区域")) or ""
        qty = f.get("合格合计")
        try:
            val = float(qty) if qty not in (None, "") else 0.0
        except (TypeError, ValueError):
            val = 0.0
        if batch and proc:
            index[(batch, product, proc, area)] += val
    return index


def lookup_qualified(
    index: dict[tuple[str, str, str, str], float],
    batch: str,
    product: str,
    proc: str,
    area: str,
) -> float:
    proc = norm_process(proc)
    if area:
        return index.get((batch, product, proc, area), 0.0)
    # #2030 等无区域管控行：合并同批同工序各区域汇总
    total = 0.0
    prefix = (batch, product, proc)
    for key, val in index.items():
        if key[:3] == prefix:
            total += val
    return total


def reconcile(client: Client, dry_run: bool) -> list[str]:
    index = build_summary_index(client)
    updates: list[dict] = []
    matched = 0
    for row in client.list_records(CTRL_TABLE):
        f = row.get("fields", {})
        batch = extract_text(f.get("批号文本")) or extract_text(f.get("批次号"))
        if not batch:
            continue
        product = extract_text(f.get("产品"))
        proc = extract_text(f.get("工序代码"))
        area = extract_text(f.get("生产区域")) or ""
        qty = lookup_qualified(index, batch, product, proc, area)
        if qty > 0 or f.get("合格合计") not in (None, "", 0):
            updates.append(
                {
                    "record_id": row["record_id"],
                    "fields": {"合格合计": qty},
                }
            )
            if qty > 0:
                matched += 1

    lines = [f"汇总键 {len(index)} 个 · 拟更新管控 {len(updates)} 行 · 有数 {matched} 行"]
    if dry_run:
        lines.append("[dry-run] skip batch_update")
        return lines

    if updates:
        # 飞书 batch_update 每批最多 500
        for i in range(0, len(updates), 100):
            chunk = updates[i : i + 100]
            resp = client.call(
                "POST",
                f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/records/batch_update",
                json={"records": chunk},
            )
            if resp.get("code") != 0:
                lines.append(f"FAIL batch_update: {resp.get('msg')}")
                return lines
        lines.append(f"ok: updated {len(updates)} control rows")
    else:
        lines.append("skip: no updates")
    return lines


RECON_VIEW = "P1·管控对账"
RECON_KEEP = {
    "批次号", "批号文本", "产品", "工序代码", "生产区域", "批号状态",
    "本工序下发数量", "合格合计", "对账差异", "是否超产", "计划数量", "下发日期",
}


def ensure_recon_view(client: Client, dry_run: bool) -> list[str]:
    from advance_v4_extensions import patch_view_columns

    views = {}
    page = None
    while True:
        params: dict = {"page_size": 100}
        if page:
            params["page_token"] = page
        data = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/views", params=params)["data"]
        for v in data["items"]:
            views[v["view_name"]] = v["view_id"]
        if not data.get("has_more"):
            break
        page = data.get("page_token")

    if RECON_VIEW in views:
        vid = views[RECON_VIEW]
        msg = f"skip view: {RECON_VIEW}"
    elif dry_run:
        return [f"[dry-run] create {RECON_VIEW}"]
    else:
        resp = client.call(
            "POST",
            f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/views",
            json={"view_name": RECON_VIEW, "view_type": "grid"},
        )
        vid = resp.get("data", {}).get("view", {}).get("view_id")
        msg = f"create {RECON_VIEW}: {resp.get('msg')}"

    if vid and not dry_run:
        # patch_view_columns uses V4 APP constant; inline minimal patch
        fields = client.list_fields(CTRL_TABLE)
        name_to_id = {f["field_name"]: f["field_id"] for f in fields}
        primary = next(f["field_id"] for f in fields if f.get("is_primary"))
        keep_ids = {primary, *(name_to_id[n] for n in RECON_KEEP if n in name_to_id)}
        hidden = [f["field_id"] for f in fields if f["field_id"] not in keep_ids]
        resp = client.call(
            "PATCH",
            f"/bitable/v1/apps/{APP}/tables/{CTRL_TABLE}/views/{vid}",
            json={"property": {"hidden_fields": hidden}},
        )
        col_msg = f"columns: {resp.get('msg')}"
        return [msg, col_msg]
    return [msg]


def run(config_path: Path, dry_run: bool) -> int:
    cfg = load_config(config_path)
    if cfg["feishu"]["base_app_token"] != APP:
        cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])

    print("sync_control_reconciliation")
    print("=" * 60)
    for line in ensure_control_fields(client, dry_run):
        print(line)
    for line in reconcile(client, dry_run):
        print(line)
    for line in ensure_recon_view(client, dry_run):
        print(line)
    print("=" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path(__file__).with_name("config.2026.json"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    try:
        return run(args.config, args.dry_run)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
