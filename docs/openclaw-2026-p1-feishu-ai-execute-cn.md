# 飞书 AI · 2026 生产 Base P1 执行单（一键粘贴）

> Base `NiyZbKpKfae9x3sUP64cl9SFnRb` · P0 已完成，请在本 Base **仅做下列配置**，勿删字段/数据。

---

## 任务 A — 8 个报工 form 的关联筛选（per-view 字段）

打开 **生产日志主表** `tblSw8eYEpe7y1am` → 进入下列 **表单视图** → 点击对应关联字段 → **编辑字段** → **筛选关联记录** → 满足所有条件：

- **STOPPER#2030自动化生产日志** (`vew5XS2d4C`) → 字段 **关联管控批_STOPPER#2030** (`fldQ7m86rl`)
  - 关联表：入库批次管控表 `tblyvJJhyq5KoT4F`
  - 筛选：产品=STOPPER（`recyB8Z4Hljubu`）；工序=#2030（`recAV0kYI0r5LS`）；批号状态=**已下发**（option `optuiw7Px6`）
  - 对照只读视图：**P1·首道池 STOPPER#2030**
- **止动块-#4050磨床生产日志** (`vewEah4EhT`) → 字段 **关联管控批_止动块#4050** (`fldL9IMguv`)
  - 关联表：入库批次管控表 `tblyvJJhyq5KoT4F`
  - 筛选：产品=止动块（`recsxLFXuAXXI0`）；工序=#4050（`recv94Wg644L3s`）；批号状态=**已下发**（option `optuiw7Px6`）
  - 对照只读视图：**P1·首道池 止动块#4050**
- **STOPPER#4050生产日志** (`vew5Rb9Urh`) → 字段 **上道批号_STOPPER#4050** (`fldpH050dZ`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=STOPPER；上道工序=#2030（marker `#2030车床自动化-STOPPER`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 STOPPER#2030→#4050**
- **STOPPER#60检测机生产日志** (`vew121aeT9`) → 字段 **上道批号_STOPPER#60** (`fldElwIQWR`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=STOPPER；上道工序=#4050（marker `#4050磨床-STOPPER`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 STOPPER#4050→#60**
- **STOPPER#70出库填报单** (`vew2SbrO7V`) → 字段 **上道批号_STOPPER#70** (`fldmzrF9Dg`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=STOPPER；上道工序=#60（marker `#60检查机-STOPPER`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 STOPPER#60→#70**
- **止动块-#60检测机生产日志** (`vew3B1ivXN`) → 字段 **上道批号_止动块#60** (`fldkXdHTVy`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=止动块；上道工序=#4050（marker `#4050磨床-止动块`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 止动块#4050→#60**
- **止动块-#70外观检生产日志** (`vewbP2DKMa`) → 字段 **上道批号_止动块#70** (`fldXRdAZRd`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=止动块；上道工序=#60（marker `#60检查机-止动块`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 止动块#60→#70**
- **止动块-#80出库填报单** (`vew5WATrGc`) → 字段 **上道批号_止动块#80** (`fldRFpqBhz`)
  - 关联表：生产日志主表 `tblSw8eYEpe7y1am`
  - 筛选：产品=止动块；上道工序=#70（marker `#70外观检-止动块`）；工序下发状态=**已确认**或**已审核**（option `opt0pDHwcO` / `optdqbYcV3`）
  - **勿加** 有效合格数量>0
  - 对照只读视图：**P1·上道池 止动块#70→#80**

> 说明：首道选 **管控表**；下道选 **主表** 上道已确认行。OpenAPI 无法写入 form 筛选，必须在表单设计器完成。

---

## 任务 B — 管控表「合格合计」（已由脚本自动写入）

**已由 `sync_control_reconciliation.py` 在每次 sync 后写入**（数字列 + 对账差异/是否超产公式）。

打开管控表视图 **P1·管控对账** 验收。若仍想用飞书「查找引用」，可按下列配置（与脚本二选一，勿重复建列）：
2. 设置：
   - 关联表：**批工序产量汇总表** `tblXonlkdLxrTLXE`
   - 引用字段：**合格合计**（`fld58R4m10`）
   - 计算方式：**原值**
3. 匹配条件（4 条，全部满足）：

| # | 管控表字段 | 运算符 | 汇总表字段 |
|---|-----------|--------|-----------|
| 1 | 批号文本 (`fldTG0SeXm`) | 等于 | 批号文本 (`fldQGAT11f`) |
| 2 | 产品 (`fldqCtMsEG`) | 等于 | 产品 (`fldNo5CK16`) |
| 3 | 工序代码 (`fldkyrhKt4`) | 等于 | 工序代码 (`fldisD5ip1`) |
| 4 | 生产区域 | 等于 | 生产区域 (`fldduXaag5`) |

> #2030 行管控表 **生产区域** 可留空；#4050 止动块 MG02/MG03 行须填生产区域与汇总一致。

4. 保存后检查管控表 `S-260617-A` 等行是否出现合格合计数字。

---

## 任务 C — 公式列

在管控表确认存在（任务 B 完成后）：
- **对账差异** = `合格合计 - 本工序下发数量`
- **是否超产** = `对账差异 > 0`

完成后在服务器执行：`python3 remediate_2026_p1.py --fix-all`（自动补公式）

---

## 任务 D — 验收

1. 打开 **P1·首道池** / **P1·上道池** 视图，确认与 form 筛选一致
2. 管理视图 `vewQqWVrxH` 看管控对账
3. 汇总 cron：`sync_batch_summary.py --config config.2026.json`（每天 8/12/20 点）

---

## 禁止

- 勿新建汇总公式列（`#4050汇总*` 等）
- 勿把「已报工」计入汇总（仅 **已确认/已审核**）
- 勿删除 per-view 字段

*生成：`remediate_2026_p1.py`*

