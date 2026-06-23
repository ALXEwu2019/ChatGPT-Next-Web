# 生产 Base · 关联筛选 · 飞书 AI Prompt（修正版）

> **前置：** `docs/openclaw-2026-context-supplement-cn.md`  
> **勿**新建 `关联管控批_*` / `上道批号_*` 字段（已从旧库删除）

<!-- OPENCLAW_2026_P1_VIEWS_BEGIN -->

你是飞书多维表格实施助手。Base：`NiyZbKpKfae9x3sUP64cl9SFnRb`，主表 `tblSw8eYEpe7y1am`。

本库为 **旧库演进版**，按 v4 语义配置 **既有字段** 的关联筛选：

### 首道（生产批号-输入 fldZXaX1dj）

| 表单/视图 | view_id | 筛选（管控表 tblyvJJhyq5KoT4F） |
| --- | --- | --- |
| STOPPER-#2030 | vewK5AzZee | 产品=recyB8Z4Hljubu；工序=recAV0kYI0r5LS；批号状态=已下发 |
| 止动块-#4050 | vewEah4EhT | 产品=recsxLFXuAXXI0；工序=recv94Wg644L3s；批号状态=已下发 |

### 下道（上道生产记录）

| 视图 | 字段 | 上道工序 record_id |
| --- | --- | --- |
| STOPPER#4050 vew5Rb9Urh | （磨床）上道 fld2RvZGc7 | recAV0kYI0r5LS |
| STOPPER#60 vew121aeT9 | （检测）上道 fld7I263ZK | recpGjOr9LdIrW |
| STOPPER#70 vew2SbrO7V | （检测）上道 fld7I263ZK | recoEwR8aH1qZ2 |
| 止动块#60 vew3B1ivXN | （磨床）上道 fld2RvZGc7 | recv94Wg644L3s + 产品=止动块 |
| 止动块#70 vewbP2DKMa | （检测）上道 fld7I263ZK | rectBainbnqqi0 + 产品=止动块 |
| 止动块#80 vew5WATrGc | （检测）上道 fld7I263ZK | recFtCShkvImYO + 产品=止动块 |

筛选条件：**工序下发状态=已确认或已审核** + 工序代码=上道；**勿用** 有效合格>0。

### 表单视图
报工多为 **form 类型**，在表单设计器中编辑上述字段的「筛选关联记录」，不是表格列头。

### 禁止
新建 per-view 字段；恢复 #4050汇总* 公式列；用已报工计入汇总（v4 仅已确认/已审核）

<!-- OPENCLAW_2026_P1_VIEWS_END -->
