# 工位二维码与表单字段对照表

> **用途：** 贴车间工位、配置飞书「表单视图」时逐格对照。  
> **应用：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d)  
> **前置：** 已执行 `python3 setup_role_entrypoints.py`（操作工表格视图列已收敛）

---

## 一、配置步骤（每个工位做一次）

1. 打开下表 **源表格视图** 链接（不要直接用默认表格）。
2. 右上角 **… → 复制视图 → 表单视图**。
3. 表单命名建议：`扫码-{产品}-{工序}`（与下表「建议二维码标题」一致）。
4. 在表单设计器中 **只保留下表「表单字段顺序」列中的字段**，其余删除或隐藏。
5. 将字段 **按表中顺序从上到下拖拽**（即员工填写顺序）。
6. 设必填：带 ★ 的字段在表单里勾「必填」。
7. **分享表单 → 生成二维码**，打印贴工位。

**不要放进操作工表单：** 工序下发状态、有效合格/报废、返工后合格/报废、批号文本、完整追溯号、是否有不良、管控批状态/产品/工序、日志编号（系统自动）。

**产品 / 工序代码：** 若表单新建行时为空，可在视图筛选里固定产品+工序，或表单默认值里写死（推荐视图已按工序拆分，员工一般无需手选）。

---

## 二、操作工：12 个工位对照表


| #   | 建议二维码标题         | 产品      | 工序         | 源表格视图                                                                                                                       | view_id      |
| --- | --------------- | ------- | ---------- | --------------------------------------------------------------------------------------------------------------------------- | ------------ |
| 1   | 扫码-STOPPER-2030 | STOPPER | #2030 车床首道 | [STOPPER·#2030报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewfbrQvsu) | `vewfbrQvsu` |
| 2   | 扫码-STOPPER-4050 | STOPPER | #4050 磨床   | [STOPPER·#4050报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew7Diocr5) | `vew7Diocr5` |
| 3   | 扫码-STOPPER-60   | STOPPER | #60 加工中心   | [STOPPER·#60报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewgS0km1u)   | `vewgS0km1u` |
| 4   | 扫码-STOPPER-70   | STOPPER | #70 检测末道   | [STOPPER·#70报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewqlHptpP)   | `vewqlHptpP` |
| 5   | 扫码-止动块-2030     | 止动块     | #2030 车床首道 | [止动块·#2030报工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewBbCamcQ)       | `vewBbCamcQ` |
| 6   | 扫码-止动块-4050     | 止动块     | #4050 磨床   | [止动块·#4050报工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew4kJ8hxX)       | `vew4kJ8hxX` |
| 7   | 扫码-止动块-60       | 止动块     | #60 加工中心   | [止动块·#60 报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewEMVET4u)      | `vewEMVET4u` |
| 8   | 扫码-止动块-70       | 止动块     | #70 检测     | [止动块·#70 报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewUWGnXfU)      | `vewUWGnXfU` |
| 9   | 扫码-止动块-80       | 止动块     | #80 末道     | [止动块·#80 报工视图](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewEJZrQu5)      | `vewEJZrQu5` |
| 10  | 扫码-PTJ92-1020   | PTJ92   | #1020 首道   | [PTJ92·#1020报工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew2SeSRgG)     | `vew2SeSRgG` |
| 11  | 扫码-PTJ92-3040   | PTJ92   | #3040      | [PTJ92·#3040报工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewDNLBqX5)     | `vewDNLBqX5` |
| 12  | 扫码-PTJ92-50     | PTJ92   | #50 末道     | [PTJ92·#50报工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewhTfcmic)       | `vewhTfcmic` |


---

## 三、逐工位：表单字段顺序与必填

说明：**选批字段** = 员工第一个要点的关联字段；选完后 **生产批号** 应自动带出（只读展示，供核对）。

### STOPPER


| 工位    | 选批字段 ★                   | 表单字段顺序（上→下）                                                                     | 区域/工位取值              |
| ----- | ------------------------ | ------------------------------------------------------------------------------- | -------------------- |
| #2030 | **关联管控批_STOPPER#2030** ★ | ① 关联管控批_STOPPER#2030 → ② 生产批号 → ③ **生产区域** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次 | `A1` `A2` `B1` `B2`  |
| #4050 | **上道批号_STOPPER#4050** ★  | ① 上道批号_STOPPER#4050 → ② 生产批号 → ③ **生产区域** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次  | `MG02` `MG03` `MG04` |
| #60   | **上道批号_STOPPER#60** ★    | ① 上道批号_STOPPER#60 → ② 生产批号 → ③ **工位代码** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次    | `J1` `J2`（追溯用）       |
| #70   | **上道批号_STOPPER#70** ★    | ① 上道批号_STOPPER#70 → ② 生产批号 → ③ 合格数量 ★ → ④ 报废数量 → ⑤ 操作工 → ⑥ 班次                   | 无                    |


### 止动块


