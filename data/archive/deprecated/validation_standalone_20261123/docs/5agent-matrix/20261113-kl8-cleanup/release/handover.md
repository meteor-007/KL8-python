# Handover · KL8 收尾清理（2026-11-13）

## 1. 本次交付

| 项 | 结果 |
|---|---|
| C 文档路径 | 5 个文件从 `kl8-prediction-engine` 回退到实际目录 `微积分分区` |
| C 可复现性 | 新增 `requirements.txt`（numpy 2.4.6 / openpyxl 3.1.5 / torch 2.13.0 / pytest 9.1.1） |
| C 测试入口 | 新增 `pytest.ini`：`testpaths = tests`，排除 `legacy_archive`；根目录 `pytest` 40 passed |
| C 备份 | 删除回灌产生的未跟踪 `.bak`；`.gitignore` 增加 `*.bak`；保留已跟踪的旧 `.bak` |
| A 任务板 | T6 改 done；G1 新增测试数 12→18；C 测试/依赖问题标记已修复 |
| A 输入目录 | `file/` 从 796.8 MiB 降到 513.6 MiB；旧期 18 个文件归档到 A 外 |
| B 收尾 | 两个闲置会话已归档；本地目录不存在 |

C 提交：`407ba73 chore: pin dependencies and fix pytest collection`（已推送）。

## 2. A 输入归档

- 归档：`C:\D-pan\Dpanqianyi\backup\kl8_inputs\archive_2026294_2026300.zip`
  - 18 个条目，`testzip=None`，486,961,329 B；
  - 同名 manifest 记录每个条目的字节数与 CRC32。
- `file/` 保留：2026301–2026303（9 个）、3 个母版、294/295/298 的 7 个历史单测 fixture。
- 7 个 fixture 为只读（0444）。WPS/Office 后台可能重存 OLE 容器（每个 +1536 B），
  单元格值不变；**归档 zip 是原始字节权威副本**，需要时重新解压即可。
- 为消除重存，本次结束了 `wpscloudsvr` 等后台进程；需要 WPS 时重新启动即可。

## 3. 验证

```bash
cd "C:/D-pan/Dpanqianyi/点位+遗漏号分析"
python -m pytest -q                 # 359 passed
python scripts/data_sync.py --json  # exit 0（B skipped，C 2123/2026302 一致）
python scripts/prereg.py status     # active；冻结校验通过；2/2/298

cd "C:/D-pan/Dpanqianyi/微积分分区"
python -m pytest -q                 # 40 passed
python -m compileall -q kl8_engine main.py
python main.py --help
```

- 294/295/298 定向：19 passed；G1 定向（data_sync + research_bridge）：18 passed。
- preflight 对 2026302/2026303 仍能选到点位图、高概率图、找胆图。
- B 会话 `local_fb7eb913…`、`local_1003923d…` 均 `isArchived=true`。

## 4. G1–G5

| Goal | 结论 | 证据 |
|---|---|---|
| G1 需求契约保真 | 达成 | `contract.md`；上述 diff |
| G2 权限与数据脚本 | 达成（ACL/DDL N/A） | 先归档后删除；`evidence/phase2-dev-20261113.log` |
| G3 编译与验证 | 达成 | A 359 / C 40 / data_sync 0；`evidence/phase3-final-20261113.log` |
| G4 工业质检 | 达成 | `release/review-card.md`（PASS，0 High/0 Medium） |
| G5 发布就绪 | 达成 | 本文件 + `publish-copy.md` |

## 5. 回滚

- C：`git revert 407ba73` 可撤销依赖/测试配置；5 个文档路径回退是 `git checkout` 恢复，未提交额外内容。
- A 输入：从备份 zip 解压对应文件到 `file/` 即可；归档移回 `file/` 会重新增大目录。
- B 远端仓库保留，未删除；本地目录已不存在。

## 6. 残留 / 注意

1. **预注册继续**：`KL8-2026-11-11-001` 仍 active，剩余 298 期；不要改冻结核心，不把 C 研究信号并入生产 Top5。
2. **C 目录未改名**：仍为 `微积分分区`；A 的 `scripts/data_sync.py` 与 `research_compare.py` 默认路径与此一致。
3. **A 的 `file/` 仍约 513.6 MiB**：最近三期 + 母版 + 测试 fixture；旧期在 A 外备份。
4. **WPS 后台进程**：本次为字节稳定结束了 `wpscloudsvr` 等进程；不影响 A/C 运行。
5. 本轮为收尾清理，不包含任何模型/权重/预注册变更。