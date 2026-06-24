"""2026 Base 不良明细表 / 返工完成清单 → V4 Wiki 字段与视图规格。"""

from __future__ import annotations

# --- 源（机加工车间生产日志管理系统·新）---
SRC_APP = "NiyZbKpKfae9x3sUP64cl9SFnRb"
SRC_MAIN = "tblSw8eYEpe7y1am"
SRC_DEFECT = "tblTk6xVopyoCjOF"
SRC_REWORK = "tblINpP7IJ67h4d9"
SRC_REASON = "tblrQW6JouoEEMGn"

SRC_FORMS = {
    "品保·不良明细录入": "vewKLH2HSb",
    "班组长·返工完成登记": "vewDhjhzdx",
    "品保·确认完成单": "vew7embFn1",
}

# --- 目标（机加工生产日志 V4 Wiki）---
V4_APP = "HiqNwQnxniKGEGketZBcEC9Sn3d"
V4_MAIN = "tblXr4h68tqh2HDy"
V4_DEFECT = "tblMtQ4aEwlzuhWs"
V4_REASON = "tblvX8KSv73TluVk"

V4_VIEWS = {
    "品保·不良填报": "vewGh4QxtW",
    "品保·不良录入表单": "vewhGXZnqB",
    "班组长·待返工": "vewy8lBInU",
    "班组长·返工回填": "vewQhe4OjQ",
    "班组长·返工回填表单": "vewzCBs9ta",
    "品保·待确认": "vewECvrwqs",
    "品保·待确认表单": "vewlHIaE38",
    "品保·可记不良池": None,  # 由脚本创建
}

# 源不良明细 → V4 不良明细（名称映射；同名列不列出）
SRC_TO_V4_DEFECT = {
    "不良类型": "处置类型",
    "产品名称": "产品",
    "工序": "工序代码",
    "批号文本": "生产批号",
}

# 源返工完成清单 → V4 主表（不单独建返工表）
SRC_TO_V4_MAIN = {
    "返工后合格数": "返工后合格数",
    "返工后报废数": "返工后报废数",
    "关联生产记录": "（主表行本身）",
    "关联报工记录": "（主表行本身）",
}

# V4 不良明细表须具备的字段（type: 飞书字段类型码）
# 公式字段由 setup_defect_workflow 维护，此处只声明存在性
DEFECT_ENSURE_FIELDS: dict[str, dict] = {
    "明细编号": {"type": 1001},
    "关联生产记录": {"type": 18, "link_table": V4_MAIN, "multiple": False},
    "不良数量": {"type": 2, "formatter": "0"},
    "实收不良数量": {"type": 2, "formatter": "0"},
    "不良原因": {"type": 18, "link_table": V4_REASON, "multiple": False},
    "处置类型": {"type": 3, "options": ["返工", "报废"]},
    "状态": {"type": 3, "options": ["待返工", "已返工", "已确认"]},
    "返工任务状态": {
        "type": 3,
        "options": ["待通知", "待返工", "待品保确认", "已完成", "无需返工"],
    },
    "返工完成状态": {"type": 3, "options": ["未完成", "已完成"]},
    "应返工数量": {"type": 2, "formatter": "0"},
    "返工后合格数": {"type": 2, "formatter": "0"},
    "返工后报废数": {"type": 2, "formatter": "0"},
    "登记人": {"type": 11},
    "通知时间": {"type": 5},
    "返工人": {"type": 11},
    "确认人": {"type": 11},
    "备注": {"type": 1},
}

# 公式镜像字段（须存在且 type=20）
DEFECT_FORMULA_FIELDS = ("生产批号", "完整追溯号", "产品", "工序代码")

# V4 主表返工相关（源自返工完成清单语义）
MAIN_REWORK_FIELDS: dict[str, dict] = {
    "返工后合格数": {"type": 2, "formatter": "0"},
    "返工后报废数": {"type": 2, "formatter": "0"},
    "是否有不良": {"type": 7},
    "有效合格数量": {"type": 20},
    "有效报废数量": {"type": 20},
    "工序下发状态": {"type": 3},
}

MAIN_STATUS_OPTIONS = [
    "待报工",
    "已报工",
    "待返工",
    "待品保确认",
    "已确认",
    "已审核",
]

# 视图列收敛
QA_DEFECT_KEEP = {
    "明细编号",
    "关联生产记录",
    "生产批号",
    "完整追溯号",
    "产品",
    "工序代码",
    "不良数量",
    "实收不良数量",
    "不良原因",
    "处置类型",
    "状态",
    "备注",
}

LEADER_DEFECT_KEEP = {
    "关联生产记录",
    "生产批号",
    "产品",
    "工序代码",
    "实收不良数量",
    "不良数量",
    "不良原因",
    "处置类型",
    "不良类型",
    "登记人",
    "通知时间",
    "返工任务状态",
    "返工后合格数",
    "返工后报废数",
    "返工人",
    "确认人",
    "备注",
    "状态",
}

LEADER_MAIN_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "工序下发状态",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "是否有不良",
}

QA_MAIN_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "工序下发状态",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "有效合格数量",
    "有效报废数量",
    "是否有不良",
}

DEFECT_FORM_KEEP = {
    "关联生产记录",
    "生产批号",
    "完整追溯号",
    "产品",
    "工序代码",
    "不良数量",
    "不良原因",
    "处置类型",
    "备注",
}

LEADER_FORM_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "批号文本",
    "生产批号",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
}

QA_FORM_KEEP = {
    "日志编号",
    "产品",
    "工序代码",
    "批号文本",
    "合格数量",
    "报废数量",
    "返工后合格数",
    "返工后报废数",
    "工序下发状态",
}

# 误导入产生的重复字段后缀，审计时告警
DUPLICATE_SUFFIX = " (1)"
