# V4 可选扩展 · 推进单（P3）

> **状态：✅ P3 已全部完成**（2026-06-24 PTJ92 筛选验收 + `verify_extensions` 8/8 PASS）  
> **入口：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)

---

## 1. 三项扩展总览

| 扩展 | API/脚本 | 飞书界面 | 状态 |
| --- | --- | --- | --- |
| 末道 #70/#80 | 测试数据 + 链路 + sync | P1 筛选已配 | ✅ |
| #4050 对账 | 列收敛 + 字段验收 | 视图/公式已存在 | ✅ |
| PTJ92 全链 | 字段+视图+追溯+管控批 | 3 视图关联筛选 | ✅ **2026-06-24** |

**约束遵守：** 未用有效合格>0 · 未改汇总表 · 未新建应用 · 关联字段单选 · 生产批号只读。

---

## 2. PTJ92 人工验收（2026-06-24）

| 验证项 | 结果 |
| --- | --- |
| 首道选中 P-TEST-A 管控批 | ✅ #1020 视图关联管控批可选 |
| #3040 下道筛选 | ✅ 可检索 PTJ92·#1020·已确认记录 |
| #50 下道筛选 | ✅ 可检索 PTJ92·#3040·已确认记录 |
| 三视图名称 | ✅ PTJ92·#1020/#3040/#50 报工 |

---

## 3. 自动验收

```bash
cd feishu-batch-summary-sync
python3 verify_extensions.py   # 8/8 PASS
```

---

## 4. 末道 #70/#80

| 视图 | view_id |
| --- | --- |
| STOPPER·#70报工视图 | `vewqlHptpP` |
| 止动块·#70 报工视图 | `vewUWGnXfU` |
| 止动块·#80 报工视图 | `vewEJZrQu5` |

- ✅ STOPPER #70 测试报工 + 汇总 `S-TEST-A-#70` 合格 55
- 止动块 #70/#80：视图与 P1 筛选已就绪，待产线实报数据

---

## 5. #4050 对账

| 项 | ID |
| --- | --- |
| 视图 | `vewEEYWvZN` 管理·批工序对账 |
| 对账差异 / 是否超产 | `fldGwYItxM` / `fldAYpgVFB` |

按 MG 分行对账（A3 默认）。

---

## 6. PTJ92 全链

| 视图 | view_id |
| --- | --- |
| PTJ92·#1020报工 | `vew2SeSRgG` |
| PTJ92·#3040报工 | `vewDNLBqX5` |
| PTJ92·#50报工 | `vewhTfcmic` |

| 实体 | record_id |
| --- | --- |
| PTJ92 | `recvnngInM41nM` |
| #1020 / #3040 / #50 | `recy0wR8UdunUU` / `recST53o7KuXQy` / `recRxX5JjvzuEm` |
| 测试管控批 | `P-TEST-A` #1020 已下发 |

---

## 7. V4 绿场总进度

| 阶段 | 状态 |
| --- | --- |
| P0 / P1 / 联动 / P2 / **P3** | ✅ |
| cron 定时汇总 | ⏳ 国宝（`guobao-cron-deploy-cn.md`） |

---

## 8. 文档索引

| 文件 | 用途 |
| --- | --- |
| `advance_v4_extensions.py` | 扩展 API 脚本 |
| `verify_extensions.py` | 扩展验收 |
| `openclaw-p3-ptj92-prompt-cn.md` | PTJ92 Prompt（已归档） |

---

*P3 扩展推进单 v2 · 已完成*
