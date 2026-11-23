# Taskboard · 20261113-kl8-research-migration

| ID | 任务 | 交付物 | 验收 | 状态 |
|---|---|---|---|---|
| M1 | 复制引擎/测试/CLI/license | `research/kl8_engine/`、`research/tests/`、`research/cli.py`、`research/LICENSE` | 文件齐全，无 `__pycache__` | done |
| M2 | 研究依赖与路径 | `research/requirements.txt`、`research/conftest.py`、`research/VENDORED.md` | `pip` 清单可读；测试可 import | done |
| M3 | 桥接默认路径 | `scripts/research_compare.py` 默认 `research/`；报告文案去 C 化 | `--help` 与真实报告 | done |
| M4 | A pytest 配置 | `pytest.ini` `testpaths=tests` | A 359；research 单独 40 | done |
| M5 | QA | 测试日志、真实报告 | A 359 / research 40 / compare exit 0 | done |
| M6 | 独立审查 | `release/review-card.md` | 0 High / 0 Medium | done |
| M7 | C 备份/归档 | `backup/kl8-prediction-engine-407ba73.zip`；C 本地删除 | 备份可读；无进程占用 | done |
| M8 | 发布 | `release/handover.md`、`publish-copy.md`；A 提交推送 | 远端 HEAD 一致 | done |