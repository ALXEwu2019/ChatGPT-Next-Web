# V4 可选扩展 · 推进单（P3）

> **入口：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)  
> **脚本：** `feishu-batch-summary-sync/advance_v4_extensions.py`

---

## 1. 三项扩展总览

| 扩展 | API/脚本 | 飞书界面 | 状态 |
| --- | --- | --- | --- |
| 末道 #70/#80 | 测试数据 + 链路修复 + sync | P1 筛选已配 | ✅ API 完成 |
| #4050 对账 | 列收敛 + 字段验收 | 视图/公式已存在 | ✅ |
| PTJ92 全链 | 字段+视图+追溯+管控批 | **3 视图关联筛选** | ⏳ Prompt 待执行 |

---

## 2. 一键执行（API）

```bash
cd feishu-batch-summary-sync
python3 advance_v4_extensions.py --dry-run
python3 advance_v4_extensions.py
python3 verify_extensions.py
```

分项执行：

```bash
python3 advance_v4_extensions.py --only end
python3 advance_v4_extensions.py --only reconcile
python3 advance_v4_extensions.py --only ptj92
```

---

## 3. 末道 #70/#80

### 已有（P1）

| 视图 | view_id | 上道工序 |
| --- | --- | --- |
| STOPPER·#70报工视图 | `vewqlHptpP` | #60 `recfoJ5q7gJVtK` |
| 止动块·#70 报工视图 | `vewUWGnXfU` | #60 |
| 止动块·#80 报工视图 | `vewEJZrQu5` | #70 `recIZhFG8RKKMI` |

### 脚本补充

- 写入 **STOPPER #70** 测试报工（接上道 `recvnmEzmWn7PY` #60 行）
- 跑 `sync_batch_summary.py` → 汇总表出现 `S-TEST-A-#70`

### 验收

- [ ] STOPPER·#70 视图能筛到 S-TEST-A 上道 #60
- [ ] 新建 #70 报工并已确认后，汇总表有对应行

---

## 4. #4050 对账视图

### 已有

| 项 | ID / 说明 |
| --- | --- |
| 视图 | `管理·批工序对账` `vewEEYWvZN`（管控表） |
| 合格合计 | `fldoyp4fwS` 四条件查找 |
| 对账差异 | `fldGwYItxM` 公式 |
| 是否超产 | `fldAYpgVFB` 公式 |

### 规则（A3 默认）

按 **MG 区分行** 对账：管控 MG02 行 vs 汇总 `S-xxx-#4050-MG02`。

### 脚本补充

- 对账视图列收敛（批号、产品、工序、区域、下发量、合格合计、差异、超产）

### 验收

- [ ] S-TEST-A #4050 MG02 行：合格合计=80，下发量=1000 → 未超产
- [ ] 止动块 S-260618-A 双 MG 行均无超产

---

## 5. PTJ92 全链

### 路线表（已有 3 行）

| 顺序 | 工序 | 首道 | 上道 | 批号来源 |
| --- | --- | --- | --- | --- |
| 1 | #1020 | ✓ | — | 入库批次管控 |
| 2 | #3040 | | #1020 | 上道批号池 |
| 3 | #50 | | #3040 | 上道批号池 |

| 视图 | view_id |
| --- | --- |
| PTJ92·#1020报工 | `vew2SeSRgG` |
| PTJ92·#3040报工 | `vewDNLBqX5` |
| PTJ92·#50报工 | `vewhTfcmic` |

### 脚本已创建

| 项 | 内容 |
| --- | --- |
| 主表字段 | `关联管控批_PTJ92#1020`、`上道批号_PTJ92#3040`、`上道批号_PTJ92#50` |
| 追溯规则 | +3 行（共 11 行） |
| 管控测试批 | `P-TEST-A` #1020 已下发 300 |

### 关键 ID

| 实体 | record_id |
| --- | --- |
| PTJ92 产品 | `recvnngInM41nM` |
| #1020 | `recy0wR8UdunUU` |
| #3040 | `recST53o7KuXQy` |
| #50 | `recRxX5JjvzuEm` |

### 手工（飞书 AI）

将 `docs/openclaw-p3-ptj92-prompt-cn.md` 全文粘贴给飞书 AI，配置 **3 个 PTJ92 视图关联筛选**。

### 验收

- [ ] 首道 #1020 能选 P-TEST-A 管控批
- [ ] #3040 能筛到 #1020 已确认批
- [ ] #50 能筛到 #3040 已确认批
- [ ] `verify_extensions.py` 全部 PASS

---

## 6. 配置更新

`config.v4.wiki.example.json` 已增加 `#1020` / `#3040` / `#50` 汇总聚合（仅批号+产品+工序）。

---

## 7. 文档索引

| 文件 | 用途 |
| --- | --- |
| `advance_v4_extensions.py` | 扩展一键脚本 |
| `verify_extensions.py` | 扩展验收 |
| `openclaw-p3-ptj92-prompt-cn.md` | PTJ92 视图筛选 Prompt |
| `openclaw-route-table-migration-prompt-cn.md` | 路线表参考 |
| `feishu-lookup-qualified-total-cn.md` | 对账查找说明 |

---

*P3 扩展推进单 v1*
