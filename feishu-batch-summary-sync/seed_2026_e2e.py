#!/usr/bin/env python3
"""2026 生产 Base 试跑：写入约 20 条各工序报工数据并验收 sync。

用法:
  python3 seed_2026_e2e.py --dry-run
  python3 seed_2026_e2e.py --seed
  python3 seed_2026_e2e.py --rework-loop          # 单条不良→返工→确认闭环
  python3 seed_2026_e2e.py --seed --rework-loop   # 全量试跑 + 闭环
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from dataclasses import dataclass

from remediate_2026_p1 import PROD
from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_number, extract_text, run_sync

CTRL = "tblyvJJhyq5KoT4F"
SUM = "tblXonlkdLxrTLXE"
DEFECT = "tblTk6xVopyoCjOF"
REWORK = "tblINpP7IJ67h4d9"

REWORK_BATCH = "S-RW-E2E"
REWORK_DEFECT_QTY = 10
REWORK_OK = 8
REWORK_SCRAP = 2

PROC = {
    ("STOPPER", "#2030"): "recAV0kYI0r5LS",
    ("STOPPER", "#4050"): "recpGjOr9LdIrW",
    ("STOPPER", "#60"): "recoEwR8aH1qZ2",
    ("STOPPER", "#70"): "reczlaor8Rv7vZ",
    ("止动块", "#4050"): "recv94Wg644L3s",
    ("止动块", "#60"): "rectBainbnqqi0",
    ("止动块", "#70"): "recFtCShkvImYO",
    ("止动块", "#80"): "recbaiuSiRHZ0Y",
    ("PTJ92", "#1020"): "recLaql6dh8AQl",
    ("PTJ92", "#3040"): "recikK9BOxOsVr",
    ("PTJ92", "#50"): "recGCZogduCeFj",
}

FIRST_CTRL = {
    ("STOPPER", "#2030"): "关联管控批_STOPPER#2030",
    ("止动块", "#4050"): "关联管控批_止动块#4050",
    ("PTJ92", "#1020"): "关联管控批_PTJ92#1020",
}

UPSTREAM = {
    ("STOPPER", "#4050"): "上道批号_STOPPER#4050",
    ("STOPPER", "#60"): "上道批号_STOPPER#60",
    ("STOPPER", "#70"): "上道批号_STOPPER#70",
    ("止动块", "#60"): "上道批号_止动块#60",
    ("止动块", "#70"): "上道批号_止动块#70",
    ("止动块", "#80"): "上道批号_止动块#80",
    ("PTJ92", "#3040"): "上道批号_PTJ92#3040",
    ("PTJ92", "#50"): "上道批号_PTJ92#50",
}

PRODUCT_COL = {
    "STOPPER": ("产品-STOPPER", "STOPPER"),
    "止动块": ("产品-止动块", "止动块"),
    "PTJ92": ("产品-PTJ92", "PTJ92"),
}

MARKER = {
    ("止动块", "#4050"): "#4050磨床-止动块",
    ("止动块", "#60"): "#60检查机-止动块",
    ("止动块", "#70"): "#70外观检-止动块",
    ("止动块", "#80"): "#80出库-止动块",
    ("PTJ92", "#1020"): "#1020车床自动化-PTJ92",
    ("PTJ92", "#3040"): "#304050-PTJ92",
    ("PTJ92", "#50"): "#60-PTJ92",
}

OPERATOR = "recvmNyu0pAN69"  # 曾亮
SHIFT = "recvmO03wfw8sG"  # 白班
# 2026-06-22 08:00 东八区（供 月日 / 完整追溯号 公式）
REPORT_DATE_MS = int(
    datetime.datetime(2026, 6, 22, 8, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=8))).timestamp()
    * 1000
)


@dataclass
class Step:
    product: str
    code: str
    ok: int = 95
    scrap: int = 2
    extra: dict | None = None
    upstream_key: str | None = None  # key in created dict


def find_control(client: Client, batch_text: str) -> str | None:
    for row in client.list_records(CTRL):
        f = row.get("fields", {})
        if extract_text(f.get("批号文本")) == batch_text or extract_text(f.get("批次号")) == batch_text:
            return row["record_id"]
    return None


def ensure_control(client: Client, batch: str, product: str, proc_code: str, dry_run: bool) -> str:
    existing = find_control(client, batch)
    if existing:
        return existing
    if dry_run:
        return f"dry-ctrl-{batch}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{CTRL}/records",
        json={
            "fields": {
                "批号文本": batch,
                "批次号": batch,
                "产品": [PROD[product]],
                "工序代码": [PROC[(product, proc_code)]],
                "批号状态": "已下发",
                "本工序下发数量": 500,
            }
        },
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create control {batch}: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def create_row(
    client: Client,
    *,
    product: str,
    code: str,
    ctrl_id: str | None,
    upstream_id: str | None,
    extra: dict | None,
    ok: int,
    scrap: int,
    dry_run: bool,
) -> str:
    fields: dict = {
        "操作工": [OPERATOR],
        "班次": [SHIFT],
        "填报日期": REPORT_DATE_MS,
        "投入数量": ok + scrap,
        "良品数量": ok,
        "报废数量": scrap,
        "工序下发状态": "已报工",
    }
    ctrl_field = FIRST_CTRL.get((product, code))
    if ctrl_id and ctrl_field:
        fields[ctrl_field] = [ctrl_id]
    up_field = UPSTREAM.get((product, code))
    if upstream_id and up_field:
        fields[up_field] = [upstream_id]
    prod_col, prod_val = PRODUCT_COL[product]
    fields[prod_col] = prod_val
    marker = MARKER.get((product, code))
    if marker:
        fields[marker] = marker
    if extra:
        fields.update(extra)
    if dry_run:
        return f"dry-{product}-{code}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records",
        json={"fields": fields},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create {product}{code}: {resp.get('msg')} — fields={list(fields)}")
    return resp["data"]["record"]["record_id"]


def confirm_row(client: Client, rid: str, dry_run: bool) -> None:
    if dry_run:
        return
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/{rid}",
        json={"fields": {"工序下发状态": "已确认"}},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"confirm {rid}: {resp.get('msg')}")


def patch_row(client: Client, rid: str, fields: dict, dry_run: bool) -> None:
    if dry_run:
        return
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/{rid}",
        json={"fields": fields},
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"patch {rid}: {resp.get('msg')}")


def field_num(fields: dict, name: str) -> float | None:
    value = fields.get(name)
    if isinstance(value, list) and value:
        value = value[0]
    return extract_number(value)


def find_main_by_batch(client: Client, batch: str, proc_code: str) -> str | None:
    for row in client.list_records(MAIN_TABLE):
        f = row.get("fields", {})
        if extract_text(f.get("批号文本")) == batch and extract_text(f.get("工序代码")) == proc_code:
            return row["record_id"]
    return None


def create_defect(
    client: Client,
    main_id: str,
    qty: int,
    dry_run: bool,
) -> str:
    if dry_run:
        return f"dry-defect-{main_id}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/records",
        json={
            "fields": {
                "关联生产记录": [main_id],
                "不良类型": "返工",
                "实收不良数量": qty,
                "返工任务状态": "待返工",
            }
        },
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create defect: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def create_rework(
    client: Client,
    main_id: str,
    defect_id: str,
    rework_ok: int,
    rework_scrap: int,
    dry_run: bool,
) -> str:
    if dry_run:
        return f"dry-rework-{main_id}"
    resp = client.call(
        "POST",
        f"/bitable/v1/apps/{APP}/tables/{REWORK}/records",
        json={
            "fields": {
                "关联生产记录": [main_id],
                "关联不良明细": [defect_id],
                "返工后合格数": rework_ok,
                "返工后报废数": rework_scrap,
            }
        },
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"create rework: {resp.get('msg')}")
    return resp["data"]["record"]["record_id"]


def link_rework_to_defect(client: Client, defect_id: str, rework_id: str, dry_run: bool) -> None:
    if dry_run:
        return
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{DEFECT}/records/{defect_id}",
        json={
            "fields": {
                "关联返工完成记录": [rework_id],
                "返工任务状态": "待品保确认",
            }
        },
    )
    if resp.get("code") != 0:
        raise RuntimeError(f"link defect→rework: {resp.get('msg')}")


def get_main_fields(client: Client, record_id: str) -> dict:
    resp = client.call("GET", f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/records/{record_id}")
    return resp.get("data", {}).get("record", {}).get("fields", {})


def verify_rework_stage(
    client: Client,
    main_id: str,
    *,
    status: str,
    expect_has_defect: bool,
    expect_valid_ok: float | None,
    expect_valid_scrap: float | None,
    expect_rework_ok: float | None = None,
    dry_run: bool,
) -> list[str]:
    if dry_run:
        return [f"[dry-run] verify {status}"]
    time.sleep(12)
    f = get_main_fields(client, main_id)
    lines: list[str] = []
    got_status = extract_text(f.get("工序下发状态"))
    has_def = (field_num(f, "是否有不良") or 0) > 0
    valid_ok = field_num(f, "有效合格数量")
    valid_scrap = field_num(f, "有效报废数量")
    rework_ok = field_num(f, "返工后合格数")
    lines.append(
        f"{'PASS' if got_status == status else 'FAIL'} 工序下发状态={got_status!r} 期望={status!r}"
    )
    lines.append(
        f"{'PASS' if has_def == expect_has_defect else 'FAIL'} 是否有不良={has_def} 期望={expect_has_defect}"
    )
    if expect_rework_ok is not None:
        lines.append(
            f"{'PASS' if rework_ok == expect_rework_ok else 'FAIL'} 返工后合格数={rework_ok} 期望={expect_rework_ok}"
        )
    if expect_valid_ok is None:
        ok_blank = valid_ok is None or valid_ok == 0
        lines.append(f"{'PASS' if ok_blank else 'FAIL'} 有效合格数量应为空 实际={valid_ok!r}")
    else:
        lines.append(
            f"{'PASS' if valid_ok == expect_valid_ok else 'FAIL'} 有效合格数量={valid_ok} 期望={expect_valid_ok}"
        )
    if expect_valid_scrap is None:
        scrap_blank = valid_scrap is None or valid_scrap == 0
        lines.append(f"{'PASS' if scrap_blank else 'FAIL'} 有效报废数量应为空 实际={valid_scrap!r}")
    else:
        lines.append(
            f"{'PASS' if valid_scrap == expect_valid_scrap else 'FAIL'} 有效报废数量={valid_scrap} 期望={expect_valid_scrap}"
        )
    check = extract_text(f.get("返工校验"))
    if check:
        lines.append(f"{'PASS' if check == '一致' else 'CHECK'} 返工校验={check!r}")
    return lines


def seed_rework_loop(client: Client, dry_run: bool) -> list[str]:
    """单条闭环：报工 → 不良 → 返工完成清单 → 品保确认。"""
    lines: list[str] = []
    existing = find_main_by_batch(client, REWORK_BATCH, "#2030")
    if existing and not dry_run:
        f = get_main_fields(client, existing)
        if (field_num(f, "是否有不良") or 0) > 0 and extract_text(f.get("工序下发状态")) == "已确认":
            lines.append(f"skip: {REWORK_BATCH} 闭环用例已存在 ({existing})")
            return lines

    print(f"\n## 返工闭环 {REWORK_BATCH}")
    ctrl = ensure_control(client, REWORK_BATCH, "STOPPER", "#2030", dry_run)
    main_id = create_row(
        client,
        product="STOPPER",
        code="#2030",
        ctrl_id=ctrl,
        upstream_id=None,
        extra={"#2030STOPPER-生产区域A": "RW1"},
        ok=95,
        scrap=2,
        dry_run=dry_run,
    )
    lines.append(f"1 报工 STOPPER #2030 → {main_id}（已报工，未确认）")

    defect_id = create_defect(client, main_id, REWORK_DEFECT_QTY, dry_run)
    lines.append(f"2 品保录入不良 实收={REWORK_DEFECT_QTY} → {defect_id}")
    patch_row(
        client,
        main_id,
        {"返工数量": REWORK_DEFECT_QTY, "工序下发状态": "待返工"},
        dry_run,
    )
    lines.append("3 主表 → 待返工")

    rework_id = create_rework(client, main_id, defect_id, REWORK_OK, REWORK_SCRAP, dry_run)
    lines.append(
        f"4 班组长返工完成清单 合格={REWORK_OK} 报废={REWORK_SCRAP} → {rework_id}"
    )
    link_rework_to_defect(client, defect_id, rework_id, dry_run)
    patch_row(client, main_id, {"工序下发状态": "待品保确认"}, dry_run)
    lines.append("5 不良/主表 → 待品保确认")

    for line in verify_rework_stage(
        client,
        main_id,
        status="待品保确认",
        expect_has_defect=True,
        expect_valid_ok=None,
        expect_valid_scrap=None,
        expect_rework_ok=REWORK_OK,
        dry_run=dry_run,
    ):
        lines.append(f"  待确认 {line}")

    patch_row(client, main_id, {"工序下发状态": "已确认"}, dry_run)
    lines.append("6 品保确认 → 已确认")

    for line in verify_rework_stage(
        client,
        main_id,
        status="已确认",
        expect_has_defect=True,
        expect_valid_ok=REWORK_OK,
        expect_valid_scrap=REWORK_SCRAP,
        expect_rework_ok=REWORK_OK,
        dry_run=dry_run,
    ):
        lines.append(f"  已确认 {line}")

    return lines


def build_plan() -> list[tuple[str, list[Step]]]:
    """返回 (批号, 工序步骤列表)，合计 20 条主表记录。"""
    return [
        (
            "S-T20-A",
            [
                Step("STOPPER", "#2030", extra={"#2030STOPPER-生产区域A": "A1"}),
                Step("STOPPER", "#2030", extra={"#2030STOPPER-生产区域B": "B1"}),
                Step("STOPPER", "#2030", extra={"#2030STOPPER-生产区域C": "C1"}),
                Step("STOPPER", "#4050", extra={"#4050STOPPER-生产区域_输入": "MG2"}, upstream_key="S-T20-A:#2030:0"),
                Step("STOPPER", "#4050", extra={"#4050STOPPER-生产区域_输入": "MG3"}, upstream_key="S-T20-A:#2030:1"),
                Step("STOPPER", "#4050", extra={"#4050STOPPER-生产区域_输入": "MG4"}, upstream_key="S-T20-A:#2030:2"),
                Step("STOPPER", "#60", extra={"#60检查机-生产区域_输入": "J1"}, upstream_key="S-T20-A:#4050:0"),
                Step("STOPPER", "#60", extra={"#60检查机-生产区域_输入": "J2"}, upstream_key="S-T20-A:#4050:1"),
                Step("STOPPER", "#70", upstream_key="S-T20-A:#60:0"),
            ],
        ),
        (
            "S-T20-B",
            [
                Step("STOPPER", "#2030", extra={"#2030STOPPER-生产区域A": "A2"}),
                Step("STOPPER", "#4050", extra={"#4050STOPPER-生产区域_输入": "MG2"}, upstream_key="S-T20-B:#2030:0"),
                Step("STOPPER", "#60", extra={"#60检查机-生产区域_输入": "J1"}, upstream_key="S-T20-B:#4050:0"),
            ],
        ),
        (
            "Z-T20-A",
            [
                Step("止动块", "#4050"),
                Step("止动块", "#60", upstream_key="Z-T20-A:#4050:0"),
                Step("止动块", "#70", upstream_key="Z-T20-A:#60:0"),
                Step("止动块", "#80", upstream_key="Z-T20-A:#70:0"),
            ],
        ),
        (
            "Z-T20-B",
            [
                Step("止动块", "#4050"),
                Step("止动块", "#60", upstream_key="Z-T20-B:#4050:0"),
            ],
        ),
        (
            "P-T20-A",
            [
                Step("PTJ92", "#1020", extra={"#1020PTJ92 -生产区域_输入": "J1"}),
                Step("PTJ92", "#3040", upstream_key="P-T20-A:#1020:0"),
                Step("PTJ92", "#50", upstream_key="P-T20-A:#3040:0"),
            ],
        ),
    ]


def first_proc(product: str) -> str:
    return {"STOPPER": "#2030", "止动块": "#4050", "PTJ92": "#1020"}[product]


def seed_batch(client: Client, batch: str, steps: list[Step], dry_run: bool) -> list[str]:
    product = steps[0].product
    ctrl = ensure_control(client, batch, product, first_proc(product), dry_run)
    created: dict[str, str] = {}
    ids: list[str] = []
    for i, step in enumerate(steps):
        up_id = None
        if step.upstream_key:
            up_id = created.get(step.upstream_key)
            if not up_id and not dry_run:
                raise RuntimeError(f"missing upstream {step.upstream_key} for {batch} {step.code}")
        rid = create_row(
            client,
            product=step.product,
            code=step.code,
            ctrl_id=ctrl if (step.product, step.code) in FIRST_CTRL else None,
            upstream_id=up_id,
            extra=step.extra,
            ok=step.ok,
            scrap=step.scrap,
            dry_run=dry_run,
        )
        idx = sum(1 for s in steps[:i] if s.code == step.code)
        created[f"{batch}:{step.code}:{idx}"] = rid
        confirm_row(client, rid, dry_run)
        ids.append(rid)
        print(f"  ✓ {batch} {step.code} → {rid}")
    return ids


def verify(client: Client) -> list[str]:
    time.sleep(12)
    recs = client.list_records(MAIN_TABLE)
    lines = [f"主表记录数: {len(recs)}"]
    checks = ("批号文本", "工序代码", "工序名称", "批工序键", "有效合格数量", "工序下发状态")
    for fname in checks:
        n = sum(1 for r in recs if extract_text(r["fields"].get(fname)))
        lines.append(f"  {fname} 有值: {n}/{len(recs)}")
    confirmed = [r for r in recs if extract_text(r["fields"].get("工序下发状态")) == "已确认"]
    lines.append(f"  已确认: {len(confirmed)}/{len(recs)}")
    by_code: dict[str, int] = {}
    for r in confirmed:
        c = extract_text(r["fields"].get("工序代码")) or "?"
        by_code[c] = by_code.get(c, 0) + 1
    lines.append(f"  已确认按工序: {dict(sorted(by_code.items()))}")
    sum_recs = client.list_records(SUM)
    lines.append(f"汇总表行数: {len(sum_recs)}")
    for r in sum_recs[:8]:
        f = r["fields"]
        lines.append(
            f"  汇总 {extract_text(f.get('批工序键'))} 合格={f.get('合格合计')} 报废={f.get('报废合计')}"
        )
    return lines


def run(seed: bool, dry_run: bool, rework_loop: bool) -> int:
    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    plan = build_plan()
    total = sum(len(s) for _, s in plan)
    print("seed_2026_e2e — 2026 各工序试跑")
    print("=" * 60)

    if rework_loop and not seed and not dry_run:
        for line in seed_rework_loop(client, dry_run=False):
            print(line)
        print("\n## sync（闭环行应有效合格=8）")
        rows = run_sync(cfg, dry_run=False)
        print(f"sync 写入/更新 {len(rows)} 行")
        print("=" * 60)
        return 0

    if dry_run:
        print(f"计划写入 {total} 条报工记录（{len(plan)} 个批号）")
        if rework_loop:
            print(f"另加返工闭环 1 条（批号 {REWORK_BATCH} STOPPER #2030）")
        for batch, steps in plan:
            print(f"\n[{batch}] {len(steps)} 条")
            for st in steps:
                print(f"  {st.product} {st.code} upstream={st.upstream_key}")
        if rework_loop:
            seed_rework_loop(client, dry_run=True)
        return 0

    all_ids: list[str] = []
    if seed:
        print(f"计划写入 {total} 条报工记录（{len(plan)} 个批号）")
        for batch, steps in plan:
            print(f"\n## {batch}")
            all_ids.extend(seed_batch(client, batch, steps, dry_run=False))
        print(f"\n已写入并确认 {len(all_ids)} 条")

    if rework_loop:
        for line in seed_rework_loop(client, dry_run=False):
            print(line)

    if seed or rework_loop:
        print("\n## 公式重算后验收")
        for line in verify(client):
            print(line)

    if seed:
        print("\n## sync_batch_summary")
        rows = run_sync(cfg, dry_run=False)
        print(f"sync 写入/更新 {len(rows)} 行")
        print("\n## sync 后汇总表")
        for line in verify(client)[-6:]:
            print(line)

    print("=" * 60)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--seed", action="store_true", help="写入各工序试跑数据并跑 sync")
    p.add_argument(
        "--rework-loop",
        action="store_true",
        help="写入单条不良→返工完成清单→品保确认闭环（批号 S-RW-E2E）",
    )
    args = p.parse_args()
    if not args.seed and not args.dry_run and not args.rework_loop:
        p.error("specify --seed, --rework-loop, or --dry-run")
    try:
        return run(args.seed, args.dry_run, args.rework_loop)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
