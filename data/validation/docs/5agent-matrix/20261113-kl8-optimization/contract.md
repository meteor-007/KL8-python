# Contract · A 项目整理与优化

## 1. 整理边界

| ID | 对象 | 动作 |
|---|---|---|
| O1 | `scripts/fusion_engine_296.py`（tracked） | `git mv` 到 `legacy/scripts/` |
| O1b | 未跟踪生成物 `fusion_engine_2026297/2026299–2026302.py` | 归档到 `backup/kl8-generated-engines-2026297-2026302.zip` 后删除 |
| O2 | `scripts/make_fusion_294/295/296.py`、`patch_*.py`、`update_fusion_294.py`、`test_backtest_294.py` | `git mv` 到 `legacy/scripts/` |
| O3 | `scripts/fusion_engine_293/294/295/2026298.py` | **保留**（测试依赖）；`2026298` 由 `.gitignore` 例外强制入库 |
| O4 | `scripts/fusion_engine_template.py`、`scripts/make_fusion_daily.py`、`scripts/run_daily.py` | **保留**（冻结/日报入口） |
| O5 | `可行性落地方案.md`、`思路.txt` | `git mv` 到 `docs/archive/source/` |
| O6 | `output/extracted_images/` | 确认无引用后删除（28M，可再生成） |
| O7 | `output/research/c_engine/` | 删除旧研究输出（已迁移为 `engine_state/`） |
| O8 | `scratch/` | 备份到 `backup/kl8-scratch-20261113.zip` 后删除 |
| O9 | `__pycache__/`、`.pytest_cache/` | 清理 |
| O10 | `file/` 514M | **不动**（当前期/母版/测试 fixture） |

## 2. 验收命令

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python -m pytest -q                 # 359 passed
python -m pytest -q research/tests  # 40 passed
python scripts/make_fusion_daily.py --help
python -m compileall -q kl8 scripts tools research
```

`pytest` 必须仍能 `from scripts.fusion_engine_293/294/295/2026298`；
`run_daily.py` 必须仍能调用 `scripts/make_fusion_daily.py`。

## 3. 非目标

- 不改 `kl8/` 核心、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py`。
- 不动 `file/`、`data/`、预注册台账、canonical 历史/点位。
- 不删除历史脚本内容，只移动到 `legacy/`；不改变测试断言。
- 不引入新依赖/不升级版本。

## 4. 回滚

- `git revert` 本次提交；或把 `legacy/scripts/*`、`docs/archive/source/*` `git mv` 回原路径。
- `scratch` 从 `backup/kl8-scratch-20261113.zip` 恢复；`output/extracted_images` 可由原始 xls 重新导出。