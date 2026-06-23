#!/usr/bin/env python3
"""
Sync batch-process yield summary from Feishu production log to summary table.

Rules (v4 greenfield, section 12 confirmed):
- Only records with status = 已确认
- Source: 有效合格数量 / 有效报废数量
- #2030: merge A1/A2 -> A, B1/B2 -> B before aggregation
- #60/#70/#80: batch + product + process only
- #4050: batch + product + process + MG area
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

LOG = logging.getLogger("sync_batch_summary")
BASE_URL = "https://open.feishu.cn/open-apis"


@dataclass
class ProductionRecord:
    record_id: str
    batch_text: str
    product: str
    process_code: str
    production_area: str
    valid_qualified: float
    valid_scrap: float
    status: str


@dataclass
class SummaryRow:
    batch_text: str
    product: str
    process_code: str
    production_area: str
    qualified_total: float
    scrap_total: float
    batch_process_key: str


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    def _headers(self) -> dict[str, str]:
        if not self._token:
            self._token = self._fetch_token()
        return {"Authorization": f"Bearer {self._token}"}

    def _fetch_token(self) -> str:
        resp = requests.post(
            f"{BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Failed to get token: {data}")
        return data["tenant_access_token"]

    def list_records(
        self, app_token: str, table_id: str, page_size: int = 500
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token
            resp = requests.get(
                f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                headers=self._headers(),
                params=params,
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"List records failed: {payload}")
            data = payload["data"]
            records.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token")
        return records

    def list_summary_keys(
        self, app_token: str, table_id: str, key_field: str, page_size: int = 500
    ) -> dict[str, str]:
        """Map batch_process_key -> record_id for upsert."""
        mapping: dict[str, str] = {}
        for item in self.list_records(app_token, table_id, page_size):
            fields = item.get("fields", {})
            key = extract_text(fields.get(key_field))
            if key:
                mapping[key] = item["record_id"]
        return mapping

    def create_records(
        self, app_token: str, table_id: str, rows: list[dict[str, Any]]
    ) -> None:
        for i in range(0, len(rows), 500):
            chunk = rows[i : i + 500]
            resp = requests.post(
                f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                headers=self._headers(),
                json={"records": [{"fields": r} for r in chunk]},
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"Batch create failed: {payload}")

    def update_records(
        self, app_token: str, table_id: str, updates: list[dict[str, Any]]
    ) -> None:
        for i in range(0, len(updates), 500):
            chunk = updates[i : i + 500]
            resp = requests.post(
                f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
                headers=self._headers(),
                json={"records": chunk},
                timeout=60,
            )
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"Batch update failed: {payload}")


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("text") or first.get("name") or "").strip()
        return str(first).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or "").strip()
    return str(value).strip()


def extract_link_record_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    ids: list[str] = []
    for item in value:
        if isinstance(item, dict):
            for rid in item.get("record_ids") or []:
                if rid:
                    ids.append(str(rid))
    return ids


class LinkResolver:
    def __init__(self, client: FeishuClient, app_token: str, link_tables: dict[str, Any]):
        self._cache: dict[str, dict[str, str]] = {}
        self._reverse: dict[str, dict[str, str]] = {}
        self.control_batch: dict[str, str] = {}
        for name, spec in link_tables.items():
            table_id = spec["table_id"]
            fields = spec.get("lookup_fields") or [spec.get("display_field", "")]
            mapping: dict[str, str] = {}
            reverse: dict[str, str] = {}
            for item in client.list_records(app_token, table_id):
                record_id = item["record_id"]
                row_fields = item.get("fields", {})
                for field_name in fields:
                    text = extract_text(row_fields.get(field_name))
                    if text:
                        mapping[record_id] = text
                        reverse[text] = record_id
                        break
            self._cache[name] = mapping
            self._reverse[name] = reverse
            LOG.debug("Link table %s: %d records resolved", name, len(mapping))

        control_spec = link_tables.get("control")
        if control_spec:
            for item in client.list_records(app_token, control_spec["table_id"]):
                batch = extract_text(item.get("fields", {}).get("批号文本"))
                if batch:
                    self.control_batch[item["record_id"]] = batch
            LOG.debug("Control batches: %d", len(self.control_batch))

    def resolve(self, table_name: str, value: Any) -> str:
        ids = extract_link_record_ids(value)
        if ids:
            mapping = self._cache.get(table_name, {})
            hit = mapping.get(ids[0], "")
            if hit:
                return hit
        return extract_text(value)

    def reverse_resolve(self, table_name: str, display_value: str) -> str:
        if not display_value:
            return ""
        return self._reverse.get(table_name, {}).get(display_value, "")

    def batch_from_control_link(self, value: Any) -> str:
        ids = extract_link_record_ids(value)
        if ids and ids[0] in self.control_batch:
            return self.control_batch[ids[0]]
        return ""


def build_record_batch_map(
    raw_records: list[dict[str, Any]], link_resolver: LinkResolver | None
) -> dict[str, str]:
    """Resolve record_id -> batch_text including control/upstream links."""
    id_to_batch: dict[str, str] = {}
    control_keys = (
        "关联管控批",
        "关联管控批_STOPPER#2030",
        "关联管控批_止动块#4050",
    )
    upstream_keys = (
        "上道批号",
        "上道批号_STOPPER#4050",
        "上道批号_STOPPER#60",
        "上道批号_STOPPER#70",
        "上道批号_止动块#60",
        "上道批号_止动块#70",
        "上道批号_止动块#80",
    )

    for item in raw_records:
        rid = item["record_id"]
        fields = item.get("fields", {})
        batch = extract_text(fields.get("批号文本")) or extract_text(fields.get("生产批号"))
        if not batch and link_resolver:
            for key in control_keys:
                batch = link_resolver.batch_from_control_link(fields.get(key))
                if batch:
                    break
        if batch:
            id_to_batch[rid] = batch

    for _ in range(len(raw_records) + 1):
        changed = False
        for item in raw_records:
            rid = item["record_id"]
            if rid in id_to_batch:
                continue
            fields = item.get("fields", {})
            for key in upstream_keys:
                for up_id in extract_link_record_ids(fields.get(key)):
                    if up_id in id_to_batch:
                        id_to_batch[rid] = id_to_batch[up_id]
                        changed = True
                        break
                if rid in id_to_batch:
                    break
        if not changed:
            break
    return id_to_batch


def extract_number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = extract_text(value)
    if not text:
        return 0.0
    return float(text)


def resolve_summary_area(
    process_code: str, production_area: str, region_merge: dict[str, dict[str, str]]
) -> str:
    merge_map = region_merge.get(process_code, {})
    if not merge_map:
        return production_area
    return merge_map.get(production_area, production_area)


def get_aggregation_keys(
    process_code: str, config: dict[str, Any]
) -> list[str]:
    by_process = config.get("aggregation_by_process", {})
    return by_process.get(process_code, config.get("default_aggregation", []))


def build_batch_key(row: dict[str, str], process_code: str, config: dict[str, Any]) -> str:
    formats = config.get("batch_key_format", {})
    template = formats.get(process_code, formats.get("default", "{batch_text}-{process_code}"))
    fmt_row = {**row, "process_code": process_code}
    return template.format(**fmt_row)


def parse_production_records(
    raw_records: list[dict[str, Any]],
    field_map: dict[str, str],
    include_status: list[str],
    require_valid: bool,
    link_resolver: LinkResolver | None = None,
    record_batch_map: dict[str, str] | None = None,
) -> list[ProductionRecord]:
    parsed: list[ProductionRecord] = []
    record_batch_map = record_batch_map or {}
    for item in raw_records:
        fields = item.get("fields", {})
        status = extract_text(fields.get(field_map["status"]))
        if status not in include_status:
            continue

        valid_q = extract_number(fields.get(field_map["valid_qualified"]))
        valid_s = extract_number(fields.get(field_map["valid_scrap"]))
        if require_valid and fields.get(field_map["valid_qualified"]) in (None, ""):
            continue

        batch_text = extract_text(fields.get(field_map["batch_text"]))
        if not batch_text and "batch_text_fallback" in field_map:
            batch_text = extract_text(fields.get(field_map["batch_text_fallback"]))
        if not batch_text:
            batch_text = record_batch_map.get(item["record_id"], "")

        if link_resolver:
            product = link_resolver.resolve("product", fields.get(field_map["product"]))
            process_code = link_resolver.resolve(
                "process", fields.get(field_map["process_code"])
            )
            if not process_code:
                process_code = extract_text(fields.get(field_map["process_code"]))
        else:
            product = extract_text(fields.get(field_map["product"]))
            process_code = extract_text(fields.get(field_map["process_code"]))

        parsed.append(
            ProductionRecord(
                record_id=item["record_id"],
                batch_text=batch_text,
                product=product,
                process_code=process_code,
                production_area=extract_text(fields.get(field_map["production_area"])),
                valid_qualified=valid_q,
                valid_scrap=valid_s,
                status=status,
            )
        )
    return parsed


def aggregate_records(
    records: list[ProductionRecord], config: dict[str, Any]
) -> list[SummaryRow]:
    region_merge = config.get("region_merge", {})
    buckets: dict[tuple[str, ...], dict[str, Any]] = defaultdict(
        lambda: {"qualified": 0.0, "scrap": 0.0, "meta": {}}
    )

    for rec in records:
        if not rec.batch_text or not rec.process_code:
            continue

        summary_area = resolve_summary_area(
            rec.process_code, rec.production_area, region_merge
        )
        dim_values = {
            "batch_text": rec.batch_text,
            "product": rec.product,
            "process_code": rec.process_code,
            "production_area": rec.production_area,
            "summary_area": summary_area,
        }
        agg_keys = get_aggregation_keys(rec.process_code, config)
        bucket_key = tuple(dim_values[k] for k in agg_keys)
        buckets[bucket_key]["qualified"] += rec.valid_qualified
        buckets[bucket_key]["scrap"] += rec.valid_scrap
        buckets[bucket_key]["meta"] = dim_values

    rows: list[SummaryRow] = []
    for bucket in buckets.values():
        meta = bucket["meta"]
        process_code = meta["process_code"]
        summary_area = meta["summary_area"]
        area_for_output = (
            summary_area
            if process_code in region_merge
            else meta["production_area"]
        )
        key_parts = {
            **meta,
            "summary_area": summary_area,
            "production_area": meta["production_area"],
        }
        batch_key = build_batch_key(key_parts, process_code, config)
        rows.append(
            SummaryRow(
                batch_text=meta["batch_text"],
                product=meta["product"],
                process_code=process_code,
                production_area=area_for_output,
                qualified_total=round(bucket["qualified"], 4),
                scrap_total=round(bucket["scrap"], 4),
                batch_process_key=batch_key,
            )
        )
    rows.sort(key=lambda r: r.batch_process_key)
    return rows


def summary_to_fields(
    row: SummaryRow,
    field_map: dict[str, str],
    sync_run_id: str,
    now_ms: int,
    link_resolver: LinkResolver | None = None,
    write_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    write_spec = write_spec or {}
    link_fields = write_spec.get("link_fields", {})
    skip_fields = set(write_spec.get("skip_fields", []))

    fields: dict[str, Any] = {
        field_map["batch_text"]: row.batch_text,
        field_map["qualified_total"]: row.qualified_total,
        field_map["scrap_total"]: row.scrap_total,
        field_map["batch_process_key"]: row.batch_process_key,
        field_map["last_sync_time"]: now_ms,
        field_map["sync_run_id"]: sync_run_id,
    }

    if "production_area" in field_map and "production_area" not in skip_fields:
        if row.production_area:
            fields[field_map["production_area"]] = row.production_area

    for logical_name, value in (
        ("product", row.product),
        ("process_code", row.process_code),
    ):
        if logical_name not in field_map:
            continue
        feishu_field = field_map[logical_name]
        link_table = link_fields.get(logical_name)
        if link_table and link_resolver:
            record_id = link_resolver.reverse_resolve(link_table, value)
            if record_id:
                fields[feishu_field] = [record_id]
            continue
        fields[feishu_field] = value

    return fields


def run_sync(
    config: dict[str, Any],
    dry_run: bool = False,
    fixture_path: Path | None = None,
) -> list[SummaryRow]:
    feishu_cfg = config["feishu"]
    tables = config["tables"]
    pl_fields = config["field_mapping"]["production_log"]
    sum_fields = config["field_mapping"]["batch_summary"]
    sync_cfg = config.get("sync", {})

    if fixture_path:
        with fixture_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        LOG.info("Loaded %d records from fixture %s", len(raw), fixture_path)
    else:
        client = FeishuClient(feishu_cfg["app_id"], feishu_cfg["app_secret"])
        app_token = feishu_cfg["base_app_token"]
        raw = client.list_records(
            app_token, tables["production_log"], sync_cfg.get("page_size", 500)
        )

    link_resolver = None
    record_batch_map: dict[str, str] = {}
    if not fixture_path and config.get("link_tables"):
        client = FeishuClient(feishu_cfg["app_id"], feishu_cfg["app_secret"])
        link_resolver = LinkResolver(
            client, feishu_cfg["base_app_token"], config["link_tables"]
        )
        record_batch_map = build_record_batch_map(raw, link_resolver)

    records = parse_production_records(
        raw,
        pl_fields,
        sync_cfg.get("include_status", ["已确认"]),
        sync_cfg.get("require_valid_quantities", True),
        link_resolver=link_resolver,
        record_batch_map=record_batch_map,
    )
    LOG.info("Fetched %d raw records, %d eligible for aggregation", len(raw), len(records))

    summary_rows = aggregate_records(records, config)
    LOG.info("Aggregated into %d summary rows", len(summary_rows))

    if dry_run or fixture_path:
        return summary_rows

    client = FeishuClient(feishu_cfg["app_id"], feishu_cfg["app_secret"])
    app_token = feishu_cfg["base_app_token"]
    existing = client.list_summary_keys(
        app_token,
        tables["batch_summary"],
        sum_fields["batch_process_key"],
        sync_cfg.get("page_size", 500),
    )
    sync_run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    write_spec = config.get("summary_write", {})

    to_create: list[dict[str, Any]] = []
    to_update: list[dict[str, Any]] = []
    for row in summary_rows:
        fields = summary_to_fields(
            row, sum_fields, sync_run_id, now_ms, link_resolver, write_spec
        )
        record_id = existing.get(row.batch_process_key)
        if record_id:
            to_update.append({"record_id": record_id, "fields": fields})
        else:
            to_create.append(fields)

    if to_create:
        client.create_records(app_token, tables["batch_summary"], to_create)
        LOG.info("Created %d summary records", len(to_create))
    if to_update:
        client.update_records(app_token, tables["batch_summary"], to_update)
        LOG.info("Updated %d summary records", len(to_update))

    return summary_rows


def print_dry_run(rows: list[SummaryRow]) -> None:
    print(f"{'批工序键':<40} {'合格':>10} {'报废':>10}")
    print("-" * 64)
    for row in rows:
        print(
            f"{row.batch_process_key:<40} {row.qualified_total:>10.2f} {row.scrap_total:>10.2f}"
        )
    print(f"\nTotal summary rows: {len(rows)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Feishu batch-process yield summary")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
        help="Path to config.json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print aggregated summary without writing to Feishu",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        nargs="?",
        const=Path(__file__).parent / "fixtures" / "sample_records.json",
        default=None,
        help="Load production log from JSON fixture (default: fixtures/sample_records.json)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = load_config(args.config)
    fixture = args.fixture
    if (
        args.dry_run
        and not fixture
        and config["feishu"].get("app_id") == "YOUR_APP_ID"
    ):
        fixture = Path(__file__).parent / "fixtures" / "sample_records.json"
    rows = run_sync(
        config,
        dry_run=args.dry_run or bool(fixture),
        fixture_path=fixture,
    )
    if args.dry_run:
        print_dry_run(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
