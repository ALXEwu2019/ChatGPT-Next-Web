# P1 手工配置操作手册 · 生产 Base（新）

> **Base：** [机加工车间生产日志管理系统（新）](https://kcnfxml9dtzq.feishu.cn/base/NiyZbKpKfae9x3sUP64cl9SFnRb?table=tblSw8eYEpe7y1am&view=vewQqWVrxH)  
> **app_token：** `NiyZbKpKfae9x3sUP64cl9SFnRb`  
> **预计耗时：** 20–30 分钟（关联筛选飞书 API 无法自动配置，须界面操作）

---

## 配置前确认（API 已完成）

| 项 | 状态 |
| --- | --- |
| 8 个 per-view 选批字段 | ✅ 已创建 |
| #40/#50 废弃视图 | ✅ 已删除 |
| 禁止汇总列 | ✅ 已隐藏/删除 |
| 管控表 批号文本/工序代码/本工序下发数量 | ✅ 8 行已回填 |
| 工序下发状态含「已确认」选项 | ✅ 已添加（现网数据多为「已报工」，汇总脚本两者均认） |

完整 field_id / view_id 见 `docs/openclaw-2026-context-supplement-cn.md`。

---

## 一、上道批号 · 6 个视图关联筛选

### 通用路径

1. 打开 **生产日志主表** `tblSw8eYEpe7y1am`
2. 切换到 **下道报工视图**（见下表）
3. 点击该视图专用的 **上道批号_*** 列头 → **编辑字段** → **筛选关联记录** → **满足所有条件**
4. **不要**添加「有效合格数量>0」（公式字段可能导致保存失败）
5. 保存后确认字段 **不允许多条**（单选）

### 筛选条件

| 视图 | view_id | 字段 field_id | 条件 |
| --- | --- | --- | --- |
| STOPPER#4050生产日志 | `vew5Rb9Urh` | 上道批号_STOPPER#4050 `fldqhOeFGP` | 工序下发状态=**已确认**或**已报工**；工序代码=#2030 `recAV0kYI0r5LS` |
| STOPPER#60检测机生产日志 | `vew121aeT9` | 上道批号_STOPPER#60 `fldfGKKcIq` | 同上；工序代码=#4050 `recpGjOr9LdIrW` |
| STOPPER#70出库填报单 | `vew2SbrO7V` | 上道批号_STOPPER#70 `fld79hDwiF` | 同上；工序代码=#60 `recoEwR8aH1qZ2` |
| 止动块-#60检测机生产日志 | `vew3B1ivXN` | 上道批号_止动块#60 `fld00T5v7e` | 状态=已确认/已报工；工序=#4050 `recv94Wg644L3s`；**产品=止动块** `recsxLFXuAXXI0` |
| 止动块-#70外观检生产日志 | `vewbP2DKMa` | 上道批号_止动块#70 `fldrGiNg9l` | 同上；工序=#60 `rectBainbnqqi0`；产品=止动块 |
| 止动块-#80出库填报单 | `vew5WATrGc` | 上道批号_止动块#80 `fldUG1BLwE` | 同上；工序=#70 `recFtCShkvImYO`；产品=止动块 |

**工序点选：** 在筛选中选「工序表」记录，显示名可能为 `#2030车床自动化-STOPPER`，以 **工序代码 #2030** 为准。

---

## 二、首道 · 2 个关联管控批筛选

### 通用路径

1. 进入 **首道报工视图**
2. 点击 **关联管控批_*** 列 → **编辑字段** → **筛选关联记录** → **满足所有条件**
3. 关联表为 **入库批次管控表** `tblyvJJhyq5KoT4F`

| 视图 | view_id | 字段 field_id | 条件 |
| --- | --- | --- | --- |
| STOPPER-#2030报工 | `vewK5AzZee` | 关联管控批_STOPPER#2030 `fldwq1A1yQ` | 产品=STOPPER `recyB8Z4Hljubu`；工序代码=#2030 `recAV0kYI0r5LS`；批号状态=**已下发** |
| 止动块-#4050磨床生产日志 | `vewEah4EhT` | 关联管控批_止动块#4050 `fld0v2iySA` | 产品=止动块 `recsxLFXuAXXI0`；工序=#4050 `recv94Wg644L3s`；批号状态=已下发 |

---

## 三、管控表 · 合格合计查找（对账）

1. 打开 **入库批次管控表** `tblyvJJhyq5KoT4F`
2. 新增字段 **合格合计**（查找引用）→ 来源 **批工序产量汇总** `tblXonlkdLxrTLXE`
3. 引用 **合格合计** 列，满足 **所有** 条件：

| 汇总表字段 | 运算符 | 管控表字段 |
| --- | --- | --- |
| 批号文本 `fldQGAT11f` | 等于 | 批号文本 `fldTG0SeXm` |
| 产品 `fldNo5CK16` | 等于 | 产品（用产品名称文本或公式转成文本匹配） |
| 工序代码 `fldisD5ip1` | 等于 | 工序代码（关联字段的工序代码文本） |

> 汇总表「产品/工序代码」当前为文本列，查找时需用管控表侧 **公式/查找** 得到可比对文本，或先将汇总表产品/工序改为关联类型。

4. 可选：新增 **对账差异** = 本工序下发数量 − 合格合计

---

## 四、验收

```bash
cd feishu-batch-summary-sync
python3 verify_2026.py
python3 sync_batch_summary.py --config config.2026.json --dry-run -v
```

配置完 8 个视图后，在 STOPPER#4050 视图应能从上道批号选出 `S-260617-A` 等已报工批号。

---

## 五、飞书 AI 一键 Prompt

将 `docs/openclaw-2026-context-supplement-cn.md` + `docs/openclaw-2026-p1-view-filters-prompt-cn.md` 整段粘贴给飞书 AI。
