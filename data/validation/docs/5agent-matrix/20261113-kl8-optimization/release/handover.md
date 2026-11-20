# Handover · A 项目整理与优化（2026-11-13）

## 1. 结果

| 项 | 结果 |
|---|---|
| 历史脚本 | 15 个 tracked 文件 `git mv` 到 `legacy/scripts/`（内容零变化） |
| 未跟踪生成引擎 | 2026297/299/300/301/302 归档到外部 zip 后删除 |
| 测试 fixture | `scripts/fusion_engine_2026298.py` 已入库（`.gitignore` 例外） |
| 根文档 | `思路.txt`、`可行性落地方案.md` 移到 `docs/archive/source/` |
| 生成物 | `output/extracted_images/`（28M）、旧 `output/research/c_engine/` 删除 |
| scratch | 归档到 `backup/kl8-scratch-20261113.zip`（23 条，242,855 B）后删除 |
| 缓存 | `__pycache__`、`.pytest_cache` 清理 |
| 目录体积 | 约 835M → **520M**（主要剩余为 `file/` 514M 输入） |

## 2. 保留

- 冻结核心：`kl8/*.py`、`main.py`、`config.yaml`、`scripts/fusion_engine_template.py`、
  `scripts/run_daily.py`、`scripts/prereg.py` 零改动。
- 日报链路：`scripts/make_fusion_daily.py` + 冻结模板。
- 测试依赖：`scripts/fusion_engine_293/294/295/2026298.py`。
- `file/`、`data/`、预注册台账、canonical 数据未动。

## 3. 归档

| 文件 | 条目 | 字节 | SHA-256 |
|---|---:|---:|---|
| `backup/kl8-scratch-20261113.zip` | 23 | 242,855 | `96d39da56ef55f3f7b475958a542b90e302f435c4a13579a4a1bc17eaaabe94e` |
| `backup/kl8-generated-engines-2026297-2026302.zip` | 5 | 119,125 | `7a4f354bdaaec4681d9956a58bd4ffb117bea278d30d133763546154cec8d1cd` |

`testzip=None`，可恢复。

## 4. 验证

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python -m pytest -q                 # 359 passed
python -m pytest -q research/tests  # 40 passed
python scripts/make_fusion_daily.py --help
python -m compileall -q kl8 scripts tools research
```

## 5. 回滚

- 历史脚本/根文档：`git mv` 回原路径，或 `git revert` 本次提交。
- scratch：从 zip 解压。
- 生成引擎：从 zip 解压到 `scripts/`（仅供历史回放，不入库）。
- `output/extracted_images`：无自动导出脚本；需从 `file/` 原始 xls 重新导出，非生产依赖。

## 6. 注意

1. `file/` 中 294/295/298 的 7 个 xls 工作副本与 `backup/kl8_inputs` 归档存在 OLE 容器
   +1536 B 差异（WPS/Office 重存），逐单元格值一致；归档仍是原始字节副本。
2. `legacy/scripts/` 不参与测试/生产；`pytest.ini` 固定 `testpaths = tests`。
3. 预注册 `KL8-2026-11-11-001` 未变，剩余 298 期；本次不涉及模型/权重。
4. `file/` 体积仍是主要占用；如需进一步瘦身，先确认最近三期与母版再归档。