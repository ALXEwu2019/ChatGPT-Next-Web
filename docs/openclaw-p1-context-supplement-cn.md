# P1 飞书 AI 上下文补充包（完整 ID + 字段 + 数据）

> **用途：** 飞书 AI 反馈「缺少业务实体上下文」时，将本文 **BEGIN～END** 整段粘贴给它，再接 `openclaw-p1-sprint-prompt-cn.md` 执行。  
> **数据来源：** 2026-06-23 API 实测（机加工生产日志 v4 绿场 · Wiki 主战场）

---

## 应用与表 ID


| 项                  | 值                                                                                                                                                                                                                |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 应用名称               | 机加工生产日志 v4                                                                                                                                                                                                       |
| **Wiki 入口**        | [https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1) |
| app_token（wiki）    | `HiqNwQnxniKGEGketZBcEC9Sn3d`                                                                                                                                                                                    |
| app_token（base 等价） | `CHNKbTKTCaWbQis1vVXcsLvsnDh`                                                                                                                                                                                    |
| 生产日志主表             | `tblXr4h68tqh2HDy`                                                                                                                                                                                               |
| 入库批次管控表            | `tbl6bCLJThyUaD8U`                                                                                                                                                                                               |
| 批工序产量汇总表           | `tblu1h0huPW1Mixd`                                                                                                                                                                                               |
| 产品表                | `tblntK7K89dOpJVp`                                                                                                                                                                                               |
| 工序表                | `tblxbzA1m4mS5rXf`                                                                                                                                                                                               |


---

## 一、8 个报工视图 ID + 要改的字段

> 止动块有重复视图名，**优先配置带「报工视图」后缀的 4 个**；简写版可同步或隐藏。

### 首道（2 个）— 改「关联管控批」专用字段


| 视图名               | view_id      | 要配置的字段             | field_id     |
| ----------------- | ------------ | ------------------ | ------------ |
| STOPPER·#2030报工视图 | `vewfbrQvsu` | 关联管控批_STOPPER#2030 | `fldfvRkDZf` |
| 止动块·#4050报工       | `vew4kJ8hxX` | 关联管控批_止动块#4050     | `flde9u7r8S` |


**关联管控批筛选条件（关联→入库批次管控表 `tbl6bCLJThyUaD8U`）：**


| 视图            | 条件                                                               |
| ------------- | ---------------------------------------------------------------- |
| STOPPER·#2030 | 产品 record=`rechKic8YG1cTc`；工序=`recC9QvIgUH8oK`(#2030)；状态=**已下发** |
| 止动块·#4050     | 产品 record=`recvnmMdIn6lCo`；工序=`recs76rS587WRW`(#4050)；状态=**已下发** |


### 下道（6 个）— 改「上道批号」专用字段


| 视图名               | view_id      | 要配置的字段            | field_id     | 上道工序 record_id           |
| ----------------- | ------------ | ----------------- | ------------ | ------------------------ |
| STOPPER·#4050报工视图 | `vew7Diocr5` | 上道批号_STOPPER#4050 | `fldlSVdUxR` | `recC9QvIgUH8oK` (#2030) |
| STOPPER·#60报工视图   | `vewgS0km1u` | 上道批号_STOPPER#60   | `fldyLk2vMC` | `recs76rS587WRW` (#4050) |
| STOPPER·#70报工视图   | `vewqlHptpP` | 上道批号_STOPPER#70   | `fldICbx5p7` | `recfoJ5q7gJVtK` (#60)   |
| 止动块·#60 报工视图      | `vewEMVET4u` | 上道批号_止动块#60       | `fldvjM58FP` | `recs76rS587WRW` (#4050) |
| 止动块·#70 报工视图      | `vewUWGnXfU` | 上道批号_止动块#70       | `flds7u3fTQ` | `recfoJ5q7gJVtK` (#60)   |
| 止动块·#80 报工视图      | `vewEJZrQu5` | 上道批号_止动块#80       | `fld8FPWbLM` | `recIZhFG8RKKMI` (#70)   |


**上道批号筛选（关联→生产日志主表 `tblXr4h68tqh2HDy`，满足所有条件）：**


| 条件     | 值                            |
| ------ | ---------------------------- |
| 工序下发状态 | **已确认**（选项之一，勿用有效合格>0）       |
| 工序代码   | 上道工序 record_id（见上表）          |
| 产品     | 止动块视图额外加：产品=`recvnmMdIn6lCo` |


