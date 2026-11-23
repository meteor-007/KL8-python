【KL8 研究引擎迁移完成 · 2026-11-13】

✅ 已迁移
· C 的 kl8_engine、40 个测试、CLI、MIT License → A 的 research/
· 来源 commit 407ba73，逐字节一致
· research_compare.py 默认使用本地 research/，不再依赖 C 目录

✅ 验证
· A 生产 359 passed（不加载 torch）
· 研究测试 40 passed
· 真实对比 2026302 exit 0
· 报告明确：不进入生产 Top5 / 预注册台账

✅ 收尾
· C 本地目录已删除
· 完整备份：backup/kl8-prediction-engine-407ba73.zip（218 条目，testzip 通过）
· GitHub meteor-007/kl8-prediction-engine 保留

✅ 质量
· 独立审查 PASS：0 High / 0 Medium
· 预注册 KL8-2026-11-11-001 仍 active，冻结校验通过
· 未改模型、权重、生产 Top5

后续：研究用 python scripts/research_compare.py；生产继续按每日指令执行。不构成投注建议。