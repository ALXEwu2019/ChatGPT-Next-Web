# 三产品产线角色入口手册

> **应用：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d)  
> **适用：** STOPPER、止动块、PTJ92 三产品同时在跑，含返工与报废（P2 质量闭环）

---

## 一、角色与入口总览

| 角色 | 做什么 | 打开哪个视图 |
| --- | --- | --- |
| **操作工** | 扫码/填单：选批、填合格/报废、选区域或工位 | 各产品 **#工序 报工** 视图（共 11 个） |
| **品保** | ① 记不良 ② 返工完成后最终确认 | **品保·不良填报** → **品保·待确认** |
| **班组长** | 查看待返工明细；在主表回填返工后合格/报废 | **班组长·待返工** → **班组长·返工回填** |

### 状态机（有返工/报废时）

```
操作工保存（已报工）
    ↓ 品保在「不良填报」关联本行并保存
主表 → 待返工
    ↓ 班组长在「返工回填」填写返工后合格数/报废数
主表 → 待品保确认
    ↓ 品保在「待确认」改为已确认
主表 → 已确认（有效数生效，可汇总、可作下道上道批）
```

**无不良时：** 保存后自动化直接 **已确认**（有效合格=合格数量，有效报废=报废数量）。

---

## 二、操作工入口（11 个报工视图）

每个视图只显示本工序要填的列：**选批 → 生产批号（只读）→ 区域/工位 → 合格/报废 → 操作工/班次**。

### STOPPER

| 工序 | 视图 | 链接 |
| --- | --- | --- |
| #2030 首道 | STOPPER·#2030报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewfbrQvsu) |
| #4050 | STOPPER·#4050报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew7Diocr5) |
| #60 | STOPPER·#60报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewgS0km1u) |
| #70 末道 | STOPPER·#70报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewqlHptpP) |

- 首道选 **关联管控批_STOPPER#2030**（仅「已下发」批号）
- 下道选 **上道批号_STOPPER#***（上道 **已确认**）
- #2030/#4050 必填 **生产区域**；#60 必填 **工位代码**

### 止动块

| 工序 | 视图 | 链接 |
| --- | --- | --- |
| #4050 首道 | 止动块·#4050报工 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew4kJ8hxX) |
| #60 | 止动块·#60 报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewEMVET4u) |
| #70 | 止动块·#70 报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewUWGnXfU) |
| #80 末道 | 止动块·#80 报工视图 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewEJZrQu5) |

- 首道选 **关联管控批_止动块#4050**
- 下道选 **上道批号_止动块#***

### PTJ92

| 工序 | 视图 | 链接 |
| --- | --- | --- |
| #1020 首道 | PTJ92·#1020报工 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vew2SeSRgG) |
| #3040 | PTJ92·#3040报工 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewDNLBqX5) |
| #50 末道 | PTJ92·#50报工 | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewhTfcmic) |

- 首道选 **关联管控批**（通用字段）
- 下道选 **上道批号_PTJ92#3040** / **上道批号_PTJ92#50**
- #1020 建议填 **工位代码**（追溯用）

### 扫码填单（推荐）

1. 在飞书中打开上表对应 **报工视图**
2. 右上角 **… → 复制视图 → 表单视图**
3. 表单设计器里只保留：选批、生产批号、区域/工位、合格数量、报废数量、操作工、班次
4. **分享表单 → 生成二维码**，贴到工位

---

## 三、品保入口

| 步骤 | 视图 | 链接 | 操作 |
| --- | --- | --- | --- |
| 1 记不良 | 品保·不良填报（不良明细表） | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewGh4QxtW) | 新建行：**关联生产记录** 选报工行；填不良数量、不良原因、处置类型（返工/报废） |
| 2 最终确认 | 品保·待确认（主表，已筛「待品保确认」） | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewECvrwqs) | 核对返工后数量，将 **工序下发状态** 改为 **已确认** |

---

## 四、班组长入口

| 步骤 | 视图 | 链接 | 操作 |
| --- | --- | --- | --- |
| 1 看待返工 | 班组长·待返工（不良明细表） | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblMtQ4aEwlzuhWs&view=vewy8lBInU) | 查看待返工不良行（只读核对） |
| 2 回填返工数 | 班组长·返工回填（主表，已筛「待返工」） | [打开](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewQhe4OjQ) | 填 **返工后合格数**、**返工后报废数**；保存后状态应变 **待品保确认**（依赖飞书自动化） |

---

## 五、API 一键配置与验收

```bash
cd feishu-batch-summary-sync

# 1. 收敛三角色视图列 + 班组长/品保筛选
python3 setup_role_entrypoints.py

# 2. 批号/有效数公式（含首道 per-view 管控批）
python3 remediate_v4_formulas.py

# 3. 灌入三产品测试批 + 跑通返工/报废链（S/Z/P-WF-E2E）
python3 seed_workflow_e2e.py

# 4. 字段与汇总验收
python3 verify_p2.py
python3 sync_batch_summary.py --dry-run -v
```

**E2E 测试批号：** `S-WF-E2E`（STOPPER 有不良返工）、`Z-WF-E2E`（止动块无不良）、`P-WF-E2E`（PTJ92 有不良返工）。

---

## 六、默认表格视图是干什么的？

**默认表格**（`vewT0WgVD1`）给计划/管理员看全字段，**不要**作为员工入口。

其他视图是把同一张主表按角色拆开：操作工只见 11 道报工列，班组长只见返工列，品保只见确认列。  
**上道池**（PTJ92·上道池#1020/#3040）仅供核对可接上道的批，不在此填单。

**工位贴码对照表（11 工位表单字段顺序 + 打印清单）：** [`production-workstation-qr-mapping-cn.md`](production-workstation-qr-mapping-cn.md)

---

*角色入口手册 v1 · 2026-06-24*
