"""Canonical product / process record IDs — 工序表 12 行（按产品×工序代码，2026-06-24）."""

from __future__ import annotations

# 产品表 record_id
PROD_STOPPER = "rechKic8YG1cTc"
PROD_ZHIDONG = "recvnmMdIn6lCo"
PROD_PTJ92 = "recvnngInM41nM"

PROD: dict[str, str] = {
    "STOPPER": PROD_STOPPER,
    "ZHIDONG": PROD_ZHIDONG,
    "PTJ92": PROD_PTJ92,
}

# (产品键, 工序代码) → 工序表 record_id
PROC_BY_PRODUCT: dict[tuple[str, str], str] = {
    ("STOPPER", "#2030"): "recC9QvIgUH8oK",
    ("STOPPER", "#4050"): "recs76rS587WRW",
    ("STOPPER", "#60"): "recfoJ5q7gJVtK",
    ("STOPPER", "#70"): "recIZhFG8RKKMI",
    ("ZHIDONG", "#2030"): "recvnmMevC5Dbr",
    ("ZHIDONG", "#4050"): "recAq53nXbm2sg",
    ("ZHIDONG", "#60"): "rec3Pi8IEmA25k",
    ("ZHIDONG", "#70"): "recy0wR8UdunUU",
    ("ZHIDONG", "#80"): "recST53o7KuXQy",
    ("PTJ92", "#1020"): "recRxX5JjvzuEm",
    ("PTJ92", "#3040"): "recvnsaO7aa25k",
    ("PTJ92", "#50"): "recvnsaO7a1Qx6",
}

# 产品工序链：工序代码顺序（首道 → 末道）
CHAINS: dict[str, list[str]] = {
    "STOPPER": ["#2030", "#4050", "#60", "#70"],
    "ZHIDONG": ["#2030", "#4050", "#60", "#70", "#80"],
    "PTJ92": ["#1020", "#3040", "#50"],
}

# 路线表展示名
ROUTE_LABEL: dict[tuple[str, str], str] = {
    ("STOPPER", "#2030"): "STOPPER#2030",
    ("STOPPER", "#4050"): "STOPPER#4050",
    ("STOPPER", "#60"): "STOPPER#60",
    ("STOPPER", "#70"): "STOPPER#70",
    ("ZHIDONG", "#2030"): "止动块#2030",
    ("ZHIDONG", "#4050"): "止动块#4050",
    ("ZHIDONG", "#60"): "止动块#60",
    ("ZHIDONG", "#70"): "止动块#70",
    ("ZHIDONG", "#80"): "止动块#80",
    ("PTJ92", "#1020"): "PTJ92#1020",
    ("PTJ92", "#3040"): "PTJ92#3040",
    ("PTJ92", "#50"): "PTJ92#50",
}

# 汇总维度 / 批号来源（路线表用）
ROUTE_META: dict[tuple[str, str], tuple[str, str]] = {
    ("STOPPER", "#2030"): ("批号+合并区(A/B)", "入库批次管控"),
    ("STOPPER", "#4050"): ("批号+区域(MG)", "上道批号池"),
    ("STOPPER", "#60"): ("仅批号", "上道批号池"),
    ("STOPPER", "#70"): ("仅批号", "上道批号池"),
    ("ZHIDONG", "#2030"): ("批号+合并区(A/B)", "入库批次管控"),
    ("ZHIDONG", "#4050"): ("批号+区域(MG)", "上道批号池"),
    ("ZHIDONG", "#60"): ("仅批号", "上道批号池"),
    ("ZHIDONG", "#70"): ("仅批号", "上道批号池"),
    ("ZHIDONG", "#80"): ("仅批号", "上道批号池"),
    ("PTJ92", "#1020"): ("批号+工位", "入库批次管控"),
    ("PTJ92", "#3040"): ("仅批号", "上道批号池"),
    ("PTJ92", "#50"): ("仅批号", "上道批号池"),
}