**字段属性：**

- 上述 6 个上道字段 + 通用 `上道批号`(`fldDnQmyR6`)：**取消「允许多条」**（当前 `上道批号` multiple=true，需改为 false）
- **不要**添加「有效合格数量>0」

### 止动块重复视图（已 API 删除）

以下 3 个简写重复视图已于 2026-06-23 由 `advance_v4_greenfield.py` 删除，**仅保留带「报工视图」后缀的 4 个**：


| view_id      | 视图名       | 状态  |
| ------------ | --------- | --- |
| `vewRy47uJk` | 止动块·#60报工 | 已删除 |
| `vewsXMq522` | 止动块·#70报工 | 已删除 |
| `vewxR6vOrR` | 止动块·#80报工 | 已删除 |


---

## 二、产品表记录（`tblntK7K89dOpJVp`）


| record_id        | 产品代码    | 产品名称 | 筛选时显示         |
| ---------------- | ------- | ---- | ------------- |
| `rechKic8YG1cTc` | STOPPER | 小逗号  | STOPPER       |
| `recvnmMdIn6lCo` | ZHIDONG | 止动块  | 止动块 / ZHIDONG |
| `recvnngInM41nM` | PTJ92   | 三柱轴  | PTJ92         |


---

## 三、工序表记录（`tblxbzA1m4mS5rXf`）


| record_id        | 工序代码  | 用途                 |
| ---------------- | ----- | ------------------ |
| `recC9QvIgUH8oK` | #2030 | STOPPER 首道         |
| `recs76rS587WRW` | #4050 | STOPPER 二道 / 止动块首道 |
| `recfoJ5q7gJVtK` | #60   | 检查机                |
| `recIZhFG8RKKMI` | #70   | STOPPER 出库（筛选用这条）  |
| `recvnmMevC5Dbr` | #80   | 止动块出库              |
| `recy0wR8UdunUU` | #1020 | PTJ92（P2 后）        |
| `recST53o7KuXQy` | #3040 | PTJ92              |
| `recRxX5JjvzuEm` | #50   | PTJ92              |


> #70 有两条记录，筛选请用 `recIZhFG8RKKMI`（工序代码=#70）。

---

## 四、生产日志主表关键字段（`tblXr4h68tqh2HDy`）


