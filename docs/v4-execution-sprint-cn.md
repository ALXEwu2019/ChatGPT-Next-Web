# 机加工生产日志 v4 · 执行推进单

> **当前阶段：** P1 收尾 → 质量视图 → P2 启动  
> **更新：** 自动验收 6/6 PASS · 路线表 11 行 · 联动规则 137 行 · 汇总脚本 dry-run 通过

---

## 进度总览

| 阶段 | 自动/脚本 | 飞书界面（你/飞书AI） |
| --- | --- | --- |
| P0 建库+脚本 | ✅ 完成 | ✅ 完成 |
| P1 选批+对账 | ✅ verify_p1 PASS | ⏳ **6+2 视图筛选、合格合计** |
| 质量配置 | ✅ 原因库+联动137行 | ⏳ **4 个联动视图** |
| cron | ⏳ 云环境无 crontab | ⏳ **你的服务器部署** |
| P2 不良闭环 | ✅ 明细表+处置类型字段 | ⏳ 状态机+公式+测试 |
| **2026 Base 优化** | ✅ 审计+方案+verify_2026 | ⏳ **飞书 AI 按阶段 A–G 执行** |

---

## 2026 Base 优化（并行推进）

**生产 Base：** `P2MtbRCz1a0Pj8sAOtocrHb6ntf`（用户日常链接）  
**文档：** `docs/machining-production-log-2026-optimization-cn.md`  
**飞书 AI：** `docs/openclaw-2026-optimization-prompt-cn.md` + `docs/openclaw-2026-context-supplement-cn.md`

```bash
cd feishu-batch-summary-sync
cp config.2026.example.json config.2026.json   # 填入凭证
python3 verify_2026.py
python3 sync_batch_summary.py --config config.2026.json --dry-run -v
```

---

## 第一步：P1 飞书界面（今天，约 30 分钟）

**操作手册：** `docs/feishu-p1-manual-setup-cn.md`  
**一键 Prompt：** `docs/openclaw-p1-sprint-prompt-cn.md`（复制给飞书 AI）

| # | 任务 | 验收 |
| --- | --- | --- |
| 1 | 6 个下道视图上道批号筛选 | 能选出上道已确认批 |
| 2 | 取消上道批号「允许多条」 | 单选 |
| 3 | 止动块视图加产品=止动块 | 不串 STOPPER |
| 4 | 2 个首道视图管控批筛选（已下发） | 首道能选 S-TEST-A |
| 5 | 管控表合格合计 4 条件查找 | 对账非 0 |
| 6 | 生产批号各视图只读 | 不可手改 |

**注意：** 上道筛选 **不要** 用「有效合格>0」（公式字段会导致保存失败）。用：

- 工序下发状态 = 已确认  
- 工序代码 = 上道工序（点选工序表）  
- （止动块视图）产品 = 止动块  

完成后运行：

```bash
cd feishu-batch-summary-sync
python3 verify_p1.py
python3 sync_batch_summary.py --dry-run -v
```

---

## 第二步：联动规则四视图（10 分钟）

**指南：** `docs/feishu-defect-linkage-views-setup-cn.md`

| 视图 | 筛选 | 预期行数 |
| --- | --- | --- |
| 启用·按产品工序 | 启用状态=启用 | 110 |
| 返工原因 | 启用 + 不良类型=返工 | 23 |
| 报废原因 | 启用 + 不良类型=报废 | 87 |
| 历史·止动块#2030 | 止动块 + #2030 | 27 |

---

## 第三步：cron 部署（你的服务器）

云 Agent 环境 **无 crontab**，需在你本机/服务器执行：

```bash
cd feishu-batch-summary-sync
chmod +x run_sync.sh
crontab -e
# 粘贴 cron.example 三行，路径改为实际目录
```

详见 `docs/p1-cron-setup-cn.md`。

---

## 第四步：P2 不良闭环（P1 通过后）

**Prompt：** `docs/openclaw-p2-prompt-cn.md`  
**公式修复：** `docs/feishu-p2-formula-fix-cn.md`

| # | 内容 |
| --- | --- |
| 1 | 不良明细表：处置类型、状态机字段（处置类型已 API 补列） |
| 2 | 主表：有不良→待返工→待品保确认→已确认 |
| 3 | 有效合格/有效报废公式（有不良分支） |
| 4 | 视图：品保·不良填报、班组长·待返工、品保·待确认 |
| 5 | 测试：1 条有不良报工 → 返工 → 确认 → 汇总只读已确认 |

---

## 第五步：末道 + 对账 + PTJ92（后续）

| 项 | 说明 |
| --- | --- |
| STOPPER #70、止动块 #70/#80 报工视图 | P2 后 |
| #4050 对账视图（MG 汇总 vs 下发） | P1 合格合计完成后 |
| PTJ92 全链启用 | P2 完成后单开 |
| 主表多套专用字段清理 | 可选，统一分视图筛选 |

---

## 自动验收命令

```bash
cd feishu-batch-summary-sync
python3 verify_p1.py          # P1 六项
python3 verify_sprint.py      # 路线/联动/明细表
python3 import_defect_linkage.py --dry-run
```

---

## 文档索引

| 用途 | 文件 |
| --- | --- |
| 总方案 | `machining-production-log-v4-greenfield-cn.md` |
| P1 清单 | `p1-completion-checklist-cn.md` |
| P1 手工 | `feishu-p1-manual-setup-cn.md` |
| P1 一键 | `openclaw-p1-sprint-prompt-cn.md` |
| 联动视图 | `feishu-defect-linkage-views-setup-cn.md` |
| P2 | `openclaw-p2-prompt-cn.md` |
