# 国宝 · 机加工生产日志 v4 协作执行单

> **致国宝：** 请按本单参与 v4 绿场落地。  
> **飞书应用：** [机加工生产日志 V4 Wiki](https://kcnfxml9dtzq.feishu.cn/wiki/HiqNwQnxniKGEGketZBcEC9Sn3d?table=tblXr4h68tqh2HDy&view=vewT0WgVD1)  
> **当前任务：** **任务 C · cron 定时汇总部署**（约 15 分钟）

---

## 一、进度总览

| 任务 | 内容 | 状态 |
| --- | --- | --- |
| A | P1 飞书配置（8 视图筛选、合格合计） | ✅ 2026-06-23 已完成 |
| B | 联动规则四视图（110/23/87/27） | ✅ 2026-06-23 已完成 |
| **C** | **服务器 cron（8/12/20 点汇总）** | **⏳ 请国宝执行** |
| D | P2 不良闭环 | ⏳ C 完成后启动 |

---

## 二、国宝当前任务：cron 部署

**请打开并按步骤执行：** **`docs/guobao-cron-deploy-cn.md`**

### 快速摘要

1. 在能长期开机的机器拉分支 `cursor/machining-production-log-ad82`
2. `feishu-batch-summary-sync/` 下配置 `config.json`（用 `config.v4.wiki.example.json` 模板）
3. 试跑：`python3 verify_p1.py` → `python3 sync_batch_summary.py -v`
4. 安装定时任务：每天 **08:00 / 12:00 / 20:00** 执行 `run_sync.sh`（Linux）或 `run_sync.bat`（Windows）

```bash
cd feishu-batch-summary-sync
cp config.v4.wiki.example.json config.json   # 填入 app_id / app_secret
chmod +x run_sync.sh
python3 verify_p1.py
python3 sync_batch_summary.py -v
crontab -e   # 粘贴 cron.example 三行，改路径
```

**验收：**

- [ ] `logs/sync_batch_summary.log` 有成功记录  
- [ ] crontab 或 Windows 任务计划已安装  
- [ ] 截图发群  

---

## 三、任务 D · P2（cron 完成后）

把 `docs/openclaw-p2-prompt-cn.md` 全文给飞书 AI：

- 不良明细与主表状态机（待返工→待品保确认→已确认）  
- 有不良时的有效合格/有效报废公式（见 `docs/feishu-p2-formula-fix-cn.md`）  
- 品保/班组长视图  

**验收：** 手工走通 1 条「有不良→返工→品保确认→汇总仍只读已确认」。

---

## 四、遇到问题

| 现象 | 处理 |
| --- | --- |
| 脚本报错 | 终端完整输出 + 确认 `config.json` 已填，发给项目负责人 |
| cron 没跑 | 核对 `crontab -l` 路径是否与 `config.json` 同目录 |
| 凭证不知道填什么 | 向项目负责人索取 app_id / app_secret（勿发群） |

**仓库分支：** `cursor/machining-production-log-ad82`  
**总导航：** `docs/v4-wiki-full-execution-cn.md`

---

## 五、完成后请回报（复制填空发群）

```
国宝 v4 执行回报：
- 任务 A P1 视图：✅ 已完成
- 任务 B 联动四视图：✅ 已完成（返工23/报废87/历史27）
- 任务 C cron：完成 / 未完成（机器：___，路径：___）
- 任务 D P2：未开始 / 进行中 / 已完成
- 附件：cron 截图 ___ 张、sync 日志末 10 行
```

---

*协作单 v2 · cron 交由国宝执行*
