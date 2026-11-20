# yuce-kaiyuan 前瞻记录归档

## 基本信息

| 项 | 值 |
|---|---|
| 归档时间 | 2026-11-13 |
| 来源路径 | `C:\D-pan\Dpanqianyi\yuce-kaiyuan\output\forward_test\pre_registered_20261110.jsonl` |
| 源仓库 | `meteor-007/yuce-kaiyuan` |
| 源仓库 HEAD | `a4cb2de005e9208186f9f83cfad4dcd4c2339da6`（`data: sync history through 2026302`） |
| 该文件最后提交 | `1b1cd1c5d6264d51dfa521c0c3acd7cb43fb2570`（Initial commit） |
| 源工作区状态 | `modified`，相对 HEAD 新增 2 行（未提交） |
| 归档副本 | `docs/archive/yuce-kaiyuan/forward_test/pre_registered_20261110.jsonl` |
| 字节数 | 3644 |
| 行数 | 5 |
| SHA-256 | `5341b114c64237ce758a83f39237ea05e2809ae0fe9ed9c1d9ff8e0cc0b47977` |
| 关联 meta | `docs/archive/yuce-kaiyuan/forward_test/pre_registered_20261110_meta.json`（354 字节，`3e41ea49…a7bb2`） |
| 协议文档 | `docs/archive/yuce-kaiyuan/protocol/预注册_主攻三元组_20261110.md`（3213 字节，`c5c700d1…f43d42`） |
| 本地独有文件清单 | `docs/archive/yuce-kaiyuan/local_outputs_manifest.txt`（205 条，仅元数据，不含内容） |

## 内容

| 行 | event | period | 日期 |
|---:|---|---:|---|
| 1 | prediction | 2026300 | 2026-11-10 |
| 2 | settlement | 2026300 | 2026-11-10 |
| 3 | prediction | 2026301 | 2026-11-11 |
| 4 | settlement | 2026301 | 2026-11-11 |
| 5 | prediction | 2026302 | 2026-11-12 |

第 4、5 行是归档时尚未提交的两行：2026301 的结算、2026302 的预测。

## 关联文件

- `pre_registered_20261110_meta.json`：预注册参数（200 期、p0、α、规则指纹）。
- `../protocol/预注册_主攻三元组_20261110.md`：完整预注册协议与规则冻结说明。
- `../local_outputs_manifest.txt`：B 本地未提交/被忽略文件的路径、大小、SHA-256 和修改时间；
  仅登记元数据，不保留 `output/`、`.tmp_research/` 等文件内容。

## 用途与边界

- 归档副本为**原样字节复制**，未修改内容、换行或编码。
- 这是 B（前身项目）的前瞻测试记录，**不是 A 的生产 Top5**，也不进入 A 的预注册台账。
- A 的每日流程不读取此文件；保留它只用于 B 本地删除后的追溯与审计。
- B 的原始工作区仍有这 5 行；删除 B 前无需再改动该文件。

## 校验

```bash
python -c "import hashlib,pathlib; p=pathlib.Path('docs/archive/yuce-kaiyuan/forward_test/pre_registered_20261110.jsonl'); print(hashlib.sha256(p.read_bytes()).hexdigest())"
```

期望输出：

```text
5341b114c64237ce758a83f39237ea05e2809ae0fe9ed9c1d9ff8e0cc0b47977
```