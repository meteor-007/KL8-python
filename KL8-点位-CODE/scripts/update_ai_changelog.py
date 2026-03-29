#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动/手动追加 AI changelog 草稿条目。

用法：
1) 提交后自动模式
   python scripts/update_ai_changelog.py --from-latest-commit

2) 手动模式
   python scripts/update_ai_changelog.py --title "修复专家看板" --background "补充说明" --files src/data/export_expert_dashboard.py src/data/start_service.py
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ChangeEntry:
    title: str
    commit_hash: str
    background: str
    files: list[str]
    timestamp: str


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _resolve_project_root() -> Path:
    # 以脚本所在目录为基准，保证在多项目工作区中也能落到当前项目。
    return Path(__file__).resolve().parent.parent


def _load_latest_commit(repo_root: Path) -> ChangeEntry:
    try:
        meta = _run_git(["log", "-1", "--pretty=format:%H%n%s%n%cI"], repo_root).splitlines()
    except RuntimeError:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        return ChangeEntry(
            title="提交后自动记录（无提交信息）",
            commit_hash="待提交",
            background="仓库暂无可读取的最新提交，请在提交后补全该条。",
            files=[],
            timestamp=now,
        )
    if len(meta) < 3:
        raise RuntimeError("无法读取最新提交信息")
    commit_hash, subject, commit_time = meta[0], meta[1], meta[2]
    files_raw = _run_git(["show", "--name-only", "--pretty=format:", commit_hash], repo_root)
    files = [line.strip() for line in files_raw.splitlines() if line.strip()]
    timestamp = datetime.fromisoformat(commit_time.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    return ChangeEntry(
        title=subject or "提交后自动记录",
        commit_hash=commit_hash,
        background="来自 post-commit 自动记录，请补充本次业务背景。",
        files=files,
        timestamp=timestamp,
    )


def _build_manual_entry(args: argparse.Namespace) -> ChangeEntry:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return ChangeEntry(
        title=args.title or "手动补录变更",
        commit_hash=args.commit or "待提交",
        background=args.background or "请补充本次需求背景。",
        files=args.files or [],
        timestamp=now,
    )


def _render_entry(entry: ChangeEntry) -> str:
    files_block = "\n".join([f"  - `{item}`" for item in entry.files]) if entry.files else "  - （待补充）"
    return f"""
### [{entry.timestamp}] {entry.title}

- 提交号：{entry.commit_hash}
- 需求背景：
  - {entry.background}
- 改动文件：
{files_block}
- 核心实现点：
  - （待补充）
- 风险 / 回滚点：
  - （待补充）
- 验证结果：
  - （待补充）
- 后续待办：
  - （待补充）
""".rstrip() + "\n"


def _append_entry(changelog_file: Path, entry: ChangeEntry, dry_run: bool) -> None:
    content = changelog_file.read_text(encoding="utf-8")
    if entry.commit_hash and entry.commit_hash != "待提交" and entry.commit_hash in content:
        print(f"[SKIP] 已存在提交号 {entry.commit_hash}，不重复写入。")
        return

    addition = "\n" + _render_entry(entry)
    if dry_run:
        print("[DRY-RUN] 将追加以下内容：")
        print(addition)
        return

    changelog_file.write_text(content.rstrip() + "\n" + addition, encoding="utf-8")
    print(f"[OK] 已追加 changelog 条目到: {changelog_file}")


def main() -> int:
    parser = argparse.ArgumentParser(description="追加 AI_CHANGELOG 草稿条目")
    parser.add_argument("--from-latest-commit", action="store_true", help="从 git 最新提交生成条目")
    parser.add_argument("--title", type=str, default="", help="手动模式标题")
    parser.add_argument("--background", type=str, default="", help="手动模式背景说明")
    parser.add_argument("--files", nargs="*", default=[], help="手动模式改动文件列表")
    parser.add_argument("--commit", type=str, default="", help="手动模式提交号")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入文件")
    args = parser.parse_args()

    project_root = _resolve_project_root()
    changelog_file = project_root / "docs" / "AI_CHANGELOG.md"
    if not changelog_file.exists():
        raise FileNotFoundError(f"未找到 changelog 文件: {changelog_file}")

    entry = _load_latest_commit(project_root) if args.from_latest_commit else _build_manual_entry(args)
    _append_entry(changelog_file, entry, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
