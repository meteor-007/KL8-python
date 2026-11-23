# -*- coding: utf-8 -*-
"""git_sync 台账提交工具测试。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("git_sync", ROOT / "scripts" / "git_sync.py")
git_sync = importlib.util.module_from_spec(spec)
sys.modules["git_sync"] = git_sync
spec.loader.exec_module(git_sync)


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    (repo / "data" / "state").mkdir(parents=True)
    (repo / "data" / "state" / "prereg_ledger.jsonl").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    (repo / "kl8").mkdir()
    (repo / "kl8" / "report.py").write_text("# code\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def test_secret_scan():
    assert git_sync._scan_secrets("normal text") == []
    assert "GitHub PAT (ghp_)" in git_sync._scan_secrets("x ghp_" + "a" * 30)
    assert "GitHub web session" in git_sync._scan_secrets("_gh_sess=" + "a" * 30)


def test_commit_allowed_ledger_only(tmp_path):
    repo = _repo(tmp_path)
    (repo / "data" / "state" / "prereg_ledger.jsonl").write_text("{}\n{}\n",
                                                                 encoding="utf-8")
    rc = git_sync.main(["--repo", str(repo), "--period", "2026001"])
    assert rc == 0
    log = _git(repo, "log", "--oneline", "-1")
    assert "Lock 2026001" in log


def test_refuse_non_ledger_change(tmp_path):
    repo = _repo(tmp_path)
    (repo / "kl8" / "report.py").write_text("# changed\n", encoding="utf-8")
    rc = git_sync.main(["--repo", str(repo), "--period", "2026002"])
    assert rc == 1
    assert "init" in _git(repo, "log", "--oneline", "-1")


def test_refuse_secret_in_ledger(tmp_path):
    repo = _repo(tmp_path)
    (repo / "data" / "state" / "prereg_ledger.jsonl").write_text(
        '{"token":"ghp_' + "a" * 30 + '"}\n', encoding="utf-8")
    rc = git_sync.main(["--repo", str(repo), "--period", "2026003"])
    assert rc == 1
    assert "init" in _git(repo, "log", "--oneline", "-1")


def test_no_changes_push_without_remote(tmp_path):
    repo = _repo(tmp_path)
    rc = git_sync.main(["--repo", str(repo), "--push"])
    assert rc == 1  # 没有 origin，推送失败


def test_no_changes_push_synced(tmp_path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True,
                   capture_output=True)
    repo = _repo(tmp_path)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-u", "origin", "main")
    rc = git_sync.main(["--repo", str(repo), "--push"])
    assert rc == 0  # 本地与 origin/main 同步，不需要网络
