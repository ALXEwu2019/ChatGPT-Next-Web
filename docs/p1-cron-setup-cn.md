# P1 定时同步部署 — 每天 8:00 / 12:00 / 20:00

> 脚本目录：`feishu-batch-summary-sync/`  
> 命令：`python sync_batch_summary.py`（经 `run_sync.sh` 包装写日志）

---

## 1. 服务器准备（Linux）

```bash
# 1) 放置代码与 config.json（含凭证，勿提交 git）
cd ~
git clone https://github.com/ALXEwu2019/ChatGPT-Next-Web.git
cd ChatGPT-Next-Web
git checkout cursor/machining-production-log-ad82
cd feishu-batch-summary-sync
cp config.example.json config.json
# 编辑 config.json 填入 app_id / app_secret / app_token / table_id

# 2) 依赖
pip3 install -r requirements.txt

# 3) 可执行包装脚本
chmod +x run_sync.sh

# 4) 手动试跑
./run_sync.sh
tail -n 20 logs/sync_batch_summary.log
```

---

## 2. 安装 Cron（每天 8、12、20 点）

```bash
crontab -e
```

粘贴（**修改路径**为你的实际目录）：

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

0 8 * * *  cd /home/ubuntu/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
0 12 * * * cd /home/ubuntu/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
0 20 * * * cd /home/ubuntu/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
```

验证：

```bash
crontab -l
```

---

## 3. Windows 任务计划（若脚本跑在 Windows 服务器）

1. 打开 **任务计划程序** → 创建基本任务  
2. 触发器：每天 08:00（再建 12:00、20:00 两个任务，或一条任务三条触发器）  
3. 操作：启动程序  
   - 程序：`C:\Python312\python.exe`（按本机 Python 路径）  
   - 参数：`sync_batch_summary.py -v`  
   - 起始于：`C:\Users\WU\Projects\ChatGPT-Next-Web\feishu-batch-summary-sync`  

或批处理 `run_sync.bat`：

```bat
@echo off
cd /d C:\Users\WU\Projects\ChatGPT-Next-Web\feishu-batch-summary-sync
python sync_batch_summary.py -v >> logs\sync_batch_summary.log 2>&1
```

---

## 4. 时区说明

Cron 使用 **服务器本地时区**。若服务器为 UTC，需换算：

| 北京时间 | UTC cron |
| --- | --- |
| 08:00 | `0 0 * * *` |
| 12:00 | `0 4 * * *` |
| 20:00 | `0 12 * * *` |

建议服务器设为 `Asia/Shanghai`，或按上表调整。

---

## 5. 日志与告警

- 日志文件：`feishu-batch-summary-sync/logs/sync_batch_summary.log`
- 每次运行应看到 `sync start` / `sync done` / `Created N` 或 `Updated N`
- 失败时检查：凭证过期、飞书应用权限、网络

---

## 6. P1 与定时任务关系

| 时间 | 动作 |
| --- | --- |
| 白天报工 | 主表录入，状态改「已确认」 |
| 8 / 12 / 20 点 | cron 跑脚本 → 汇总表 upsert |
| 随时 | 打开「管理·汇总只读」「管理·批工序对账」查看 |

---

*配套：`docs/openclaw-p1-prompt-cn.md`（飞书建管控表与选批视图）*
