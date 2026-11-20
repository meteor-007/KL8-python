# Taskboard · 20261113-kl8-cleanup

| ID | 任务 | 输入 | 交付物 | 写作用域 | 验收 | 依赖 | 状态 |
|---|---|---|---|---|---|---|---|
| U1 | C 路径回退 | 5 个 path-only diff | 恢复 `微积分分区` 路径 | C 文档 | `git diff --exit-code -- 每日预测指令.txt docs legacy_archive/tests/README.md` | R0 | done |
| U2 | C 可复现性 | 已装依赖、pytest 行为 | `requirements.txt`、`pytest.ini` | C 根目录 | C 根 `pytest -q` 40 passed | U1 | done |
| U3 | C 备份清理 | 回灌备份 | 删除未跟踪 `.bak`；`.gitignore` 加 `*.bak` | C 根目录 | `git status` 无新 `.bak` | U2 | done |
| U4 | A 任务板收尾 | 现有 taskboard/goal | T6 done；G1 18 项 | A `docs/5agent-matrix/20261113-kl8-integration/` | grep T6=done；G1=18 | 无 | done |
| U5 | A 输入归档 | `file/` 30 个 xls | `C:\D-pan\Dpanqianyi\backup\kl8_inputs\archive_2026294_2026300.zip`；删除旧期 | A `file/` | zip 可读；保留最近三期+母版+7 fixture；preflight 仍选到文件 | U4 | done |
| U6 | B 会话归档 | 两个 B 会话 | 归档记录 | Claude 会话 | `list_sessions` 中 B 会话已归档 | 无 | done |
| U7 | QA + 独立审查 | U1–U6 | 测试日志、review-card | `evidence/`、`release/` | A 359；C 40；0 High/0 Medium | U1–U6 | done |
| U8 | 发布与推送 | U7 | handover/publish-copy；A/C 提交 | `release/`、A/C 仓库 | 远端 HEAD 与本地一致 | U7 | done |

**写作用域原则**：C 只改路径回退、依赖/测试配置和 `.gitignore`；A 只改任务板/证据/输入归档；不改冻结核心，不碰 B 远端。
