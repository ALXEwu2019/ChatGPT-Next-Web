#!/usr/bin/env python3
"""Unit tests for batch summary aggregation (no Feishu API required)."""

import json
import unittest
from pathlib import Path

from sync_batch_summary import (
    ProductionRecord,
    aggregate_records,
    load_config,
    parse_production_records,
    run_sync,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sample_records.json"
CONFIG = Path(__file__).parent / "config.json"


class TestAggregation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)

    def test_2030_region_merge(self):
        recs = [
            ProductionRecord("1", "S-260617-A", "STOPPER", "#2030", "A1", 100, 0, "已确认"),
            ProductionRecord("2", "S-260617-A", "STOPPER", "#2030", "A2", 50, 1, "已确认"),
            ProductionRecord("3", "S-260617-A", "STOPPER", "#2030", "B1", 80, 0, "已确认"),
        ]
        rows = aggregate_records(recs, self.config)
        keys = {r.batch_process_key: r for r in rows}
        self.assertEqual(keys["S-260617-A-#2030-A"].qualified_total, 150)
        self.assertEqual(keys["S-260617-A-#2030-A"].scrap_total, 1)
        self.assertEqual(keys["S-260617-A-#2030-B"].qualified_total, 80)

    def test_60_batch_only(self):
        recs = [
            ProductionRecord("1", "S-260617-A", "STOPPER", "#60", "", 200, 2, "已确认"),
        ]
        rows = aggregate_records(recs, self.config)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].batch_process_key, "S-260617-A-#60")
        self.assertEqual(rows[0].production_area, "")

    def test_fixture_excludes_non_confirmed(self):
        raw = json.loads(FIXTURES.read_text(encoding="utf-8"))
        field_map = self.config["field_mapping"]["production_log"]
        sync_cfg = self.config["sync"]
        recs = parse_production_records(
            raw,
            field_map,
            sync_cfg["include_status"],
            sync_cfg["require_valid_quantities"],
        )
        self.assertEqual(len(recs), 6)
        rows = aggregate_records(recs, self.config)
        keys = {r.batch_process_key for r in rows}
        self.assertIn("S-260617-A-#2030-A", keys)
        self.assertIn("S-260617-A-#2030-B", keys)
        self.assertIn("S-260617-A-#4050-MG02", keys)
        self.assertIn("S-260617-A-#60", keys)
        self.assertIn("S-260618-A-#70", keys)
        a_row = next(r for r in rows if r.batch_process_key == "S-260617-A-#2030-A")
        self.assertEqual(a_row.qualified_total, 500)


class TestFixtureDryRun(unittest.TestCase):
    def test_fixture_mode(self):
        rows = run_sync(load_config(CONFIG), dry_run=True, fixture_path=FIXTURES)
        self.assertGreaterEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()
