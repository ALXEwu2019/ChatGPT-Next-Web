# 2026 Base 飞书 AI 上下文补充包

> **用途：** 优化「机加工车间生产日志管理系统（新）2026」时，将 **BEGIN～END** 整段粘贴给飞书 AI。  
> **数据来源：** 2026-06-23 API 实测

---

## 应用与表 ID

| 项 | 值 |
| --- | --- |
| 应用名称 | 机加工车间生产日志管理系统（新） 2026 |
| app_token | `P2MtbRCz1a0Pj8sAOtocrHb6ntf` |
| 用户入口视图 | `vewQqWVrxH`（【管理视图】生产批次管控表） |
| 生产日志主表 | `tblolmz13JUyLDFO` |
| 批工序产量汇总 | `tblIygS9QW3mPmIu` |
| 入库批次管控表 | `tbltHNZWMrKAJGWh` |
| 产品表 | `tblkF2fYnyShAiMR` |
| 工序表 | `tblPirQ3ygZPS82h` |
| 产品工序对照表 | `tblhPAqu65L6dUsN` |
| 不良原因库 | `tblBqYPtdnIVh6Ml` |
| 不良原因联动规则表 | `tblYlVXydRLMzPeG` |
| 不良明细表 | `tbl5cpw7wSdjnrox` |

---

## 产品 record_id

| record_id | 产品代码 | 产品名称 |
| --- | --- | --- |
| `recyB8Z4Hljubu` | STOPPER | STOPPER |
| `recsxLFXuAXXI0` | ZDK | 止动块 |
| `recoTeNeaQYuST` | PTJ92 | PTJ92 |

---

## 工序 record_id（当前 12 行，优化后应合并为通用码）

| record_id | 工序代码 | 工序名称（含产品后缀，待去重） |
| --- | --- | --- |
| `recAV0kYI0r5LS` | #2030 | #2030车床自动化-STOPPER |
| `recvmWALPvTrAk` | #2030 | #2030车床自动化-止动块 |
| `recpGjOr9LdIrW` | #4050 | #4050磨床-STOPPER |
| `recv94Wg644L3s` | #4050 | #4050磨床-止动块 |
| `recoEwR8aH1qZ2` | #60 | #60检查机-STOPPER |
| `rectBainbnqqi0` | #60 | #60检查机-止动块 |
| `reczlaor8Rv7vZ` | #70 | #70出库-STOPPER |
| `recFtCShkvImYO` | #70 | #70外观检-止动块 |
| `recbaiuSiRHZ0Y` | #80 | #80出库-止动块 |
| `recLaql6dh8AQl` | #1020 | #1020车床自动化-PTJ92 |
| `recikK9BOxOsVr` | #3040 | #3040-PTJ92 |
| `recGCZogduCeFj` | #50 | #50-PTJ92 |

---

## 主表关键字段 field_id

| 字段名 | field_id | 类型 |
| --- | --- | --- |
| 批号文本 | `fldn9YCUgm` | 公式 |
| 生产批号 | `fldiDpvDL8` | 公式 |
| 产品 | `fldrmvZbgA` | 关联 |
| 工序代码 | `fldwknKvOm` | 关联 |
| 生产区域 | `fldpSt5LMh` | 单选 |
| 工序下发状态 | `fldOUZwxgp` | 单选 |
| 有效合格数量 | `fldhSjn8xF` | 公式 |
| 有效报废数量 | `fldLgCNdFq` | 公式 |
| 完整追溯号 | `fldvkctHVc` | 公式 |
| 填报月日 | `fldJeSAltE` | 公式 |
| #4050选择上道汇总 | `fld2Ylxtlr` | 关联 **待删除** |
| 车床简化批号 | `fldQ3UVcGI` | 公式 **待删除** |

> **缺口：** 当前主表**尚无**绿场版 per-view 字段 `关联管控批_STOPPER#2030`、`上道批号_STOPPER#4050` 等，阶段 C 需新建。

---

## 报工视图 view_id（优化目标 8+2）

### 保留并对齐 v4 的报工视图

| 视图名 | view_id | 产品 | 工序 |
| --- | --- | --- | --- |
| STOPPER-#2030报工 | `vewK5AzZee` | STOPPER | #2030 |
| STOPPER#4050生产日志 | `vew5Rb9Urh` | STOPPER | #4050 |
| STOPPER#60检测机生产日志 | `vew121aeT9` | STOPPER | #60 |
| STOPPER#70出库填报单 | `vew2SbrO7V` | STOPPER | #70 |
| 止动块-#4050磨床生产日志 | `vewEah4EhT` | 止动块 | #4050 |
| 止动块-#60检测机生产日志 | `vew3B1ivXN` | 止动块 | #60 |
| 止动块-#70外观检生产日志 | `vewbP2DKMa` | 止动块 | #70 |
| 止动块-#80出库填报单 | `vew5WATrGc` | 止动块 | #80 |

### 须隐藏（废弃 #40/#50）

| 视图名 | view_id |
| --- | --- |
| STOPPER-#40报工 | `vewutGRS7H` |
| STOPPER-#50检测 | `vew9iD0uOM` |
| 止动块-#40报工 | `vewIhOXmBg` |
| 止动块-#50检测 | `vewNTBCgpS` |
| PTJ92-#50检测出库 | `vew11lWJej` |

---

## 汇总表字段

| 字段名 | field_id |
| --- | --- |
| 批号文本 | `fldQGAT11f` |
| 产品 | `fldNo5CK16` |
| 工序代码 | `fldisD5ip1` |
| 批工序键 | `fldMYivtNb` |
| 合格合计 | `fld58R4m10` |
| 报废合计 | `fldjGhprUG` |
| 末次更新时间 | `fld5Xu4zL6` |

---

## 管控表现状字段

`批次号`、`山中完整批号`、`产品`、`来料数量`、`计划数量`、`下发日期`、`批号状态`、`责任人`、`出库数量`、`备注`、`仓库出入库表`、`主表行ID`、`关联生产记录`

**v4 需补：** `批号文本`、`本工序下发数量`（或映射计划数量）、`工序代码`、`合格合计`（查找汇总表）

---

## 绿场对照（仅参考，勿混用 token）

| 项 | 绿场 v4 |
| --- | --- |
| app_token | `CHNKbTKTCaWbQis1vVXcsLvsnDh` |
| 主表 | `tblXr4h68tqh2HDy` |
| P1 视图/字段详情 | `docs/openclaw-p1-context-supplement-cn.md` |

---

<!-- OPENCLAW_2026_CONTEXT_BEGIN -->
以上 ID 均来自 2026 Base 实网 API。优化时严格按 v4 最终方案：删除选择上道汇总、汇总公式列改脚本、工序表去产品后缀、视图隐藏 #40/#50。
<!-- OPENCLAW_2026_CONTEXT_END -->
