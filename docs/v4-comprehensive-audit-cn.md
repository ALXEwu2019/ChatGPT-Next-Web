# 机加工生产日志 V4 · 全面审计与锁定列修复

> **原则：** 生产日志主表 **日志编号** 保持 **自动编号**（索引列/锁定列）；其余字段、视图、公式按业务逻辑优化。  
> **应用：** `HiqNwQnxniKGEGketZBcEC9Sn3d` · 主表 `tblXr4h68tqh2HDy`

---

## 一、「锁定列」含义

| 项 | 要求 |
|----|------|
| **日志编号** `fldGXpl2l5` | 首列 + **type=1005 自动编号**（yyyyMMdd + 3 位流水） |
| **禁止** | 把日志编号改成公式引用 `批号文本` / `生产批号`（会 #CIRCLE 整表红叹号） |
| **上道选批 UX** | 表单用「上道批号（选记录）+ 生产批号（只读）」核对，不改首列 |

联动规则表 `tblUyVVrhKQOu1pO` 的主字段应为 **规则编号**，勿用 **不良类型**（见 `feishu-defect-linkage-fix-primary-field-cn.md`）。

---

## 二、一键执行

```bash
cd feishu-batch-summary-sync
# 配置凭证后：
./run_v4_comprehensive_audit.sh

# 或分步：
python3 audit_v4_comprehensive.py          # 只读审计
python3 remediate_v4_comprehensive.py      # 全面修复 + 修复后审计
```

仅审计、不写飞书：

```bash
python3 audit_v4_comprehensive.py
```

---

## 三、审计项（7 类）

1. **索引列** — 日志编号类型、是否误改公式、其他公式是否引用日志编号  
2. **批号公式** — 与 `remediate_v4_formulas.py` 定稿是否一致  
3. **关联字段** — 上道批号/管控批 `multiple=false`（单选）  
4. **12 工位视图** — 列收敛、筛选是否存在  
5. **联动表主字段** — 规则编号 vs 不良类型  
6. **不良明细表** — P2 核心字段、重复导入列  
7. **数据抽样** — 空批号、CONCATENATE 重复拼接  

---

## 四、修复顺序（`remediate_v4_comprehensive.py`）

| 步骤 | 动作 |
|------|------|
| 1 | 恢复 **日志编号** 自动编号 |
| 2 | 上道/管控关联 → 单选 |
| 3 | 去重双填上道 + 重刷批号/有效数公式 |
| 4 | 8 核心报工视图 `hidden_fields` |
| 5 | `remediate_process_routes.py` — 12 工位筛选 |
| 6 | `setup_role_entrypoints.py` — 三角色视图 |
| 7 | `fix_ptj92_upstream.py` — PTJ92 |
| 8 | `sync_defect_rework_from_2026.py` — 不良/返工 |
| 9 | 联动表选项清理（返工/报废、启用/停用） |
| 10 | `remediate_defect_leader_view.py` — 班组长·待返工 |

**不会执行：** `remediate_index_column.py --apply-safe-index`（已永久禁用）。

---

## 五、仍须飞书界面手工

- 联动表 **规则编号** 设为主字段并删除「不良类型」列  
- 报工/不良表单字段顺序与必填  
- 关联字段筛选（已报工 / 已确认 / 产品+工序）  
- 四条状态机自动化  

---

*v4-comprehensive-audit v1 · 2026-06-24*