| 字段名     | field_id     | 类型     | 说明                            |
| ------- | ------------ | ------ | ----------------------------- |
| 生产批号    | `fldvMRl868` | 公式     | 各视图设为只读                       |
| 生产批号_上道 | `fldncziHl9` | 公式     | 下道批号带出                        |
| 产品      | `fldSUoQi47` | 关联→产品表 |                               |
| 工序代码    | `fldMxRQhnU` | 关联→工序表 |                               |
| 工序下发状态  | `fld1PUlkCs` | 单选     | 待报工/已报工/待返工/待品保确认/**已确认**     |
| 生产区域    | `fld2QxxYLM` | 单选     | A1/A2/B1/B2/MG/J 等            |
| 关联管控批   | `fldxfgJtRE` | 关联→管控表 | 通用字段                          |
| 上道批号    | `fldDnQmyR6` | 关联→主表  | **当前 multiple=true，需改 false** |
| 有效合格数量  | `fldRKjpJSm` | 公式     | **不要用于筛选**                    |


---

## 五、入库批次管控表（`tbl6bCLJThyUaD8U`）

### 字段


| 字段名        | field_id     | 类型                   |
| ---------- | ------------ | -------------------- |
| 批号文本       | `fldXf5PH49` | 文本                   |
| 产品         | `fldEti7fPN` | 关联→产品表               |
| 工序代码       | `fldW6msrvH` | 关联→工序表               |
| 生产区域       | `fld4HLu08o` | 单选                   |
| 状态         | `fldjSaGns4` | 单选：未下发/ **已下发** /已结案 |
| 本工序下发数量    | `fld7m9m3bX` | 数字                   |
| 合格合计       | `fldoyp4fwS` | 查找引用→汇总表             |
| 合格合计_#4050 | `flda8dkzsT` | 查找引用→汇总表             |


### 现有测试数据


| record_id        | 批号           | 产品      | 工序    | 区域   | 状态  | 下发量  |
| ---------------- | ------------ | ------- | ----- | ---- | --- | ---- |
| `recvnnc64j5p56` | **S-TEST-A** | STOPPER | #2030 | (空)  | 已下发 | 1000 |
| `recPmOhBaEjuwp` | S-260617-A   | STOPPER | #2030 | (空)  | 已下发 | 1000 |
| `recCpIzEZaBU0t` | S-260618-A   | ZHIDONG | #4050 | MG02 | 已下发 | 500  |
| `recq6BpkPCqtJD` | S-260618-A   | ZHIDONG | #4050 | MG03 | 已下发 | 500  |


### 合格合计查找（4 条件，字段 `fldoyp4fwS`）

查找 **批工序产量汇总表** `tblu1h0huPW1Mixd` → 字段 **合格合计** `fldnEQpJuV`：


| #   | 管控表字段             | 汇总表字段             |
| --- | ----------------- | ----------------- |
| 1   | 批号文本 `fldXf5PH49` | 批号文本 `fldZQtO2sV` |
| 2   | 产品 `fldEti7fPN`   | 产品 `fldQbu1NEl`   |
| 3   | 工序代码 `fldW6msrvH` | 工序代码 `fldZYgkGrq` |
| 4   | 生产区域 `fld4HLu08o` | 生产区域 `fldCvBjksp` |


**注意：** #2030 管控行「生产区域」为空；汇总 #2030 行区域为 `A`（合并后）。若 S-TEST-A 合格合计仍为 0，#2030 行可将管控「生产区域」留空且汇总对账用区域 `A` 的行，或单独为 #2030 做不含区域的查找视图。**#4050 行必须有 MG 区域**（如 MG02）。

---

## 六、批工序产量汇总表（`tblu1h0huPW1Mixd`）现有数据


| 批号       | 产品      | 工序    | 生产区域 | 合格合计 |
| -------- | ------- | ----- | ---- | ---- |
| S-TEST-A | STOPPER | #2030 | A    | 150  |
| S-TEST-A | STOPPER | #4050 | MG02 | 80   |
| S-TEST-A | STOPPER | #4050 | MG04 | 20   |
| S-TEST-A | STOPPER | #60   | (空)  | 60   |


汇总由脚本 `feishu-batch-summary-sync/sync_batch_summary.py` 写入，勿用飞书公式聚合。

---

## 七、主表现有测试报工（选批验收用）


| 批号       | 产品      | 工序    | 状态  | 区域        |
| -------- | ------- | ----- | --- | --------- |
| S-TEST-A | STOPPER | #2030 | 已确认 | A1/A2     |
| S-TEST-A | STOPPER | #4050 | 已确认 | MG02/MG04 |
| S-TEST-A | STOPPER | #60   | 已确认 | J1        |


下道 #4050 上道应能筛到 #2030 已确认的 S-TEST-A 记录。

---

## 八、给飞书 AI 的执行 Prompt（含上下文）

---BEGIN---

**P1 已于 2026-06-23 完成验收，本节仅供归档参考。**

你已有完整上下文（app_token、表ID、视图ID、字段ID、产品/工序 record_id、测试批 S-TEST-A）。  
请在「机加工生产日志 v4」执行 P1 收尾，**不要新建应用**。

按 `docs/openclaw-p1-sprint-prompt-cn.md` 要求：

1. 对 8 个报工视图的上表「要配置的字段」设置关联筛选（用 record_id 点选，勿手打文本）
2. 上道批号字段取消允许多条
3. 生产批号公式只读
4. 管控表合格合计 4 条件查找（字段 ID 见上文第五节）
5. 止动块下道视图加产品=recvnmMdIn6lCo

**禁止：** 有效合格>0 作筛选；重建应用；汇总表公式聚合。

---END---

---

## 九、国宝手工兜底

若飞书 AI 仍无法改字段筛选，按视图打开 → 点列头字段名 → 编辑字段 → 关联记录筛选，对照本文 **第一节表格** 逐条手配。  
手册：`docs/feishu-p1-manual-setup-cn.md`

---

## 十、P1 验收记录（2026-06-23 ✅）


| 验证项                    | 结果          |
| ---------------------- | ----------- |
| 6 下道视图筛到 S-TEST-A      | ✅ 筛选配置生效    |
| 首道选 `recvnnc64j5p56`   | ✅ 管控批可选     |
| 管控 S-TEST-A #4050 合格合计 | ✅ 显示 **80** |


约束：未用有效合格>0 · 未重建应用 · 未汇总公式聚合 · record_id 点选。

**P1 已完成。** 联动四视图 ✅。**下一步：** cron → P2（`openclaw-p2-prompt-cn.md`）。