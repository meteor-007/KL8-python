# 体检卡 · KL8 收尾清理

## 结论：PASS

独立审查两轮：首轮 1 Medium（`file/` 清理后净增）+ 3 Low；修复后复审 **0 High / 0 Medium**，Low 已在发布前收紧。

## 问题与闭环

| 级别 | 问题 | 状态 |
|---|---|---|
| Medium | 归档 zip 放在 `file/` 内，且恢复 7 个 fixture，导致 `file/` 从 796.8 MiB 增到 978 MiB | 已修复：zip 移到 A 外 `backup/kl8_inputs/`，`file/` 513.6 MiB |
| Low | fixture 与 zip 字节不一致（+1536 B），证据曾误称一致 | 已修复表述：WPS/Office 重存 OLE；归档为权威副本，工作副本只要求可读/等价；phase3-final 如实记录 `same False` |
| Low | taskboard U1–U8 全 todo | 已更新：U1–U6 done、U7 doing→done、U8 发布中 |
| Low | requirements torch 版本注释/末尾换行 | 已补注释与换行 |
| Low | phase2/phase3 历史路径与瞬时表述 | 已改为 backup 路径并注明“恢复瞬间状态、此后被重存” |

## 已验证

- A 冻结核心零改动：`kl8/*.py`、`main.py`、`config.yaml`、融合模板、`run_daily.py`、`prereg.py` 均无 diff。
- C 仅 `.gitignore`（`*.bak`）、`pytest.ini`、`requirements.txt`；5 个路径文件已恢复，无 `kl8-prediction-engine` 残留。
- A **359 passed**；C 根目录 **40 passed**；294/295/298 定向 **19 passed**；G1 定向 **18 passed**。
- `data_sync` exit 0（B skipped，C 2123/2026302 一致）；预注册 active、冻结校验通过、2/2/298。
- 归档 zip 18 条目、`testzip=None`、manifest 18/18 size/CRC32 一致；`file/` 513.6 MiB、19 个文件。
- fixture 功能等价：7/7 内容逐单元格相等（约 118.6 万单元格），工作副本只读 0444。
- B 目录不存在；两个 B 会话均 `isArchived=true`。
- 未发现密钥/PII；无未归档即删除；无 ACL/DDL（G2 N/A）。

## 证据

`evidence/phase0-r0-20261113.log`、`phase2-dev-20261113.log`、`phase3-qa-20261113.log`、`phase3-final-20261113.log`。