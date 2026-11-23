# reports

本目录存放只读诊断报告，不作为生产输入。

## 数据完整性 + 条件功效

生成：

```bash
python scripts/integrity_power_report.py
```

产物：

- `integrity_power_<日期>.md`
- `integrity_power_<日期>.json`

报告内容：

1. canonical history / points 的期数、连续性、非法行、日期差异、点位缺口；
2. 活动预注册 `KL8-2026-11-11-001` 的台账、描述性命中、final-only 边界；
3. 300 期 MDE、条件/无条件功效、不同真实 lift 所需期数；
4. 开奖机器/球重/顺序偏差的频率审计功效与数据限制。

注意：报告中的描述性 lift/z **不是正式分析**；正式 p 值只在 300 期结束后计算。
`file/`、`data/`、预注册台账不被报告修改。