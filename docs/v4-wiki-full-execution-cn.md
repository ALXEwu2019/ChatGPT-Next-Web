# 机加工生产日志 V4 绿场 · 完整推进单（Wiki 主战场）

> **入口链接：** [机加工生产日志 V4](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)  
> **更新：** 2026-06-23 · P1 ✅ · 联动四视图 ✅ · verify_p1 **6/6** · verify_sprint **7/7**

---

## 1. 三个 Base 分工（勿混用）

| Base | app_token | 角色 | 策略 |
| --- | --- | --- | --- |
| **V4 绿场（主战场）** | `HiqNwQnxniKGEGketZBcEC9Sn3d`（wiki）≈ `CHNKbTKTCaWbQis1vVXcsLvsnDh` | 37 字段标准库 | **本推进单全部任务** |
| 旧生产 Base | `NiyZbKpKfae9x3sUP64cl9SFnRb` | ~81 字段旧库 | 已审计修正，见 `production-base-v4-audit-cn.md` |
| 2026 废弃 token | `P2MtbRCz1a0Pj8sUP64cl9SFnRb` | 已迁移 | **勿用** |

---

## 2. 当前自动验收状态

```bash
cd feishu-batch-summary-sync
python3 verify_p1.py          # 6/6 PASS
python3 verify_sprint.py        # 7/7 PASS
python3 advance_v4_greenfield.py --dry-run   # 预览变更
```

| 检查项 | 状态 |
| --- | --- |
| 主表 37 字段、已确认报工 | ✅（7 条） |
| 管控表 ≥4 行、S-TEST-A 首道 | ✅ |
| 汇总表 4 行（脚本写入） | ✅ |
| 产品工序路线 11 行 | ✅ |
| 不良原因库 46 行 | ✅ |
| 联动规则 137 行（启用 110 / 返工 23 / 报废 87） | ✅ |
| 产品追溯规则表 8 行 | ✅ **本次 API 补种** |
| 8 报工视图 hidden_fields 收敛 | ✅ **本次 API** |
| 3 个重复止动块简写视图 | ✅ **已删除** |
| 批工序汇总 sync | ✅ |
| **P1 界面：8 视图筛选 + 合格合计查找** | ✅ **2026-06-23 人工验收** |

### P1 人工验收记录

| 验证项 | 结果 |
| --- | --- |
| 6 下道视图筛到 S-TEST-A | ✅ |
| 首道选 `recvnnc64j5p56` | ✅ |
| 管控 S-TEST-A #4050 合格合计 | ✅ **80** |

---

## 3. 本次已执行（API / 脚本）

**脚本：** `feishu-batch-summary-sync/advance_v4_greenfield.py`

| 步骤 | 内容 |
| --- | --- |
| 1 | 产品追溯规则表 `tblWv5lus3TI8zM3` 写入 8 行（STOPPER / 止动块 × 各工序） |
| 2 | 8 个报工视图 `hidden_fields` 收敛（每视图仅显示本道选批 + 报工必填列） |
| 3 | 删除重复简写视图 `vewRy47uJk` / `vewsXMq522` / `vewxR6vOrR` |
| 4 | 运行 `sync_batch_summary.py` 刷新汇总 |

**配置模板：** `config.v4.wiki.example.json`（wiki token + 全表 ID）

---

## 4. 待完成（飞书界面 / 服务器）

### ~~4.1 P1 收尾~~ ✅ 已完成（2026-06-23）

8 视图关联筛选、上道批号单选、合格合计 4 条件查找、生产批号只读均已验收。详见 `p1-completion-checklist-cn.md`。

### ~~4.2 联动四视图~~ ✅ 已完成（2026-06-23）

**指南：** `feishu-defect-linkage-views-setup-cn.md`

| 视图 | 实际 | 预期 | 状态 |
| --- | ---: | ---: | --- |
| 启用·按产品工序 | 119 | 110 | ✅ 分组展示，底层 110 条启用 |
| 返工原因 | 23 | 23 | ✅ |
| 报废原因 | 87 | 87 | ✅ |
| 历史·止动块#2030 | 27 | 27 | ✅ 全部停用，仅档案 |

137 条数据未修改。详见 `feishu-defect-linkage-views-setup-cn.md` 第八节。

### 4.3 cron 部署（当前优先，你的服务器）

云 Agent **无 crontab**，需在本机/服务器：

```bash
cd feishu-batch-summary-sync
cp config.v4.wiki.example.json config.json   # 填入凭证
chmod +x run_sync.sh
crontab -e   # 粘贴 cron.example 三行（8/12/20 点）
```

详见 `p1-cron-setup-cn.md`。

### 4.4 P2 不良闭环（P1 通过后）

**Prompt：** `openclaw-p2-prompt-cn.md` · **公式：** `feishu-p2-formula-fix-cn.md`

| # | 内容 |
| --- | --- |
| 1 | 不良明细：处置类型、状态机 |
| 2 | 主表：有不良→待返工→待品保确认→已确认 |
| 3 | 有效合格/有效报废公式（有不良分支） |
| 4 | 视图：品保·不良填报、班组长·待返工、品保·待确认 |
| 5 | 端到端测试 1 条有不良报工 |

### 4.5 后续（P2 后）

| 项 | 说明 |
| --- | --- |
| STOPPER #70、止动块 #70/#80 报工视图 | 末道启用 |
| #4050 对账视图（MG 汇总 vs 下发） | P1 合格合计完成后 |
| PTJ92 全链 | 单开阶段 |
| 旧生产 Base 向绿场迁移 | 长期，非本单范围 |

---

## 5. 关键 ID 速查

| 项 | 值 |
| --- | --- |
| wiki app_token | `HiqNwQnxniKGEGketZBcEC9Sn3d` |
| 生产日志主表 | `tblXr4h68tqh2HDy` |
| 默认表格视图 | `vewT0WgVD1` |
| 入库批次管控 | `tbl6bCLJThyUaD8U` |
| 批工序产量汇总 | `tblu1h0huPW1Mixd` |
| 产品追溯规则 | `tblWv5lus3TI8zM3` |
| STOPPER 产品 | `rechKic8YG1cTc` |
| 止动块产品 | `recvnmMdIn6lCo` |
| 测试批 S-TEST-A 管控 | `recvnnc64j5p56` |

8 个报工视图 ID、字段 ID、筛选条件见 **`openclaw-p1-context-supplement-cn.md`**。

---

## 6. 文档索引

| 用途 | 文件 |
| --- | --- |
| v4 总方案 | `machining-production-log-v4-greenfield-cn.md` |
| **本推进单** | `v4-wiki-full-execution-cn.md` |
| 阶段推进（简版） | `v4-execution-sprint-cn.md` |
| P1 上下文包 | `openclaw-p1-context-supplement-cn.md` |
| P1 一键 Prompt | `openclaw-p1-sprint-prompt-cn.md` |
| 旧库审计 | `production-base-v4-audit-cn.md` |
| 汇总脚本 | `feishu-batch-summary-sync/sync_batch_summary.py` |
| V4 推进脚本 | `feishu-batch-summary-sync/advance_v4_greenfield.py` |

---

## 7. 给飞书 AI 的一句话

在 [机加工生产日志 V4](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1) 执行 P1 收尾：将 `openclaw-p1-context-supplement-cn.md` 全文 + `openclaw-p1-sprint-prompt-cn.md` 一并粘贴，配置 8 视图关联筛选与合格合计查找，勿重建应用、勿用有效合格>0 筛选。
