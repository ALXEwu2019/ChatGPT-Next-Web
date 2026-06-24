# 机加工生产日志 v4 · 执行推进单

> **主战场：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)  
> **完整推进单：** `docs/v4-wiki-full-execution-cn.md`  
> **更新：** verify_p1 6/6 · verify_sprint 7/7 · advance_v4_greenfield 已执行

---

## 进度总览

| 阶段 | 自动/脚本 | 飞书界面（你/飞书AI） |
| --- | --- | --- |
| P0 建库+脚本 | ✅ 完成 | ✅ 完成 |
| P1 选批+对账 | ✅ verify_p1 PASS · 追溯规则 8 行 · 视图列收敛 | ⏳ **8 视图关联筛选、合格合计查找** |
| 质量配置 | ✅ 原因库+联动137行 | ⏳ **4 个联动视图** |
| cron | ⏳ 云环境无 crontab | ⏳ **你的服务器部署** |
| P2 不良闭环 | ✅ 明细表+处置类型字段 | ⏳ 状态机+公式+测试 |
| 旧生产 Base | ✅ 审计+remediate | 独立维护，见 `production-base-v4-audit-cn.md` |

---

## V4 绿场 Wiki（当前主战场）

**app_token：** `HiqNwQnxniKGEGketZBcEC9Sn3d`  
**配置模板：** `feishu-batch-summary-sync/config.v4.wiki.example.json`

```bash
cd feishu-batch-summary-sync
cp config.v4.wiki.example.json config.json   # 填入凭证
python3 advance_v4_greenfield.py --dry-run   # 追溯规则/视图列/删重复视图
python3 verify_p1.py
python3 verify_sprint.py
python3 sync_batch_summary.py --dry-run -v
```

**本次已执行：** 8 行追溯规则 · 8 报工视图 hidden_fields · 删 3 重复视图 · sync 汇总

---

## 第一步：P1 飞书界面（今天，约 30 分钟）

**操作手册：** `docs/feishu-p1-manual-setup-cn.md`  
**上下文包：** `docs/openclaw-p1-context-supplement-cn.md`  
**一键 Prompt：** `docs/openclaw-p1-sprint-prompt-cn.md`

| # | 任务 | 验收 |
| --- | --- | --- |
| 1 | 6 个下道视图上道批号筛选 | 能选出上道已确认批 |
| 2 | 取消上道批号「允许多条」 | 单选 |
| 3 | 止动块视图加产品=止动块 | 不串 STOPPER |
| 4 | 2 个首道视图管控批筛选（已下发） | 首道能选 S-TEST-A |
| 5 | 管控表合格合计 4 条件查找 | 对账非 0 |
| 6 | 生产批号各视图只读 | 不可手改 |

**注意：** 上道筛选 **不要** 用「有效合格>0」。用工序下发状态=已确认 + 工序代码 + 产品。

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

```bash
cd feishu-batch-summary-sync
chmod +x run_sync.sh
crontab -e   # 粘贴 cron.example 三行
```

详见 `docs/p1-cron-setup-cn.md`。

---

## 第四步：P2 不良闭环（P1 通过后）

**Prompt：** `docs/openclaw-p2-prompt-cn.md`  
**公式修复：** `docs/feishu-p2-formula-fix-cn.md`

---

## 自动验收命令

```bash
cd feishu-batch-summary-sync
python3 verify_p1.py
python3 verify_sprint.py
python3 advance_v4_greenfield.py --dry-run
```

---

## 文档索引

| 用途 | 文件 |
| --- | --- |
| **Wiki 完整推进** | `v4-wiki-full-execution-cn.md` |
| 总方案 | `machining-production-log-v4-greenfield-cn.md` |
| P1 上下文 | `openclaw-p1-context-supplement-cn.md` |
| 旧库审计 | `production-base-v4-audit-cn.md` |
