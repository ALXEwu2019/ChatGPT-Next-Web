#!/usr/bin/env python3
"""修复 2026 主表「批号文本」公式：首道读管控表批号，下道沿上道链读到管控表批号。

用法:
  python3 fix_2026_batch_text_formula.py --dry-run
  python3 fix_2026_batch_text_formula.py --fix
"""

from __future__ import annotations

import argparse
import sys
import time

from remediate_2026_summary import APP, MAIN_TABLE, Client, load_2026_config
from sync_batch_summary import extract_text

MAIN = MAIN_TABLE
CTRL_BATCH_COL = "fldHJY853n"  # 管控表·批次号（现网列名）
BATCH_TEXT_FIELD = "fldn9YCUgm"

# 首道：关联管控批 → 管控表.批号文本
FIRST_CTRL = (
    "fldQ7m86rl",  # 关联管控批_STOPPER#2030
    "fldL9IMguv",  # 关联管控批_止动块#4050
    "fldn15sQzq",  # 关联管控批_PTJ92#1020
)

# 下道：上道批号 → … → 末段为关联管控批列 → 管控表.批号文本
UPSTREAM_CHAINS: tuple[tuple[str, ...], ...] = (
    ("fldSGcDH2t", "fldQ7m86rl"),  # STOPPER#4050
    ("fldIgshIew", "fldSGcDH2t", "fldQ7m86rl"),  # STOPPER#60
    ("fldJN9WVxn", "fldIgshIew", "fldSGcDH2t", "fldQ7m86rl"),  # STOPPER#70
    ("fldGcZZ2MC", "fldL9IMguv"),  # 止动块#60
    ("fldlFD16M7", "fldGcZZ2MC", "fldL9IMguv"),  # 止动块#70
    ("fldXudQ5F0", "fldlFD16M7", "fldGcZZ2MC", "fldL9IMguv"),  # 止动块#80
    ("fldyTJWQOT", "fldn15sQzq"),  # PTJ92#3040
    ("fldRzTmNOI", "fldyTJWQOT", "fldn15sQzq"),  # PTJ92#50
)


def _term(link_field: str, hops: tuple[str, ...] = ()) -> str:
    expr = f"bitable::$table[{MAIN}].$field[{link_field}]"
    for hop in hops:
        expr += f".$column[{hop}]"
    return expr + f".$column[{CTRL_BATCH_COL}]"


def build_batch_text_expr() -> str:
    terms = [_term(fid) for fid in FIRST_CTRL]
    terms.extend(_term(chain[0], chain[1:]) for chain in UPSTREAM_CHAINS)
    return "CONCATENATE(" + ",".join(terms) + ")"


def patch(client: Client, dry_run: bool) -> str:
    expr = build_batch_text_expr()
    if dry_run:
        return f"[dry-run] 批号文本 formula len={len(expr)}"
    resp = client.call(
        "PUT",
        f"/bitable/v1/apps/{APP}/tables/{MAIN_TABLE}/fields/{BATCH_TEXT_FIELD}",
        json={"field_name": "批号文本", "type": 20, "property": {"formula_expression": expr}},
    )
    if resp.get("code") != 0:
        return f"FAIL: {resp.get('msg', '')}"
    return "ok: 批号文本公式已更新"


def verify(client: Client) -> list[str]:
    time.sleep(10)
    recs = client.list_records(MAIN_TABLE)
    nonempty = 0
    samples: list[str] = []
    for r in recs:
        bt = extract_text(r["fields"].get("批号文本"))
        if bt:
            nonempty += 1
            if len(samples) < 3:
                samples.append(bt)
    return [
        f"批号文本非空: {nonempty}/{len(recs)}",
        f"样例: {', '.join(samples) or '(无)'}",
    ]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--fix", action="store_true")
    p.add_argument("--print-expr", action="store_true")
    args = p.parse_args()
    if args.print_expr:
        print(build_batch_text_expr())
        return 0
    if not args.fix and not args.dry_run:
        p.error("specify --fix or --dry-run")

    cfg = load_2026_config()
    client = Client(cfg["feishu"]["app_id"], cfg["feishu"]["app_secret"])
    print("fix_2026_batch_text_formula")
    print("-" * 60)
    print(patch(client, args.dry_run))
    if args.fix and not args.dry_run:
        for line in verify(client):
            print(line)
    print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
