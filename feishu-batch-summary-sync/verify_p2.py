#!/usr/bin/env python3
"""P2 acceptance checks: defect detail table, main table P2 fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from sync_batch_summary import load_config

BASE = "https://open.feishu.cn/open-apis"

MAIN = "tblXr4h68tqh2HDy"
DEFECT_DETAIL = "tblMtQ4aEwlzuhWs"
DEFECT_REASON = "tblvX8KSv73TluVk"
DEFECT_LINKAGE = "tblUyVVrhKQOu1pO"  # 不良原因联动规则表，非不良明细表

MAIN_P2_FIELDS = {
    "是否有不良",
    "有效合格数量",
    "有效报废数量",
    "返工后合格数",
    "返工后报废数",
    "工序下发状态",
}

DETAIL_P2_FIELDS = {
    "处置类型",
    "关联生产记录",
    "不良数量",
    "不良原因",
}


def token(cfg: dict) -> str:
    r = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": cfg["feishu"]["app_id"], "app_secret": cfg["feishu"]["app_secret"]},
        timeout=30,
    )
    return r.json()["tenant_access_token"]


def field_names(app: str, table: str, tok: str) -> set[str]:
    h = {"Authorization": f"Bearer {tok}"}
    names: set[str] = set()
    page = None
    while True:
        params: dict = {"page_size": 300}
        if page:
            params["page_token"] = page
        data = requests.get(
            f"{BASE}/bitable/v1/apps/{app}/tables/{table}/fields",
            headers=h,
            params=params,
            timeout=60,
        ).json()["data"]
        names.update(f["field_name"] for f in data["items"])
        if not data.get("has_more"):
            break
        page = data.get("page_token")
    return names


def check(name: str, ok: bool, detail: str) -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name} — {detail}")
    return ok


def main() -> int:
    cfg_path = Path(__file__).with_name("config.json")
    if not cfg_path.exists():
        print("FAIL: config.json missing")
        return 1
    cfg = load_config(cfg_path)
    app = cfg["feishu"]["base_app_token"]
    tok = token(cfg)

    print("P2 验收检查")
    print("-" * 50)
    ok = True

    main_f = field_names(app, MAIN, tok)
    detail_f = field_names(app, DEFECT_DETAIL, tok)
    reason_n = requests.get(
        f"{BASE}/bitable/v1/apps/{app}/tables/{DEFECT_REASON}/records",
        headers={"Authorization": f"Bearer {tok}"},
        params={"page_size": 1},
        timeout=60,
    ).json()["data"].get("total", 0)

    missing_main = MAIN_P2_FIELDS - main_f
    missing_detail = DETAIL_P2_FIELDS - detail_f

    ok &= check(
        "主表 P2 字段",
        not missing_main,
        "齐全" if not missing_main else f"缺 {sorted(missing_main)}",
    )
    ok &= check(
        "不良明细表 P2 字段",
        not missing_detail,
        f"tblMtQ4aEwlzuhWs" + (" 齐全" if not missing_detail else f" 缺 {sorted(missing_detail)}"),
    )
    ok &= check("不良原因库有数据", reason_n >= 46, f"{reason_n} 行")
    ok &= check(
        "表 ID 区分",
        DEFECT_DETAIL != DEFECT_LINKAGE,
        f"明细={DEFECT_DETAIL} 联动={DEFECT_LINKAGE}",
    )

    print("-" * 50)
    print("P2 界面/流程：✅ 2026-06-23 人工验收（有不良→返工→品保确认→已确认）")
    print("待完成：国宝 cron 部署（guobao-cron-deploy-cn.md）")
    print("提示：不良明细表 ID 为 tblMtQ4aEwlzuhWs，非联动规则表 tblUyVVrhKQOu1pO")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
