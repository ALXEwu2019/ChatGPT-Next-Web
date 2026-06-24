# 国宝 · cron 定时汇总部署执行单

> **执行人：** 国宝  
> **任务：** 在能长期开机的机器上，部署「机加工生产日志 V4」批工序汇总定时任务  
> **触发时间：** 每天 **08:00 / 12:00 / 20:00**（北京时间）  
> **预计耗时：** 约 15 分钟  
> **前置：** P1 ✅ · 联动四视图 ✅（你已完成）

---

## 一、要做什么（30 秒读懂）

白天同事在飞书主表报工并改状态为「已确认」后，脚本会把有效合格/报废数量 **汇总写入**「批工序产量汇总表」。  
cron 负责每天自动跑 3 次，**不用人工点按钮**。

```
主表「已确认」报工  →  sync_batch_summary.py  →  汇总表 upsert
         ↑                      ↑
    白天录入              8 / 12 / 20 点自动跑
```

**你不要改：** 飞书表结构、137 条联动规则、P1 视图筛选。

---

## 二、选机器

| 要求 | 说明 |
| --- | --- |
| 长期开机 | 办公室 PC、工控机、NAS、云服务器均可 |
| 能访问飞书 API | 需出网，能连 `open.feishu.cn` |
| 有 Python 3.9+ | `python3 --version` 或 `python --version` |
| 时区 | 建议 **Asia/Shanghai**；若 UTC 见第四节换算表 |

---

## 三、部署步骤（Linux，推荐）

### 步骤 1：拉代码

```bash
cd ~
git clone https://github.com/ALXEwu2019/ChatGPT-Next-Web.git
cd ChatGPT-Next-Web
git checkout cursor/machining-production-log-ad82
cd feishu-batch-summary-sync
```

若已有仓库，只需：

```bash
cd ~/ChatGPT-Next-Web   # 改成你的实际路径
git fetch origin cursor/machining-production-log-ad82
git checkout cursor/machining-production-log-ad82
git pull origin cursor/machining-production-log-ad82
cd feishu-batch-summary-sync
```

### 步骤 2：配置 config.json

```bash
cp config.v4.wiki.example.json config.json
```

用编辑器打开 `config.json`，填入飞书应用凭证（向项目负责人索取，**勿发群里、勿提交 git**）：

| 字段 | 填什么 |
| --- | --- |
| `feishu.app_id` | 飞书自建应用 App ID |
| `feishu.app_secret` | 飞书自建应用 App Secret |
| `feishu.base_app_token` | `HiqNwQnxniKGEGketZBcEC9Sn3d`（Wiki 绿场，已写在模板里） |

> 若你本机已有能跑通 `verify_p1.py` 的 `config.json`，直接复制过来即可。

### 步骤 3：安装依赖 + 试跑

```bash
pip3 install -r requirements.txt
chmod +x run_sync.sh

python3 verify_p1.py
python3 sync_batch_summary.py --dry-run -v
python3 sync_batch_summary.py -v
tail -n 30 logs/sync_batch_summary.log
```

**通过标准：**

- `verify_p1.py` 全部 `[PASS]`
- 日志末尾有 `sync done`，无 `ERROR` / `Traceback`
- 飞书「批工序产量汇总表」数据有更新（可选打开核对）

### 步骤 4：安装 crontab

```bash
crontab -e
```

粘贴下面三行，**把路径改成你机器上的实际目录**：

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin

0 8 * * *  cd /home/你的用户名/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
0 12 * * * cd /home/你的用户名/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
0 20 * * * cd /home/你的用户名/ChatGPT-Next-Web/feishu-batch-summary-sync && ./run_sync.sh
```

验证：

```bash
crontab -l
```

---

## 四、部署步骤（Windows 任务计划）

若脚本跑在 **Windows**（例如 `C:\Users\WU\Projects\ChatGPT-Next-Web`）：

### 步骤 1～3

PowerShell 或 CMD：

```bat
cd C:\Users\WU\Projects\ChatGPT-Next-Web
git checkout cursor/machining-production-log-ad82
cd feishu-batch-summary-sync
copy config.v4.wiki.example.json config.json
REM 编辑 config.json 填入凭证
pip install -r requirements.txt
python verify_p1.py
python sync_batch_summary.py --dry-run -v
python sync_batch_summary.py -v
```

### 步骤 4：任务计划程序

1. 打开 **任务计划程序** → 创建基本任务  
2. 名称：`机加工V4汇总同步`  
3. 触发器：每天，重复 3 次 → **08:00、12:00、20:00**（或建 3 个任务各一条）  
4. 操作：**启动程序**  
   - 程序：`C:\Users\WU\Projects\ChatGPT-Next-Web\feishu-batch-summary-sync\run_sync.bat`  
   - 起始于：`C:\Users\WU\Projects\ChatGPT-Next-Web\feishu-batch-summary-sync`  

也可命令行手动测：

```bat
run_sync.bat
type logs\sync_batch_summary.log
```

---

## 五、时区换算（仅服务器为 UTC 时）

| 北京时间 | UTC cron |
| --- | --- |
| 08:00 | `0 0 * * *` |
| 12:00 | `0 4 * * *` |
| 20:00 | `0 12 * * *` |

---

## 六、验收清单（完成后回报）

请逐项打勾，截图发群：

- [ ] `config.json` 已配置（凭证有效，未提交 git）
- [ ] `python3 verify_p1.py` 全部 PASS
- [ ] 手动 `./run_sync.sh`（或 `run_sync.bat`）成功
- [ ] `logs/sync_batch_summary.log` 有 `sync start` / `sync done`
- [ ] crontab 三行（或 Windows 任务计划）已安装
- [ ] 记录部署机器名称/路径（便于后续维护）

**回报模板（复制填空发群）：**

```
国宝 cron 部署回报：
- 机器：___（Linux / Windows）
- 脚本路径：___
- verify_p1：PASS / FAIL
- 手动 sync：成功 / 失败（附日志末 10 行）
- 定时任务：已装 8/12/20 / 未装
- 附件：crontab 或任务计划截图 ___ 张
```

---

## 七、常见问题

| 现象 | 处理 |
| --- | --- |
| `config.json not found` | 确认 cron 的 `cd` 路径与 `config.json` 同目录 |
| `tenant_access_token` 失败 | 检查 app_id / app_secret |
| 汇总表无变化 | 主表是否有「已确认」记录；看日志 `Created`/`Updated` 数量 |
| cron 没跑 | `crontab -l` 核对路径；看 `logs/sync_batch_summary.log` 是否有新时间戳 |
| 权限错误 | `chmod +x run_sync.sh` |

---

## 八、相关文档

| 文件 | 用途 |
| --- | --- |
| `feishu-batch-summary-sync/run_sync.sh` | Linux cron 包装脚本 |
| `feishu-batch-summary-sync/run_sync.bat` | Windows 任务计划包装脚本 |
| `feishu-batch-summary-sync/cron.example` | crontab 模板 |
| `docs/p1-cron-setup-cn.md` | 通用 cron 说明 |
| `docs/v4-wiki-full-execution-cn.md` | V4 总推进单 |

---

*国宝 cron 执行单 v1 · 机加工生产日志 V4 Wiki 绿场*
