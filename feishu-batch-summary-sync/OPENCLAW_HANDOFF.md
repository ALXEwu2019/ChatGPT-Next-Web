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
| 下道选批不区分上道 MG/A | 飞书视图筛选（见 P1 Prompt） |

## 部署步骤

1. 复制 `config.example.json` 为 `config.json` 并填写凭证
2. `pip install -r requirements.txt`
3. 飞书应用开通权限：`bitable:app`、知识库多维表格需 `wiki:node:read`（解析 app_token）
4. 验收：`python sync_batch_summary.py --dry-run -v`  
   无凭证时：`python sync_batch_summary.py --fixture --dry-run -v`
5. 正式：`python sync_batch_summary.py` 或 `./run_sync.sh`
6. **Cron 每天 8:00、12:00、20:00**（见 `cron.example`、`docs/p1-cron-setup-cn.md`）：

```cron
0 8 * * *  cd /path/to/feishu-batch-summary-sync && ./run_sync.sh
0 12 * * * cd /path/to/feishu-batch-summary-sync && ./run_sync.sh
0 20 * * * cd /path/to/feishu-batch-summary-sync && ./run_sync.sh
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
| 汇总 0 行但有数据 | `link_tables` 是否配置；产品/工序关联字段 |
| 写入失败 LinkFieldConvFail | `summary_write.link_fields` 是否配置 |
| #2030 未合并 | `region_merge` 是否配置 |
| API 91402 NOTEXIST | wiki 库需用 `obj_token` 作 app_token |
| API 403 | 应用权限与表格协作权限 |

## 相关文档

- `docs/machining-production-log-v4-greenfield-cn.md`
- `docs/openclaw-p1-prompt-cn.md`
- `docs/p1-cron-setup-cn.md`