| 工位    | 选批字段 ★               | 表单字段顺序（上→下）                                                                 | 区域/工位取值              |
| ----- | -------------------- | --------------------------------------------------------------------------- | -------------------- |
| #2030 | **关联管控批_止动块#2030** ★ | ① 关联管控批_止动块#2030 → ② 生产批号 → ③ **生产区域** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次 | `A1` `A2` `B1` `B2`  |
| #4050 | **上道批号_止动块#4050** ★  | ① 上道批号_止动块#4050 → ② 生产批号 → ③ **生产区域** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次  | `MG02` `MG03` `MG04` |
| #60   | **上道批号_止动块#60** ★    | ① 上道批号_止动块#60 → ② 生产批号 → ③ **工位代码** ★ → ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次    | `J1` `J2`            |
| #70   | **上道批号_止动块#70** ★    | ① 上道批号_止动块#70 → ② 生产批号 → ③ 合格数量 ★ → ④ 报废数量 → ⑤ 操作工 → ⑥ 班次                   | 无                    |
| #80   | **上道批号_止动块#80** ★    | ① 上道批号_止动块#80 → ② 生产批号 → ③ 合格数量 ★ → ④ 报废数量 → ⑤ 操作工 → ⑥ 班次                   | 无                    |


### PTJ92


| 工位    | 选批字段 ★                | 表单字段顺序（上→下）                                                          | 区域/工位取值      |
| ----- | --------------------- | -------------------------------------------------------------------- | ------------ |
| #1020 | **关联管控批** ★           | ① 关联管控批 → ② 生产批号 → ③ **工位代码**（建议填）→ ④ 合格数量 ★ → ⑤ 报废数量 → ⑥ 操作工 → ⑦ 班次 | 工位如 `J1`（追溯） |
| #3040 | **上道批号_PTJ92#3040** ★ | ① 上道批号_PTJ92#3040 → ② 生产批号 → ③ 合格数量 ★ → ④ 报废数量 → ⑤ 操作工 → ⑥ 班次        | 无            |
| #50   | **上道批号_PTJ92#50** ★   | ① 上道批号_PTJ92#50 → ② 生产批号 → ③ 合格数量 ★ → ④ 报废数量 → ⑤ 操作工 → ⑥ 班次          | 无            |


**报废数量：** 无报废时可填 `0` 或留空（按你们表单默认值习惯）。

---

## 四、选批规则速查（配置关联筛选时已做则员工无感）


| 类型  | 员工选的字段  | 下拉里应只有                       |
| --- | ------- | ---------------------------- |
| 首道  | 关联管控批_* | 入库批次管控 · **已下发** · 本产品 · 本工序 |
| 下道  | 上道批号_*  | 生产日志 · **已确认** · 上道工序 · 本产品  |


若下拉为空：检查上道是否 **已确认**，或计划员是否已 **下发** 管控批。

---

## 五、班组长 / 品保（非工位扫码，建议手机收藏）

不适合贴工位二维码，建议 **飞书收藏** 或 **工作台快捷方式**（各 1 个即可，全产线共用）。

### 班组长（2 个入口）


| 顺序  | 收藏名称     | 链接                                                                                                                 | 表单/操作字段                                  |
| --- | -------- | ------------------------------------------------------------------------------------------------------------------ | ---------------------------------------- |
| 1   | 班组长-看待返工 | [班组长·待返工](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewy8lBInU)  | 只读核对：关联生产记录、不良数量、不良原因、处置类型               |
| 2   | 班组长-返工回填 | [班组长·返工回填表单](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewzCBs9ta) | 编辑：**返工后合格数** ★、**返工后报废数** ★（行状态应为「待返工」） |


### 品保（2 个入口）


| 顺序  | 收藏名称   | 链接                                                                                                                | 表单/操作字段                                                 |
| --- | ------ | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 1   | 品保-记不良 | [品保·不良录入表单](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewhGXZnqB) | 新建：**关联生产记录** ★、**不良数量** ★、**不良原因** ★、**处置类型** ★（返工/报废） |
| 2   | 品保-待确认 | [品保·待确认](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewECvrwqs)  | 将 **工序下发状态** 改为 **已确认**（行状态应为「待品保确认」）                   |


**品保记不良 · 处置类型：**


| 处置类型 | 后续                    |
| ---- | --------------------- |
| 返工   | 班组长回填返工后合格/报废 → 品保待确认 |
| 报废   | 同上（报废数进入返工后报废）        |


---

## 六、产线贴码清单（打印勾选）

```
操作工（12 张）
□ 扫码-STOPPER-2030    □ 扫码-STOPPER-4050    □ 扫码-STOPPER-60     □ 扫码-STOPPER-70
□ 扫码-止动块-2030     □ 扫码-止动块-4050     □ 扫码-止动块-60       □ 扫码-止动块-70      □ 扫码-止动块-80
□ 扫码-PTJ92-1020      □ 扫码-PTJ92-3040      □ 扫码-PTJ92-50

班组长 / 品保（收藏链接，不贴码）
□ 班组长-看待返工  □ 班组长-返工回填  □ 品保-记不良  □ 品保-待确认
```

---

## 七、相关文档

- 角色流程说明：`docs/production-role-entrypoints-cn.md`
- 视图关联筛选手工配置：`docs/feishu-p1-manual-setup-cn.md`、`docs/openclaw-p1-context-supplement-cn.md`

---

*工位二维码对照表 v2 · 2026-06-24（12 工序 / 产品×工序代码）*