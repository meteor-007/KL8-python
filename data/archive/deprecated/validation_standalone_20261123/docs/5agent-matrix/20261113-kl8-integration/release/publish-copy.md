【KL8 三项目整合完成】

- 生产线不变：kl8-point-analysis（13 模块 + H1-H7 + 300 期预注册）
- 新增统一数据校验：scripts/data_sync.py（A/B/C 历史与点位只读比对）
- 新增研究引擎对比：scripts/research_compare.py（C 的 Transformer + 贝叶斯 + Borda + 30 码缩水，独立输出）
- 验证：A 全量 353 passed；新增 12 passed；独立质检 PASS（0 High / 0 Medium）
- 数据：A 历史 2123 期/最新 2026302；B/C 各落后 1 期；2023179/2024295/2025037 三期单号差异待人工核对
- 预注册：KL8-2026-11-11-001 active，冻结校验通过
- 文档：docs/5agent-matrix/20261113-kl8-integration/
- 说明：研究引擎输出不进入生产 Top5/预注册台账；不构成投注建议
