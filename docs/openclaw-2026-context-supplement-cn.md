# 2026 Base 飞书 AI 上下文补充包（修正版）

> **用途：** 优化「机加工车间生产日志管理系统（新）」旧库时粘贴给飞书 AI。  
> **重要：** 本库为 **95 字段旧库**，批号来源用 **生产批号-输入** / **（磨床|检测）上道生产记录**，**勿**新建 per-view 字段。

---

## 应用与表 ID

| 项 | 值 |
| --- | --- |
| app_token | `NiyZbKpKfae9x3sUP64cl9SFnRb` |
| 入口 | https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewK5AzZee |
| 生产日志主表 | `tblSw8eYEpe7y1am` |
| 入库批次管控表 | `tblyvJJhyq5KoT4F` |
| 批工序产量汇总 | `tblXonlkdLxrTLXE` |
| 产品表 | `tblWtfgylYSeuDH5` |
| 工序表 | `tblt0I1rLezriVTM` |

---

## 旧库批号字段（v4 语义）

| 字段 | field_id | 用途 |
| --- | --- | --- |
| 生产批号-输入 | `fldZXaX1dj` | 首道 STOPPER#2030、止动块#4050 |
| （磨床）上道生产记录 | `fld2RvZGc7` | STOPPER#4050、止动块#60 |
| （检测）上道生产记录 | `fld7I263ZK` | STOPPER#60/#70、止动块#70/#80 |

**已删除（勿恢复）：** `关联管控批_*`、`上道批号_*` 共 8 个误加字段。

---

## 报工视图

| 视图 | view_id | 批号字段 |
| --- | --- | --- |
| STOPPER-#2030报工 (grid) | `vewK5AzZee` | 生产批号-输入 |
| STOPPER#4050 (form) | `vew5Rb9Urh` | （磨床）上道生产记录 |
| STOPPER#60 (form) | `vew121aeT9` | （检测）上道生产记录 |
| STOPPER#70 (form) | `vew2SbrO7V` | （检测）上道生产记录 |
| 止动块#4050 (form) | `vewEah4EhT` | 生产批号-输入 |
| 止动块#60 (form) | `vew3B1ivXN` | （磨床）上道生产记录 |
| 止动块#70 (form) | `vewbP2DKMa` | （检测）上道生产记录 |
| 止动块#80 (form) | `vew5WATrGc` | （检测）上道生产记录 |

---

## 产品 / 工序 record_id

| 产品 | record_id |
| --- | --- |
| STOPPER | `recyB8Z4Hljubu` |
| 止动块 | `recsxLFXuAXXI0` |

| 工序 | record_id |
| --- | --- |
| #2030 STOPPER | `recAV0kYI0r5LS` |
| #4050 STOPPER | `recpGjOr9LdIrW` |
| #60 STOPPER | `recoEwR8aH1qZ2` |
| #70 STOPPER | `reczlaor8Rv7vZ` |
| #4050 止动块 | `recv94Wg644L3s` |
| #60 止动块 | `rectBainbnqqi0` |
| #70 止动块 | `recFtCShkvImYO` |
| #80 止动块 | `recbaiuSiRHZ0Y` |

---

## 状态机（v4 §8）

- **已报工**：不计入汇总，不可作上道池（现网 25 条默认此状态）
- **已确认 / 已审核**：计入 `sync_batch_summary.py` 汇总

---

## 审计与修正

- 报告：`docs/production-base-v4-audit-cn.md`
- 脚本：`audit_production_base.py`、`remediate_production_base.py`
- 手册：`docs/feishu-p1-manual-setup-2026-cn.md`