# 追溯规则
TRACE_RULES: list[tuple[str, str, str, bool, str, str]] = [
    ("STOPPER-#2030", "STOPPER", "#2030", True, "生产区域", "#2030 末段=A1/A2/B1/B2"),
    ("STOPPER-#4050", "STOPPER", "#4050", True, "生产区域", "#4050 末段=MG区"),
    ("STOPPER-#60", "STOPPER", "#60", True, "工位代码", "#60 末段=J1/J2"),
    ("STOPPER-#70", "STOPPER", "#70", False, "无", "不需要追溯号"),
    ("止动块-#2030", "ZHIDONG", "#2030", True, "生产区域", "A1/A2/B1/B2"),
    ("止动块-#4050", "ZHIDONG", "#4050", True, "生产区域", "MG区"),
    ("止动块-#60", "ZHIDONG", "#60", True, "工位代码", "J1/J2"),
    ("止动块-#70", "ZHIDONG", "#70", False, "无", "不需要追溯号"),
    ("止动块-#80", "ZHIDONG", "#80", False, "无", "不需要追溯号"),
    ("PTJ92-#1020", "PTJ92", "#1020", True, "工位代码", "#1020 首道"),
    ("PTJ92-#3040", "PTJ92", "#3040", False, "无", "不需要追溯号"),
    ("PTJ92-#50", "PTJ92", "#50", False, "无", "检测出库合一"),
]

STATUS_CONFIRMED = "optifE7dfZ"  # 工序下发状态·已确认

# 首道 / 下道专用主表字段名
FIRST_CTRL_FIELD: dict[tuple[str, str], str] = {
    ("STOPPER", "#2030"): "关联管控批_STOPPER#2030",
    ("ZHIDONG", "#2030"): "关联管控批_止动块#2030",
    ("PTJ92", "#1020"): "关联管控批",
}

UPSTREAM_FIELD: dict[tuple[str, str], str] = {
    ("STOPPER", "#4050"): "上道批号_STOPPER#4050",
    ("STOPPER", "#60"): "上道批号_STOPPER#60",
    ("STOPPER", "#70"): "上道批号_STOPPER#70",
    ("ZHIDONG", "#4050"): "上道批号_止动块#4050",
    ("ZHIDONG", "#60"): "上道批号_止动块#60",
    ("ZHIDONG", "#70"): "上道批号_止动块#70",
    ("ZHIDONG", "#80"): "上道批号_止动块#80",
    ("PTJ92", "#3040"): "上道批号_PTJ92#3040",
    ("PTJ92", "#50"): "上道批号_PTJ92#50",
}

# 操作工报工视图 view_id
OPERATOR_VIEWS: dict[str, tuple[str, str]] = {
    "vewfbrQvsu": ("STOPPER", "#2030"),
    "vew7Diocr5": ("STOPPER", "#4050"),
    "vewgS0km1u": ("STOPPER", "#60"),
    "vewqlHptpP": ("STOPPER", "#70"),
    "vewBbCamcQ": ("ZHIDONG", "#2030"),
    "vew4kJ8hxX": ("ZHIDONG", "#4050"),
    "vewEMVET4u": ("ZHIDONG", "#60"),
    "vewUWGnXfU": ("ZHIDONG", "#70"),
    "vewEJZrQu5": ("ZHIDONG", "#80"),
    "vew2SeSRgG": ("PTJ92", "#1020"),
    "vewDNLBqX5": ("PTJ92", "#3040"),
    "vewhTfcmic": ("PTJ92", "#50"),
}


def proc_id(product: str, code: str) -> str:
    key = (product, code)
    if key not in PROC_BY_PRODUCT:
        raise KeyError(f"unknown process: {product} {code}")
    return PROC_BY_PRODUCT[key]


def upstream_code(product: str, code: str) -> str | None:
    chain = CHAINS[product]
    idx = chain.index(code)
    return None if idx == 0 else chain[idx - 1]
