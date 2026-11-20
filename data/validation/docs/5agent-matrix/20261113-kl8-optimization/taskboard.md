# Taskboard · 20261113-kl8-optimization

| ID | 任务 | 交付物 | 验收 | 状态 |
|---|---|---|---|---|
| O1 | 历史脚本归档 | `legacy/scripts/` + README | `git mv` 完成；测试仍 359 | done |
| O2 | 根文档归档 | `docs/archive/source/` | 根目录只留 README/每日指令 | done |
| O3 | 生成物清理 | 删除 `output/extracted_images`、旧 `c_engine` | 目录不存在；输出仍可生成 | done |
| O4 | scratch 备份/清理 | `backup/kl8-scratch-20261113.zip` | zip 可读；`scratch/` 不存在 | done |
| O5 | 缓存清理 | `__pycache__`/`.pytest_cache` | 目录不存在 | done |
| O6 | QA | A 359、research 40、日报入口 help | `evidence/phase3-*` | done |
| O7 | 独立审查 | `release/review-card.md` | 0 High/0 Medium | done |
| O8 | 发布 | `release/handover.md`、`publish-copy.md`；A 提交推送 | 远端 HEAD 一致 | done |