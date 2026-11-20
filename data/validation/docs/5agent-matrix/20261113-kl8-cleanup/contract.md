# Contract · KL8 收尾清理

## 1. 范围与决策

| ID | 需求 | 决策 | 写作用域 |
|---|---|---|---|
| C1 | C 文档路径与实际目录不一致 | 保留目录名 `微积分分区`，回退 5 个文件的路径替换 | `微积分分区/每日预测指令.txt`、`docs/`、`legacy_archive/tests/README.md` |
| C2 | C 无依赖清单 | 新增 `requirements.txt`，按本机已装版本锁定；不升级 | `微积分分区/requirements.txt` |
| C3 | C 根目录 pytest 误收 legacy | 新增 `pytest.ini`，`testpaths = tests`、排除 `legacy_archive` | `微积分分区/pytest.ini` |
| C4 | C 本地备份 | 删除回灌产生的未跟踪 `.bak`；`.gitignore` 增加 `*.bak`；保留已跟踪的旧 `kl8_history.txt.bak` | `微积分分区/.gitignore` |
| A1 | 任务板 T6 仍为 todo | T6 改 done；G1 证据测试数 12→18 | A `docs/5agent-matrix/20261113-kl8-integration/` |
| A2 | A 输入目录 797M | 将 2026294–2026300 的图表压缩到 A 外的 `C:\D-pan\Dpanqianyi\backup\kl8_inputs\archive_2026294_2026300.zip`；`file/` 保留最近三期 + 3 个母版 + 294/295/298 的 7 个历史单测 fixture | A `file/`（gitignored） |
| B1 | B 闲置会话 cwd 已删除 | 归档两个 B 会话（可恢复） | Claude 会话（不写仓库） |

## 2. 验收命令

### C

```bash
cd "C:/D-pan/Dpanqianyi/微积分分区"
python -m compileall -q kl8_engine main.py
python main.py --help
python -m pytest -q
git diff --exit-code -- 每日预测指令.txt docs legacy_archive/tests/README.md
```

期望：compileall 0；help 0；pytest **40 passed**；路径文件与 HEAD 一致。

### A

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python -m pytest -q
python scripts/data_sync.py --json
python scripts/prereg.py status
```

期望：A **359 passed**；data_sync exit 0（B skipped，C ok）；预注册 active、冻结校验通过。

### A 输入归档

```bash
python - <<'PY'
from pathlib import Path
p=Path(r"C:\D-pan\Dpanqianyi\backup\kl8_inputs\archive_2026294_2026300.zip")
assert p.exists() and p.stat().st_size > 0
PY
```

期望：zip 可读、18 个条目、testzip 通过；`file/` 仅保留 2026301–2026303、3 个母版和 294/295/298 的 7 个历史单测 fixture；`file/` 体积小于清理前的 797M；294/295/298 测试 19 passed。工作副本若被 WPS/Office 重存（OLE 容器 +1536 B）不视为失败，归档 zip 是原始字节的权威副本。

## 3. 非目标

- 不重命名 C 目录；不改 A 的 `C_ROOT`/`research_compare` 默认路径。
- 不删除 B 的 GitHub 仓库。
- 不把 C 的 Transformer/贝叶斯信号写入 A 生产 Top5；不改变预注册。
- 不删除 A 的 2026301–2026303 图表与 3 个母版。
- 不升级/降级 numpy、torch、openpyxl、pytest。

## 4. G1–G5 映射

| Goal | 本契约条目 | 证据 |
|---|---|---|
| G1 | C1–C4、A1–A2、B1 | diff + 命令输出 |
| G2 | 无 ACL/DDL，N/A；A2 先归档后删除 | `evidence/phase2-*` |
| G3 | C pytest 40；A pytest 359；data_sync 0 | `evidence/phase3-*` |
| G4 | 独立审查 | `release/review-card.md` |
| G5 | 变更清单与残留 | `release/handover.md` |