# -*- coding: utf-8 -*-
"""每日台账 git 同步（审计工具，不在冻结代码哈希内）。

只提交预注册台账相关文件：
    data/state/prereg_ledger.jsonl
    prereg/active.json
    prereg/trials.jsonl

默认**拒绝**提交代码/配置等其它变更（避免误改冻结模型）；确需提交其它文件时用 --all。
提交前扫描疑似密钥；推送前不强制、不改写历史。

    python scripts/git_sync.py --period 2026301 --push
    python scripts/git_sync.py --status
    python scripts/git_sync.py --all --message "docs: ..."
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ALLOWED = {
    "data/state/prereg_ledger.jsonl",
    "prereg/active.json",
    "prereg/trials.jsonl",
}

SECRET_PATTERNS = {
    "GitHub PAT (ghp_)": r"ghp_[A-Za-z0-9]{20,}",
    "GitHub OAuth (gho_)": r"gho_[A-Za-z0-9]{20,}",
    "GitHub fine-grained PAT": r"github_pat_[A-Za-z0-9_]{20,}",
    "GitHub web session": r"_gh_sess\s*=\s*[A-Za-z0-9%._-]{20,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "Private key block": r"-----BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY-----",
}

ATTRIBUTION = "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"


def _run(args: list[str], repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(repo), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def _changed(repo: Path) -> list[tuple[str, str]]:
    out = _run(["git", "-c", "core.quotepath=false", "status", "--porcelain"], repo)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git status 失败")
    changes = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        status, path = line[:2], line[3:].strip()
        if " -> " in path:          # rename
            path = path.split(" -> ", 1)[1]
        changes.append((status, path.replace("\\", "/")))
    return changes


def _scan_secrets(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS.items()
            if re.search(pattern, text)]


def _branch(repo: Path) -> str:
    out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    branch = out.stdout.strip()
    if out.returncode != 0 or not branch or branch == "HEAD":
        raise RuntimeError("当前不在分支上（detached HEAD），拒绝自动提交/推送")
    return branch


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--period", type=int, default=None,
                    help="期号，用于提交信息")
    ap.add_argument("--message", default=None)
    ap.add_argument("--push", action="store_true", help="提交后推送到 origin")
    ap.add_argument("--all", action="store_true",
                    help="允许提交台账之外的文件（默认拒绝）")
    ap.add_argument("--status", action="store_true", help="只显示将提交的内容")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    inside = _run(["git", "rev-parse", "--is-inside-work-tree"], repo)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        print(f"✗ {repo} 不是 git 仓库", file=sys.stderr)
        return 1
    if (repo / ".git" / "MERGE_HEAD").exists() or (repo / ".git" / "rebase-merge").exists():
        print("✗ 仓库处于 merge/rebase 中，拒绝自动提交", file=sys.stderr)
        return 1

    try:
        branch = _branch(repo)
        changes = _changed(repo)
    except RuntimeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1

    if not changes:
        if args.push:
            local_head = _run(["git", "rev-parse", "HEAD"], repo).stdout.strip()
            tracking = _run(["git", "rev-parse", f"origin/{branch}"], repo)
            if tracking.returncode == 0 and tracking.stdout.strip() == local_head:
                print(f"没有本地变更；本地与 origin/{branch} 已同步，无需推送。")
                return 0
            remote = _run(["git", "remote", "get-url", "origin"], repo)
            if remote.returncode != 0:
                print("✗ 未配置 origin，无法推送", file=sys.stderr)
                return 1
            push = _run(["git", "push", "origin", branch], repo)
            if push.returncode != 0:
                print(f"✗ 推送失败：{push.stderr.strip()}", file=sys.stderr)
                return 1
            print(f"没有本地变更；已推送/确认同步：{remote.stdout.strip()} ({branch})")
            return 0
        print("没有变更；台账已同步。")
        return 2

    allowed = [(s, p) for s, p in changes if p in ALLOWED]
    other = [(s, p) for s, p in changes if p not in ALLOWED]

    if args.status:
        print("将提交：")
        for s, p in (changes if args.all else allowed):
            print(f"  {s} {p}")
        if other and not args.all:
            print("\n以下文件不在台账白名单内（默认不提交）：")
            for s, p in other:
                print(f"  {s} {p}")
        return 0

    if other and not args.all:
        print("✗ 拒绝提交：存在台账之外的文件变更。", file=sys.stderr)
        for s, p in other:
            print(f"  {s} {p}", file=sys.stderr)
        print("如确需提交，请显式使用 --all。", file=sys.stderr)
        return 1

    files = [p for _, p in (changes if args.all else allowed)]
    if not files:
        print("没有台账变更；如需提交其它文件请用 --all。")
        return 2

    add = _run(["git", "add", "--"] + files, repo)
    if add.returncode != 0:
        print(f"✗ git add 失败：{add.stderr.strip()}", file=sys.stderr)
        return 1

    staged = _run(["git", "diff", "--cached", "--no-color"], repo).stdout
    secrets = _scan_secrets(staged)
    if secrets:
        _run(["git", "reset"], repo)
        print(f"✗ 暂存内容中检测到疑似密钥：{', '.join(secrets)}；已撤销暂存。",
              file=sys.stderr)
        return 1

    if args.message:
        message = args.message
    elif args.period:
        message = f"Lock {args.period} predictions"
    else:
        message = f"Sync prereg state {date.today().isoformat()}"
    message = f"{message}\n\n{ATTRIBUTION}"

    commit = _run(["git", "commit", "-m", message], repo)
    if commit.returncode != 0:
        print(f"✗ git commit 失败：{commit.stderr.strip() or commit.stdout.strip()}",
              file=sys.stderr)
        return 1
    print(commit.stdout.strip().splitlines()[0] if commit.stdout.strip() else "已提交")

    if args.push:
        remote = _run(["git", "remote", "get-url", "origin"], repo)
        if remote.returncode != 0:
            print("✗ 未配置 origin，无法推送（本地提交已保留）", file=sys.stderr)
            return 1
        push = _run(["git", "push", "origin", branch], repo)
        if push.returncode != 0:
            print(f"✗ 推送失败：{push.stderr.strip()}", file=sys.stderr)
            print("本地提交已保留；修复认证后可重试 git push。", file=sys.stderr)
            return 1
        print(push.stderr.strip() or push.stdout.strip())
        print(f"已推送：{remote.stdout.strip()} ({branch})")

    return 0


if __name__ == "__main__":
    sys.exit(main())