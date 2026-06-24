# 机加工生产日志 v4 · 执行推进单

> **主战场：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)  
> **完整推进单：** `docs/v4-wiki-full-execution-cn.md`  
> **更新：** P1 界面 ✅ · verify_p1 6/6 · verify_sprint 7/7

---

## 进度总览

| 阶段 | 自动/脚本 | 飞书界面（你/飞书AI） |
| --- | --- | --- |
| P0 建库+脚本 | ✅ 完成 | ✅ 完成 |
| P1 选批+对账 | ✅ 全部完成（脚本 + 界面） | ✅ **2026-06-23 验收** |
| 质量配置 | ✅ 原因库+联动137行 | ✅ **四视图 2026-06-23 验收** |
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

## 第一步：~~P1 飞书界面~~ ✅ 已完成

验收记录见 `docs/p1-completion-checklist-cn.md`。

---

## 第二步：~~联动规则四视图~~ ✅ 已完成

验收记录见 `docs/feishu-defect-linkage-views-setup-cn.md` 第八节。

| 视图 | 实际 | 预期 |
| --- | ---: | ---: |
| 启用·按产品工序 | 119（分组展示） | 110 |
| 返工原因 | 23 | 23 ✅ |
| 报废原因 | 87 | 87 ✅ |
| 历史·止动块#2030 | 27 | 27 ✅ |

---

## 第三步：cron 部署（当前，你的服务器）

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
