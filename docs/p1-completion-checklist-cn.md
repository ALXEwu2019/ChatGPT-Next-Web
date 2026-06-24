# P1 收尾清单

> **状态：✅ P1 已全部完成**（2026-06-23 人工验收 + 脚本 6/6 PASS）  
> **执行总单：** `docs/v4-wiki-full-execution-cn.md` · **验收记录见下文**

---

## 人工验收结果（2026-06-23）

| 验证项 | 结果 |
| --- | --- |
| 6 个下道视图能否筛到 S-TEST-A | ✅ 筛选配置生效，可检索对应报工记录 |
| 首道能否选择 `recvnnc64j5p56`（S-TEST-A 管控批） | ✅ 关联管控批筛选可用 |
| 管控 S-TEST-A #4050 行合格合计 | ✅ 显示 **80**（符合要求） |

**约束遵守：** 未用「有效合格>0」筛选 · 未重建应用 · 未对汇总表公式聚合 · 关联筛选均 record_id 点选。

---

## 自动验收

```bash
cd feishu-batch-summary-sync
python3 verify_p1.py    # 6/6 PASS
python3 verify_sprint.py  # 7/7 PASS
```

| 自动项 | 状态 |
| --- | --- |
| 管控表、汇总、主表已确认 | ✅ |
| 产品工序路线表 11 行 | ✅ |
| 不良原因联动 137 行 | ✅ |
| 不良明细表「处置类型」列 | ✅ |
| cron 8/12/20 | ⏳ 需在用户服务器部署 |

---

## A. 飞书界面（已全部完成 ✅）

| # | 任务 | 状态 |
| --- | --- | --- |
| A1 | 6 个视图上道批号筛选 | ✅ |
| A2 | 取消「允许多条」（上道批号单选） | ✅ |
| A3 | 止动块视图加产品=止动块 | ✅ |
| A4 | 首道 2 视图关联管控批筛选（已下发） | ✅ |
| A5 | 合格合计查找 4 条件（含生产区域） | ✅ |
| A6 | 生产批号各视图只读 | ✅ |

---

## B. 服务器 / 脚本

```bash
cd feishu-batch-summary-sync
python3 sync_batch_summary.py --dry-run -v
python3 sync_batch_summary.py
chmod +x run_sync.sh
# crontab: 0 8,12,20 * * * → ./run_sync.sh
```

详见 **`docs/p1-cron-setup-cn.md`**

---

## C. P1 通过后 → 下一步

| 优先级 | 任务 | 状态 | 文档 |
| --- | --- | --- | --- |
| 1 | 联动四视图 | ✅ 2026-06-23 | `feishu-defect-linkage-views-setup-cn.md` |
| 2 | cron 部署 | ⏳ 国宝 | `guobao-cron-deploy-cn.md` |
| 3 | P2 不良闭环 | ⏳ | `openclaw-p2-prompt-cn.md` |

---

*P1 收尾 v2 · 已完成*
