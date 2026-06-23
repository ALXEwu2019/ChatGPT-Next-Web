#!/usr/bin/env python3
"""Import / repair 137 defect linkage rules in Feishu 不良原因联动规则表."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

import requests

from sync_batch_summary import FeishuClient, load_config

LOG = logging.getLogger("import_defect_linkage")
BASE_URL = "https://open.feishu.cn/open-apis"

LINKAGE_TABLE = "tblUyVVrhKQOu1pO"
REASON_TABLE = "tblvX8KSv73TluVk"
PROCESS_TABLE = "tblxbzA1m4mS5rXf"
TSV_PATH = Path(__file__).resolve().parents[1] / "docs" / "defect-linkage-137rows.tsv"

PRODUCT_MAP = {
    "STOPPER": "rechKic8YG1cTc",
    "止动块": "recvnmMdIn6lCo",
    "PTJ92": "recvnngInM41nM",
}

PRODUCT_DISPLAY = {
    "STOPPER": "STOPPER",
    "止动块": "止动块",
    "PTJ92": "PTJ92",
}

MISSING_REASONS = ["总高 5.3", "总高 8.6"]

# Current v4 table uses 不良类型 for 返工/报废 (formerly 默认处置类型).
DISPOSITION_FIELD = "不良类型"
STATUS_FIELD = "启用状态"


def list_all_records(client: FeishuClient, app_token: str, table_id: str) -> list[dict[str, Any]]:
    return client.list_records(app_token, table_id)


def delete_records(client: FeishuClient, app_token: str, table_id: str, record_ids: list[str]) -> None:
    headers = client._headers()
    for i in range(0, len(record_ids), 500):
        chunk = record_ids[i : i + 500]
        resp = requests.post(
            f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_delete",
            headers=headers,
            json={"records": chunk},
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"Batch delete failed: {payload}")


def ensure_reasons(client: FeishuClient, app_token: str) -> dict[str, str]:
    records = list_all_records(client, app_token, REASON_TABLE)
    mapping: dict[str, str] = {}
    for item in records:
        name = item.get("fields", {}).get("原因名称")
        if name:
            mapping[str(name)] = item["record_id"]

    missing = [name for name in MISSING_REASONS if name not in mapping]
    if missing:
        rows = [{"原因代码": name, "原因名称": name, "启用状态": "启用"} for name in missing]
        client.create_records(app_token, REASON_TABLE, rows)
        LOG.info("Created missing reasons: %s", missing)
        records = list_all_records(client, app_token, REASON_TABLE)
        for item in records:
            name = item.get("fields", {}).get("原因名称")
            if name:
                mapping[str(name)] = item["record_id"]

    return mapping


def build_process_map(client: FeishuClient, app_token: str) -> dict[str, str]:
    records = list_all_records(client, app_token, PROCESS_TABLE)
    mapping: dict[str, str] = {}
    for item in records:
        code = item.get("fields", {}).get("工序代码")
        if code and code not in mapping:
            mapping[str(code)] = item["record_id"]
    return mapping


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def rule_name(row: dict[str, str]) -> str:
    return (
        f"{PRODUCT_DISPLAY[row['产品']]}-{row['工序代码']}-"
        f"{row['不良原因名称']}-{row['默认处置类型']}"
    )


def build_payload(
    rows: list[dict[str, str]],
    reason_map: dict[str, str],
    process_map: dict[str, str],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        product = row["产品"]
        process_code = row["工序代码"]
        reason_name = row["不良原因名称"]
        disp = row["默认处置类型"]
        if product not in PRODUCT_MAP:
            raise KeyError(f"Row {idx}: unknown product {product}")
        if process_code not in process_map:
            raise KeyError(f"Row {idx}: unknown process {process_code}")
        if reason_name not in reason_map:
            raise KeyError(f"Row {idx}: unknown reason {reason_name}")

        fields: dict[str, Any] = {
            "关联产品": [PRODUCT_MAP[product]],
            "工序代码": [process_map[process_code]],
            "不良原因": [reason_map[reason_name]],
            DISPOSITION_FIELD: disp,
            STATUS_FIELD: row["启用状态"],
            "规则名称": rule_name(row),
        }
        payloads.append(fields)
    return payloads


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    enabled = sum(1 for r in rows if r["启用状态"] == "启用")
    disabled = len(rows) - enabled
    by_combo: dict[str, int] = {}
    for row in rows:
        key = f"{row['产品']}|{row['工序代码']}"
        by_combo[key] = by_combo.get(key, 0) + 1
    return {"total": len(rows), "enabled": enabled, "disabled": disabled, "by_combo": by_combo}


def verify_records(records: list[dict[str, Any]], rows: list[dict[str, str]]) -> dict[str, Any]:
    def txt(v: Any) -> str:
        if isinstance(v, list) and v:
            return str(v[0].get("text") or (v[0].get("text_arr") or [""])[0])
        return str(v or "")

    actual = set()
    for item in records:
        f = item.get("fields", {})
        prod = txt(f.get("关联产品"))
        if prod == "ZHIDONG":
            prod = "止动块"
        actual.add(
            (
                f.get(DISPOSITION_FIELD),
                prod,
                txt(f.get("工序代码")),
                txt(f.get("不良原因")),
                f.get(STATUS_FIELD),
            )
        )

    expected = set()
    for row in rows:
        expected.add(
            (
                row["默认处置类型"],
                row["产品"],
                row["工序代码"],
                row["不良原因名称"],
                row["启用状态"],
            )
        )

    empty = {
        DISPOSITION_FIELD: sum(1 for r in records if not r.get("fields", {}).get(DISPOSITION_FIELD)),
        STATUS_FIELD: sum(1 for r in records if not r.get("fields", {}).get(STATUS_FIELD)),
        "规则名称": sum(
            1
            for r in records
            if not r.get("fields", {}).get("规则名称")
            or str(r.get("fields", {}).get("规则名称", "")).endswith("-None")
        ),
    }
    return {
        "count": len(records),
        "missing": len(expected - actual),
        "extra": len(actual - expected),
        "empty_fields": empty,
        "ok": len(records) == 137 and not (expected - actual) and not empty[DISPOSITION_FIELD],
    }


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=Path(__file__).with_name("config.json"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-delete", action="store_true")
    parser.add_argument("--repair-only", action="store_true", help="batch_update in place, keep 规则编号")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    app_token = config["feishu"]["base_app_token"]
    client = FeishuClient(config["feishu"]["app_id"], config["feishu"]["app_secret"])

    rows = load_rows(TSV_PATH)
    stats = summarize(rows)
    LOG.info("TSV rows: %s", stats)

    reason_map = ensure_reasons(client, app_token)
    process_map = build_process_map(client, app_token)
    payloads = build_payload(rows, reason_map, process_map)

    existing = list_all_records(client, app_token, LINKAGE_TABLE)
    LOG.info("Existing linkage records: %d", len(existing))

    if args.dry_run:
        LOG.info("Dry run. First payload: %s", payloads[0])
        return 0

    if args.repair_only:
        if not existing:
            LOG.error("repair-only: no existing records")
            return 1

        key_to_rid: dict[tuple[str, ...], str] = {}

        def txt(v: Any) -> str:
            if isinstance(v, list) and v:
                return str(v[0].get("text") or (v[0].get("text_arr") or [""])[0])
            return str(v or "")

        for item in existing:
            f = item.get("fields", {})
            prod = txt(f.get("关联产品"))
            if prod == "ZHIDONG":
                prod = "止动块"
            key = (
                str(f.get(DISPOSITION_FIELD) or ""),
                prod,
                txt(f.get("工序代码")),
                txt(f.get("不良原因")),
                str(f.get(STATUS_FIELD) or ""),
            )
            key_to_rid[key] = item["record_id"]

        updates: list[dict[str, Any]] = []
        for row, fields in zip(rows, payloads, strict=True):
            key = (
                row["默认处置类型"],
                row["产品"],
                row["工序代码"],
                row["不良原因名称"],
                row["启用状态"],
            )
            rid = key_to_rid.get(key)
            if not rid:
                LOG.warning("No existing record for key %s, will create", key)
                client.create_records(app_token, LINKAGE_TABLE, [fields])
                continue
            updates.append({"record_id": rid, "fields": fields})

        if updates:
            client.update_records(app_token, LINKAGE_TABLE, updates)
        LOG.info("Repaired %d linkage records in place", len(updates))
    else:
        if existing and not args.skip_delete:
            delete_records(client, app_token, LINKAGE_TABLE, [r["record_id"] for r in existing])
            LOG.info("Deleted %d existing linkage records", len(existing))
        client.create_records(app_token, LINKAGE_TABLE, payloads)
        LOG.info("Created %d linkage records", len(payloads))

    after = list_all_records(client, app_token, LINKAGE_TABLE)
    check = verify_records(after, rows)
    LOG.info("Verification: %s", json.dumps(check, ensure_ascii=False))
    if after:
        LOG.info("Sample: %s", json.dumps(after[0]["fields"], ensure_ascii=False))
    return 0 if check["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
