# 每日操盘话术指令 · 总入口

## 先说清楚：短话术够不够？

**不够稳。**  
只发「按 01/02 文档输出」这类短句时，模型可能不读文件、只给摘要级回复，**达不到你之前那种深稿效果**。

**推荐做法（二选一）：**

1. **首选**：整段复制 [`00_DAILY_MEGA_PROMPT.md`](./00_DAILY_MEGA_PROMPT.md) 里 `=====BEGIN=====`～`=====END=====`（自包含：思考顺序 + 强制章节 + 验收清单 + 数据路径）
2. **双重保险（Cursor 本仓库）**：同一条消息里写「先 Read 00/01/02 再按 00 输出」，并贴上 mega 正文

`01` / `02` 仍是细则源；`00` 是「粘贴即跑」的完整执行包。

---

## 使用前检查（你本地先做完）

1. 历史开奖已入库到最新期（`kl8_history_final.txt`）
2. 目标期点位已录入（`daily_points.txt`，20 码）
3. （可选）三高已录入
4. 已重算：`run_sixteen_daily` + 质合尾数模块（或全流程里对应任务）

---

## 复制即用 · 每日发送（请用 00，不要用下面的短版当主力）

打开 → 全选复制：

**[`00_DAILY_MEGA_PROMPT.md`](./00_DAILY_MEGA_PROMPT.md)**

若只想测连通、不求深稿，才用 [`03_copy_paste_snippets.md`](./03_copy_paste_snippets.md) 里的短指令。

---

## 文档清单

| 文件 | 内容 | 何时用 |
|------|------|--------|
| [00_DAILY_MEGA_PROMPT.md](./00_DAILY_MEGA_PROMPT.md) | **自包含完整双轨指令** | **每天主力复制** |
| [01_sixteen_midhot_prompt.md](./01_sixteen_midhot_prompt.md) | 16期细则与禁止项 | 改规则 / 单轨深挖 |
| [01b_sixteen_dual_track_audit.md](./01b_sixteen_dual_track_audit.md) | 方法1+方法2 双轨深稿与对账模板 | 双轨输出 / 开奖后对账 |
| [01c_four_method_copyable_daily.md](./01c_four_method_copyable_daily.md) | **每日：算法死答案 + AI研判可偏差（可复制）** | **每天主力复制输出** |
| [02_prime_tail_012_prompt.md](./02_prime_tail_012_prompt.md) | 尾号012质合细则 | 改规则 / 单轨深挖 |
| [03_copy_paste_snippets.md](./03_copy_paste_snippets.md) | 短指令 / 只要票面 | 极简或对账 |

---

## 维护说明

- 评分版本变更 → 同步改 `00` 与 `01` 的 ops 口径  
- 质合 JSON 字段变更 → 同步改 `00` 与 `02` 数据来源  
- 若某日输出「太短」：把验收清单勾选项贴回去要求补章，比换模型更有效  

---

## 统一对账与 ops_pts_v4（2026-09 落地）

| 项 | 路径 / 口径 |
|----|-------------|
| 对账账本 | `storage/reviews/unified_daily_audit.jsonl` + `unified_daily_audit_latest.json` |
| Markdown 日报 | `storage/outputs/reports/unified_audit_report_latest.md`（可复制表） |
| CLI | `python -m backend.modules.unified_audit.run_daily snapshot\|settle\|report` |
| 只读 API | `GET /api/unified-audit/latest` · `GET /api/unified-audit/ledger?limit=30` |
| 操盘评分 | **`ops_pts_v4` 默认生效**：×1.15 仅 `freq∈{3,4,5}∩点位` 且非刚开；tip3 优先点位∩精选；payload 含 `scoring_contrast.raw_v3_contrast` |
| 主口径 | 最优 3 码 tip3；旧 Top5/Top12 字段同 tip3 |
| research 舱 | nightly / `_rerun_predict_modules_today.py` **默认跳过** genetic/dtw/…/brain；加 `--with-research` 才跑 |
| 主推宪法 | 不变：主推荐来源仍=`sixteen_hot`，不恢复票权熔炉 |
