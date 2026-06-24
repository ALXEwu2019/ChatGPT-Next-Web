# 不良明细 / 返工流程：2026 Base → V4 Wiki 对照

> **源：** [2026 机加工生产日志](https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb)  
> **目标：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d)

---

## 一、表结构对照

| 源（2026 Base） | 目标（V4 Wiki） | 说明 |
|----------------|----------------|------|
| `tblTk6xVopyoCjOF` 不良明细表 | `tblMtQ4aEwlzuhWs` 不良明细表 | **品保记不良** |
| `tblINpP7IJ67h4d9` 返工完成清单 | `tblXr4h68tqh2HDy` 生产日志主表 | V4 **不单独建返工表**，班组长在主表回填 |
| `tblSw8eYEpe7y1am` 生产日志主表 | `tblXr4h68tqh2HDy` 生产日志主表 | 关联目标已切换 |
| `tblrQW6JouoEEMGn` 不良原因库 | `tblvX8KSv73TluVk` 不良原因库 | 原因用 **关联** 选记录 |
| `tblABIgbureAlcnU` 联动规则 | `tblUyVVrhKQOu1pO` 联动规则 | 137 条已导入 |

---

## 二、表单对照（源 → V4）

| 源表单 | V4 表单 / 视图 | 角色 | 链接 |
|--------|---------------|------|------|
| 【品保·返工品录入】不良明细录入清单 | **品保·不良录入表单** | 品保 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewhGXZnqB) |
| 【班组长操作】返工完成登记表 | **班组长·返工回填表单** | 班组长 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewzCBs9ta) |
| 【品保操作】品保确认完成单 | **品保·待确认表单** | 品保 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewlHIaE38) |

### 品保·不良录入表单 — 保留字段（上→下）

1. **关联生产记录** ★（选「已报工」的报工行）
2. **生产批号**（只读，公式镜像）
3. **完整追溯号**（只读）
4. **不良数量** ★
5. **不良原因** ★（关联不良原因库）
6. **处置类型** ★（返工 / 报废）

可选只读：**产品**、**工序代码**、**备注**

### 班组长·返工回填表单 — 保留字段

**返工后合格数** ★、**返工后报废数** ★（行状态须为「待返工」）

### 品保·待确认表单 — 保留字段

核对数量后改 **工序下发状态** → **已确认**

> 表单字段顺序须在飞书 **表单设计器** 中手工拖拽（OpenAPI 无法配置表单列）。

---

## 三、字段映射

### 3.1 不良明细表（源 `tblTk6xVopyoCjOF` → V4 `tblMtQ4aEwlzuhWs`）

| 源不良明细 | V4 不良明细 | 说明 |
|-----------|------------|------|
| 不良类型 | **处置类型** | 单选：返工 / 报废 |
| 实收不良数量 | **不良数量** + **实收不良数量** | 两列并存，填报以不良数量为准 |
| 不良原因（单选） | **不良原因** | 关联 `tblvX8KSv73TluVk` |
| 关联生产记录 | **关联生产记录** | → V4 主表 |
| 批号文本 / 产品名称 / 工序 | **生产批号 / 产品 / 工序代码** | 公式镜像 |
| 登记人 / 通知时间 | 同名保留 | 品保记不良时填写 |
| 返工任务状态 | 同名保留 | 待通知→待返工→待品保确认→已完成 |
| 返工后合格数 / 报废数（明细行） | 明细表只读展示 | **班组长实际填主表** |
| 返工人 / 确认人 | 同名保留 | 流程跟踪 |

### 3.2 返工完成清单（源 `tblINpP7IJ67h4d9` → V4 主表）

| 源返工完成清单 | V4 | 说明 |
|---------------|-----|------|
| 关联报工 / 关联生产记录 | **生产日志主表行** | 不单独建返工表 |
| 返工后合格数 | **返工后合格数**（主表） | 班组长·返工回填表单填写 |
| 返工后报废数 | **返工后报废数**（主表） | 同上 |
| 品保确认 | **工序下发状态 → 已确认** | 品保·待确认表单 |

> V4 **刻意不创建**「返工完成清单」独立表，避免双写；状态机与有效数公式均在主表完成。

---

## 四、流程（状态机）

```
操作工报工 → 已报工
    ↓ 品保·不良录入表单：关联生产记录 + 不良数量 + 原因 + 处置类型
主表 → 待返工（自动化规则 2）
    ↓ 班组长·返工回填表单：返工后合格数 / 返工后报废数
主表 → 待品保确认（自动化规则 3）
    ↓ 品保·待确认表单：工序下发状态 → 已确认
主表 → 已确认（有效合格/报废生效，可汇总、可作下道批）
```

**无不良：** 报工保存后自动化直接 **已确认**（规则 1）。

---

## 五、班组长·待返工（不良明细表）

| 项 | 值 |
|----|-----|
| 视图 | **班组长·待返工** `vewy8lBInU` |
| 筛选 | **处置类型 = 返工** 且 **状态 = 待返工** |
| 链接 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewy8lBInU) |

从 2026 Base 导入字段后，若 **处置类型** 误出现日期选项（如 `2026/06/22 15:54`），或视图筛选丢失，执行：

```bash
cd feishu-batch-summary-sync
python3 remediate_defect_leader_view.py
```

脚本会：清理 **处置类型** 选项（仅保留返工/报废）、确保 **状态** 字段、收敛视图列、重建双条件筛选（须带 `field_type`）。

---

## 六、一键配置与验收

```bash
cd feishu-batch-summary-sync
# 推荐：按源库不良明细 + 返工完成清单 一键修复创建 V4
python3 sync_defect_rework_from_2026.py
# 或分步：
python3 setup_defect_workflow.py
python3 remediate_defect_leader_view.py
python3 verify_p2.py
```

仅审计源与 V4 字段差异（不写入）：

```bash
python3 sync_defect_rework_from_2026.py --audit-only
```

---

## 七、须飞书界面手工完成

1. **三张表单** 字段顺序 / 必填（见第二节）
2. **关联生产记录** 字段筛选：工序下发状态 = **已报工**（API 报 LinkFieldPropertyError 时需手配）
3. **不良原因** 关联筛选：按联动规则表的产品 + 工序 + 处置类型
4. **四条自动化**（见 `docs/p2-completion-record-cn.md` §3）
5. 表单 **分享 → 二维码** 给品保 / 班组长

辅助只读视图：**品保·可记不良池**（主表，仅「已报工」行）

---

*不良流程迁移说明 v1 · 2026-06-24*
