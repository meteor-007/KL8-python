# Contract · 研究引擎迁移

## 1. 迁移边界

| ID | 内容 | 决策 |
|---|---|---|
| M1 | C `kl8_engine/` | 复制到 A `research/kl8_engine/`（排除 `__pycache__`） |
| M2 | C `tests/` 40 项 | 复制到 A `research/tests/`；`research/conftest.py` 注入路径 |
| M3 | C `main.py` | 复制为 `research/cli.py`，避免与 A `main.py` 冲突 |
| M4 | LICENSE | 复制到 `research/LICENSE` |
| M5 | C 依赖 | `research/requirements.txt`（`-r ../requirements-dev.txt` + openpyxl/torch） |
| M6 | C 历史/输出/legacy/daily | 不迁移；C 本地备份后删除，GitHub 保留 |
| M7 | A 研究桥接 | `scripts/research_compare.py --engine-root` 默认 `ROOT / "research"` |
| M8 | A pytest | `pytest.ini` 固定 `testpaths = tests`；研究测试单独跑 |

## 2. 验收命令

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python -m pytest -q                 # 359 passed
python -m pytest -q research/tests  # 40 passed
python research/cli.py --help       # exit 0
python scripts/research_compare.py --help
python scripts/research_compare.py --period 2026302 --epochs 1  # exit 0
```

真实报告必须包含 `research/kl8_engine` 和“不进入 A 的生产 Top5 / 预注册台账”。

## 3. 非目标

- 不改 A 冻结核心、预注册、生产 Top5。
- 不把研究引擎依赖加入 A 生产 `requirements.txt`。
- 不迁移 C 的 `legacy_archive/`、daily 自动推送、重复历史/输出。
- 不删除 C 的 GitHub 仓库。

## 4. 回滚

- 删除 A `research/`、`pytest.ini`，把 `scripts/research_compare.py` 默认路径改回外部 C，即可恢复迁移前状态。
- C 本地备份 zip 与 GitHub 仓库均可恢复 C。