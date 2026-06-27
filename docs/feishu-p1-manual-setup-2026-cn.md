# P1 手工配置手册 · 生产 Base（v4 修正版）

> **重要：** 本库为 **旧库演进版**（95 字段），**不要**使用已删除的 `关联管控批_*` / `上道批号_*` 字段。  
> **审计报告：** `docs/production-base-v4-audit-cn.md`  
> **Base：** https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewK5AzZee

---

## 一、批号来源（旧库 v4 语义映射）

| 工序 | 应操作的字段 | 关联到 |
| --- | --- | --- |
| 首道 STOPPER #2030 | **生产批号-输入** | 入库批次管控表 |
| 首道 止动块 #4050 | **生产批号-输入** | 入库批次管控表 |
| STOPPER #4050 | **（磨床）上道生产记录** | 生产日志主表（#2030 行） |
| STOPPER #60 / #70 | **（检测）上道生产记录** | 生产日志主表（上道工序行） |
| 止动块 #60 | **（磨床）上道生产记录** | 生产日志主表（#4050 行） |
| 止动块 #70 / #80 | **（检测）上道生产记录** | 生产日志主表（上道工序行） |

---

## 二、首道 2 个视图 — `生产批号-输入` 筛选

**路径：** 打开对应 **表单视图** → 点击「生产批号-输入」→ 编辑字段 → 筛选关联记录 → 满足所有条件

| 视图 | view_id | 筛选 |
| --- | --- | --- |
| [STOPPER-#2030报工](https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewK5AzZee) | `vewK5AzZee` | 产品=STOPPER；工序=#2030；批号状态=**已下发** |
| [止动块-#4050](https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewEah4EhT) | `vewEah4EhT` | 产品=止动块；工序=#4050；批号状态=已下发 |

---

## 三、下道 6 个 — `上道生产记录` 筛选

**路径：** 表单视图 → 「（磨床）上道生产记录」或「（检测）上道生产记录」→ 筛选关联记录

| 视图 | view_id | 字段 | 筛选 |
| --- | --- | --- | --- |
| STOPPER#4050 | `vew5Rb9Urh` | （磨床）上道生产记录 | 状态=**已确认**或已审核；工序=#2030 |
| STOPPER#60 | `vew121aeT9` | （检测）上道生产记录 | 同上；工序=#4050 |
| STOPPER#70 | `vew2SbrO7V` | （检测）上道生产记录 | 同上；工序=#60 |
| 止动块#60 | `vew3B1ivXN` | （磨床）上道生产记录 | 状态=已确认/已审核；工序=#4050；**产品=止动块** |
| 止动块#70 | `vewbP2DKMa` | （检测）上道生产记录 | 同上；工序=#60；产品=止动块 |
| 止动块#80 | `vew5WATrGc` | （检测）上道生产记录 | 同上；工序=#70；产品=止动块 |

**注意：**

- **不要**添加「有效合格数量>0」  
- 现网 25 条为「已报工」，计入汇总前须班组长/品保改为 **已确认**（v4 §8）  
- 筛选工序时点选工序表记录（显示名可能含 `-STOPPER` 后缀）

---

## 四、状态与汇总（v4 定稿）

```
已报工  → 不计入脚本汇总，不可作上道池（默认）
已确认  → 计入汇总，可作上道池
已审核  → 计入汇总（若启用）
```

历史数据批量改状态：管理视图筛选「已报工」→ 批量改为「已确认」（品保验收后）。

---

## 五、脚本验收

```bash
cd feishu-batch-summary-sync
python3 remediate_production_base.py   # 若未执行过修正
python3 audit_production_base.py
python3 sync_batch_summary.py --config config.2026.json --dry-run -v
```

---

## 六、飞书 AI

粘贴 `docs/openclaw-2026-context-supplement-cn.md`（修正后）+ 说明使用 **生产批号-输入** 与 **上道生产记录**，勿建 per-view 字段。
