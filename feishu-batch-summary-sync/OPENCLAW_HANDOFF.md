# 汇总脚本交接说明

## 用途

`sync_batch_summary.py` 从 **生产日志主表** 读取 `已确认` 记录的 `有效合格数量` / `有效报废数量`，按 v4 规则聚合后 upsert 到 **批工序产量汇总表**。

飞书侧**不要**再建汇总自动化或公式聚合字段。

## 已定稿规则

| 规则 | 实现位置 |
| --- | --- |
| 仅 `已确认` 计入汇总 | `config.json` → `sync.include_status` |
| #2030 A1/A2→A，B1/B2→B | `config.json` → `region_merge["#2030"]` |
| #60/#70/#80 仅批号+工序 | `aggregation_by_process` |
| #4050 批号+MG 区 | `aggregation_by_process["#4050"]` |
| 下道选批不区分上道 MG/A | 飞书视图筛选（见 OpenClaw P0 指令单 §5.1） |

## 部署步骤

1. 复制本目录到服务器，如 `~/feishu-batch-summary-sync/`
2. `pip install -r requirements.txt`
1. 复制 `config.example.json` 为 `config.json` 并填写凭证
2. `pip install -r requirements.txt`
3. 填写 `config.json` 中的 `app_id`、`app_secret`、`base_app_token`、各 `table_id`
4. 飞书应用开通权限：`bitable:app`、`bitable:app:readonly`（读主表）、写汇总表
5. 验收：`python sync_batch_summary.py --dry-run -v`  
   无飞书凭证时：`python sync_batch_summary.py --fixture --dry-run -v`
6. 正式：`python sync_batch_summary.py`
7. Cron 示例（每 30 分钟）：

```cron
*/30 * * * * cd /path/to/feishu-batch-summary-sync && /usr/bin/python3 sync_batch_summary.py >> /var/log/feishu-batch-summary.log 2>&1
```

## 批工序键示例

```
S-260617-A-#2030-A      # A1+A2 合并
S-260617-A-#4050-MG02   # 磨床按 MG
S-260617-A-#60          # 加工中心仅批号
```

## 故障排查

| 现象 | 检查 |
| --- | --- |
| dry-run 0 行 | 主表是否有 `已确认` 且有效数非空 |
| #2030 未合并 | `生产区域` 是否为 A1/A2/B1/B2；`region_merge` 是否配置 |
| API 403 | 应用是否已发布到企业、是否有表权限 |
| 字段读不到 | `field_mapping` 是否与飞书字段名一致 |

## 相关文档

- `docs/machining-production-log-v4-greenfield-cn.md`
- `docs/openclaw-p0-build-instructions-cn.md`
