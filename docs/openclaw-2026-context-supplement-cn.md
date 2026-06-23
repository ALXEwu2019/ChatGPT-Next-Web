# 2026 Base 飞书 AI 上下文补充包

> **用途：** 优化「机加工车间生产日志管理系统（新）」时，将 **BEGIN～END** 整段粘贴给飞书 AI。  
> **数据来源：** 2026-06-23 API 实测（app_token 已迁移）

---

## 应用与表 ID

| 项 | 值 |
| --- | --- |
| 应用名称 | 机加工车间生产日志管理系统（新） |
| app_token | `NiyZbKpKfae9x3sUP64cl9SFnRb` |
| 用户入口 | https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewQqWVrxH |
| 生产日志主表 | `tblSw8eYEpe7y1am` |
| 批工序产量汇总 | `tblXonlkdLxrTLXE` |
| 入库批次管控表 | `tblyvJJhyq5KoT4F` |
| 产品表 | `tblWtfgylYSeuDH5` |
| 工序表 | `tblt0I1rLezriVTM` |
| 产品工序对照表 | `tblJkl7htgBX8xMB` |
| 不良原因库 | `tblrQW6JouoEEMGn` |
| 不良原因联动规则表 | `tblABIgbureAlcnU` |
| 不良明细表 | `tblTk6xVopyoCjOF` |

---

## 产品 record_id

| record_id | 产品代码 | 产品名称 |
| --- | --- | --- |
| `recyB8Z4Hljubu` | STOPPER | STOPPER |
| `recsxLFXuAXXI0` | ZDK | 止动块 |
| `recoTeNeaQYuST` | PTJ92 | PTJ92 |

---

## per-view 选批字段（API 已创建）

| 字段名 | field_id | 关联表 |
| --- | --- | --- |
| 关联管控批_STOPPER#2030 | `fldwq1A1yQ` | 入库批次管控表 |
| 关联管控批_止动块#4050 | `fld0v2iySA` | 入库批次管控表 |
| 上道批号_STOPPER#4050 | `fldqhOeFGP` | 生产日志主表 |
| 上道批号_STOPPER#60 | `fldfGKKcIq` | 生产日志主表 |
| 上道批号_STOPPER#70 | `fld79hDwiF` | 生产日志主表 |
| 上道批号_止动块#60 | `fld00T5v7e` | 生产日志主表 |
| 上道批号_止动块#70 | `fldrGiNg9l` | 生产日志主表 |
| 上道批号_止动块#80 | `fldUG1BLwE` | 生产日志主表 |

---

## 报工视图 view_id（#40/#50 已 API 删除）

| 视图名 | view_id | 要配置的字段 |
| --- | --- | --- |
| STOPPER-#2030报工 | `vewK5AzZee` | 关联管控批_STOPPER#2030 |
| STOPPER#4050生产日志 | `vew5Rb9Urh` | 上道批号_STOPPER#4050 |
| STOPPER#60检测机生产日志 | `vew121aeT9` | 上道批号_STOPPER#60 |
| STOPPER#70出库填报单 | `vew2SbrO7V` | 上道批号_STOPPER#70 |
| 止动块-#4050磨床生产日志 | `vewEah4EhT` | 关联管控批_止动块#4050 |
| 止动块-#60检测机生产日志 | `vew3B1ivXN` | 上道批号_止动块#60 |
| 止动块-#70外观检生产日志 | `vewbP2DKMa` | 上道批号_止动块#70 |
| 止动块-#80出库填报单 | `vew5WATrGc` | 上道批号_止动块#80 |

**上道筛选条件：** 工序下发状态=已确认 + 工序代码=上道工序 +（止动块加产品=止动块）。**勿用** 有效合格>0。

**首道管控筛选：** 产品 + 工序 + 批号状态=已下发（管控表 `fldg0qVKFJ`）。

---

## 管控表新增字段（API 已创建）

| 字段 | 说明 |
| --- | --- |
| 批号文本 | 需公式对齐主表批号 |
| 工序代码 | 关联工序表 |
| 本工序下发数量 | 可对齐计划数量 |
| **待建** 合格合计 | 查找引用汇总表 |

---

## 汇总表

| 字段 | 说明 |
| --- | --- |
| 末次同步时间 | 脚本写入 |
| 同步批次号 | 脚本写入 |
| 合格合计/报废合计 | 仅脚本 upsert |

---

## 绿场对照（勿混用 token）

| 项 | 绿场 v4 |
| --- | --- |
| app_token | `CHNKbTKTCaWbQis1vVXcsLvsnDh` |
| P1 详情 | `docs/openclaw-p1-context-supplement-cn.md` |

---

<!-- OPENCLAW_2026_CONTEXT_BEGIN -->
API 已执行：8 个 per-view 字段、5 个废弃视图删除、禁止汇总列隐藏/删除、管控/汇总补字段。剩余：8 视图关联筛选、管控合格合计查找、工序表去重。
<!-- OPENCLAW_2026_CONTEXT_END -->
