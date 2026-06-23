# 生产 Base · P1 视图关联筛选 · 飞书 AI Prompt

> **前置：** 粘贴 `docs/openclaw-2026-context-supplement-cn.md` 全文。  
> **Base：** `NiyZbKpKfae9x3sUP64cl9SFnRb`

---

<!-- OPENCLAW_2026_P1_VIEWS_BEGIN -->

你是飞书多维表格实施助手。per-view 字段、管控回填、禁止列清理 **已由 API 完成**。本次 **仅配置 8 个报工视图的关联记录筛选**。

### 任务清单

**A. 首道 2 视图 — 关联管控批字段**

| 视图 view_id | 字段 | 筛选（管控表 tblyvJJhyq5KoT4F，满足所有） |
| --- | --- | --- |
| vewK5AzZee | 关联管控批_STOPPER#2030 fldwq1A1yQ | 产品=recyB8Z4Hljubu；工序=recAV0kYI0r5LS(#2030)；批号状态 fldg0qVKFJ=已下发 |
| vewEah4EhT | 关联管控批_止动块#4050 fld0v2iySA | 产品=recsxLFXuAXXI0；工序=recv94Wg644L3s(#4050)；批号状态=已下发 |

**B. 下道 6 视图 — 上道批号字段（关联主表 tblSw8eYEpe7y1am）**

公共条件（STOPPER 三视图）：
- 工序下发状态 fldOUZwxgp = **已报工** 或 **已确认**（二选一即可，勿用有效合格>0）
- 工序代码：点选工序表对应 record_id

| view_id | 字段 field_id | 上道工序 record_id |
| --- | --- | --- |
| vew5Rb9Urh | fldqhOeFGP | recAV0kYI0r5LS (#2030) |
| vew121aeT9 | fldfGKKcIq | recpGjOr9LdIrW (#4050) |
| vew2SbrO7V | fld79hDwiF | recoEwR8aH1qZ2 (#60) |
| vew3B1ivXN | fld00T5v7e | recv94Wg644L3s + **产品=recsxLFXuAXXI0** |
| vewbP2DKMa | fldrGiNg9l | rectBainbnqqi0 + 产品=止动块 |
| vew5WATrGc | fldUG1BLwE | recFtCShkvImYO + 产品=止动块 |

**C. 字段属性**
- 6 个上道批号字段：取消「允许多条」，保持单选
- 各视图 **生产批号** 保持公式/只读，来源上道批号.批号文本 或 生产批号-输入

**D. 管控表合格合计（若时间允许）**
- 在 tblyvJJhyq5KoT4F 建查找引用 → tblXonlkdLxrTLXE.合格合计
- 匹配：批号文本 + 产品 + 工序代码

### 输出
每视图一行表格：| 视图 | 字段 | 已配筛选 | 待人工确认 |
最后列出测试：在 vew5Rb9Urh 能否选到批号 S-260617-A。

### 禁止
- 恢复 #40/#50 视图；添加有效合格>0 筛选；重建 Base

<!-- OPENCLAW_2026_P1_VIEWS_END -->
