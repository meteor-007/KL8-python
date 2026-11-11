# -*- coding: utf-8 -*-
"""每日自动提交与推送 (Auto Git Sync) — 与具体项目无关的通用实现。

大白话
------
每天跑完流水线后，把当天的代码与数据变更自动提交并推到远端，省掉手工 git 操作。

设计原则
--------
1. **绝不阻断主流程**：任何异常（无 git、无远端、网络不通、推送被拒）都只记日志，
   不会让流水线失败 —— 同步失败是运维问题，不该拖垮业务计算。
2. **不做危险动作**：只 `add -A` + `commit` + `push` 到**当前分支已跟踪的远端**；
   不 force、不 rebase、不切换分支、不碰历史。
3. **幂等**：没有变更时什么都不做（重跑流水线不会产生空提交）。
4. **可关闭**：环境变量 `AUTO_GIT_PUSH=0` 时只提交不推送；`AUTO_GIT_SYNC=0` 完全跳过。
5. **通用**：仓库根用 `git rev-parse --show-toplevel` 现算，不写死路径。

用法
----
    from backend.utils.auto_git_sync import auto_sync
    auto_sync("每日流水线", note="目标期 2026301")

    命令行：python -m backend.utils.auto_git_sync --note "目标期 2026301"
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

DEFAULT_PREFIX = "chore(auto)"
COMMIT_NAME = "meteor-007"
COMMIT_EMAIL = "meteor-007@users.noreply.github.com"


def _env_flag(name: str, default: bool = True) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() not in ("0", "false", "no", "off")


def _run(args: List[str], cwd: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """执行 git 命令（统一 UTF-8 解码，失败不抛异常）。"""
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


# ══════════════════════════════════════════════════════════
# API 推送兜底：github.com:443 被墙时，走 api.github.com 写对象
# ══════════════════════════════════════════════════════════

def _owner_repo(root: str) -> Optional[str]:
    """从 origin 的 URL 解析出 owner/repo。"""
    url = _run(["git", "remote", "get-url", "origin"], root).stdout.strip()
    if not url:
        return None
    m = __import__("re").search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def _gh(args: List[str], payload: Optional[Dict[str, Any]] = None, timeout: int = 90) -> Any:
    """调用 gh api；返回解析后的 JSON，失败抛异常。"""
    import json as _json
    cmd = ["gh", "api"] + args
    if payload is not None:
        cmd += ["--input", "-"]
        r = subprocess.run(cmd, input=_json.dumps(payload), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return _json.loads(r.stdout) if r.stdout.strip() else {}


def _state_path(root: str) -> str:
    return os.path.join(root, ".git", "auto_sync_state.json")


def _load_state(root: str) -> Dict[str, Any]:
    try:
        with open(_state_path(root), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_state(root: str, data: Dict[str, Any]) -> None:
    try:
        with open(_state_path(root), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _has_commit(root: str, sha: str) -> bool:
    return _run(["git", "cat-file", "-e", f"{sha}^{{commit}}"], root).returncode == 0


def _resolve_base(root: str, remote_sha: str) -> Optional[str]:
    """找一个本地可用的提交作为 diff 基准，它与远端头内容等价。"""
    if _has_commit(root, remote_sha):
        return remote_sha
    # API 推送会在服务端生成新 sha，本地没有该对象。用上次记录的等价本地提交兜底。
    st = _load_state(root)
    if str(st.get("remote_sha", "")) == remote_sha:
        local = str(st.get("local_sha", ""))
        if local and _has_commit(root, local):
            return local
    return None


def _push_via_api(root: str, branch: str) -> Dict[str, Any]:
    """用 GitHub Git Data API 把本地领先的提交推上去。

    安全性：
      · 基准提交必须与远端头**内容等价**（对象在本地，或由上次推送记录的等价提交）；
      · 创建 commit 之前校验服务端生成的 tree sha 必须等于本地 HEAD 的 tree，
        不一致立即中止 —— 宁可不推，也绝不写坏远端。
    推送成功后记录 {remote_sha, local_sha} 映射，供下次作为等价比对基准。
    """
    import base64

    repo = _owner_repo(root)
    if not repo:
        return {"ok": False, "message": "无法解析 origin，跳过 API 推送"}

    try:
        ref = _gh([f"repos/{repo}/git/ref/heads/{branch}"])
        remote_sha = ref["object"]["sha"]
        local_sha = _run(["git", "rev-parse", "HEAD"], root).stdout.strip()
        local_tree = _run(["git", "rev-parse", f"{local_sha}^{{tree}}"], root).stdout.strip()

        remote_commit = _gh([f"repos/{repo}/git/commits/{remote_sha}"])
        if remote_commit["tree"]["sha"] == local_tree:
            _save_state(root, {"remote_sha": remote_sha, "local_sha": local_sha})
            return {"ok": True, "message": "远端内容已与本地一致"}

        base = _resolve_base(root, remote_sha)
        if not base:
            return {"ok": False,
                    "message": f"本地没有可用的比对基准（远端头 {remote_sha[:7]} 本地不存在，"
                               f"且无等价记录），拒绝用 API 推送"}
        base_tree = _run(["git", "rev-parse", f"{base}^{{tree}}"], root).stdout.strip()
        if base_tree != remote_commit["tree"]["sha"]:
            return {"ok": False, "message": "本地基准与远端树不一致，拒绝推送（可能已分叉）"}

        diff = subprocess.run(["git", "diff", "--name-status", "-z", base, local_sha],
                              cwd=root, capture_output=True, timeout=120)
        parts = [p for p in diff.stdout.split(b"\x00") if p]
        entries, i = [], 0
        while i < len(parts):
            status = parts[i].decode("utf-8", "replace")
            path = parts[i + 1].decode("utf-8", "replace")
            i += 2
            if status.startswith("D"):
                entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
                continue
            blob = subprocess.run(["git", "show", f"{local_sha}:{path}"],
                                  cwd=root, capture_output=True, timeout=120).stdout
            res = _gh([f"repos/{repo}/git/blobs"],
                      {"content": base64.b64encode(blob).decode("ascii"), "encoding": "base64"})
            fp = os.path.join(root, path)
            mode = "100755" if (os.path.exists(fp) and (os.stat(fp).st_mode & 0o111)) else "100644"
            entries.append({"path": path, "mode": mode, "type": "blob", "sha": res["sha"]})

        tree = _gh([f"repos/{repo}/git/trees"],
                   {"base_tree": remote_commit["tree"]["sha"], "tree": entries})
        if tree["sha"] != local_tree:
            return {"ok": False,
                    "message": f"生成的 tree 与本地不一致（{tree['sha'][:7]} vs {local_tree[:7]}），已中止"}

        message = _run(["git", "log", "-1", "--format=%B", local_sha], root).stdout
        commit = _gh([f"repos/{repo}/git/commits"],
                     {"message": message, "tree": tree["sha"], "parents": [remote_sha]})
        _gh([f"repos/{repo}/git/refs/heads/{branch}", "--method", "PATCH"],
            {"sha": commit["sha"], "force": False})

        # 记录映射：远端 sha 由服务端生成，本地没有该对象，下次用它对应的本地提交作基准
        _save_state(root, {"remote_sha": commit["sha"], "local_sha": local_sha})
        return {"ok": True, "message": f"经 GitHub API 推送成功 · {commit['sha'][:7]}",
                "files": len(entries)}
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "message": f"API 推送失败: {type(e).__name__}: {str(e)[:200]}"}


def _repo_root(start: str) -> Optional[str]:
    try:
        r = _run(["git", "rev-parse", "--show-toplevel"], start)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def auto_sync(prefix: str = DEFAULT_PREFIX,
              note: str = "",
              push: bool = True,
              allow_empty: bool = False,
              start_dir: Optional[str] = None) -> Dict[str, Any]:
    """把工作区变更提交并推送到当前分支的远端。

    Args:
        prefix: 提交信息前缀（放在最前，便于日后 grep 出自动提交）
        note:   追加说明，通常写当天的目标期号
        push:   是否推送（仍受 AUTO_GIT_PUSH 环境变量约束）
        allow_empty: 无变更时是否也建一个空提交（默认否）
        start_dir:  从哪个目录开始找仓库（默认本文件所在项目）

    Returns:
        {"status": "...", "message": "...", ...}
        status ∈ pushed | committed | no_changes | skipped | error
    """
    if not _env_flag("AUTO_GIT_SYNC", True):
        return {"status": "skipped", "message": "AUTO_GIT_SYNC=0，已关闭自动同步"}

    base = start_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = _repo_root(base)
    if not root:
        return {"status": "skipped", "message": "当前目录不在 git 仓库内"}

    try:
        # 分支与远端
        br = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
        branch = br.stdout.strip()
        if br.returncode != 0 or branch in ("", "HEAD"):
            return {"status": "skipped", "message": "处于游离 HEAD 状态，不自动提交"}

        remotes = _run(["git", "remote"], root).stdout.split()
        if not remotes:
            return {"status": "skipped", "message": "仓库没有配置任何远端"}

        # 暂存全部变更（.gitignore 仍然生效）
        add = _run(["git", "add", "-A"], root)
        if add.returncode != 0:
            return {"status": "error", "message": f"git add 失败: {add.stderr.strip()[:200]}"}

        # 有变更吗
        staged = _run(["git", "diff", "--cached", "--quiet"], root)
        has_changes = staged.returncode != 0
        if not has_changes and not allow_empty:
            # 工作区干净，但可能仍有"提交了却没推上去"的本地提交 —— 不能直接返回，
            # 否则 API 兜底失败时留下的待推送提交会永远卡在本地。
            pr0 = _run(["git", "push", "origin", branch], root, timeout=120)
            if pr0.returncode == 0:
                return {"status": "no_changes", "message": "工作区无变更，本地提交也已同步", "branch": branch}
            api0 = _push_via_api(root, branch)
            if api0.get("ok"):
                return {"status": "pushed", "via": "api", "branch": branch,
                        "message": api0.get("message", "API 推送成功")}
            return {"status": "no_changes", "branch": branch,
                    "message": f"工作区无变更；待推送提交未能上传：{api0.get('message')}"}

        stat = _run(["git", "diff", "--cached", "--shortstat"], root).stdout.strip()
        today = datetime.now().strftime("%Y-%m-%d")
        subject = f"{prefix}: 每日自动同步 {today}" + (f" · {note}" if note else "")
        body = (f"\n\n- 自动提交时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- 变更统计：{stat or '（无差异）'}\n"
                f"- 由 auto_git_sync 生成（流水线收尾步骤）")

        commit = _run(
            ["git", "-c", f"user.name={COMMIT_NAME}", "-c", f"user.email={COMMIT_EMAIL}",
             "commit", "-q", "-m", subject + body],
            root,
        )
        if commit.returncode != 0:
            return {"status": "error", "message": f"git commit 失败: {commit.stderr.strip()[:200]}"}

        sha = _run(["git", "rev-parse", "--short", "HEAD"], root).stdout.strip()
        result: Dict[str, Any] = {"status": "committed", "branch": branch, "sha": sha,
                                  "subject": subject, "shortstat": stat}

        if not push or not _env_flag("AUTO_GIT_PUSH", True):
            result["message"] = "已提交，按配置未推送"
            return result

        # 推到当前分支已跟踪的远端；没有上游则建立
        upstream = _run(["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"], root)
        if upstream.returncode == 0 and upstream.stdout.strip():
            push_cmd = ["git", "push", "origin", branch]
        else:
            push_cmd = ["git", "push", "-u", "origin", branch]

        pr = _run(push_cmd, root, timeout=300)
        if pr.returncode == 0:
            result["status"] = "pushed"
            result["message"] = pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else "推送成功"
            return result

        # git push 失败（国内常见：github.com:443 被墙）→ 走 api.github.com 兜底
        api_res = _push_via_api(root, branch)
        if api_res.get("ok"):
            result["status"] = "pushed"
            result["via"] = "api"
            result["message"] = api_res.get("message", "API 推送成功")
        else:
            result["message"] = (f"已提交但推送失败: {(pr.stderr or pr.stdout).strip()[:180]}"
                                 f" | API 兜底: {api_res.get('message')}")
        return result

    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "git 命令超时"}
    except Exception as e:                                        # noqa: BLE001
        return {"status": "error", "message": f"{type(e).__name__}: {e}"}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="自动提交并推送当前仓库的日常变更")
    ap.add_argument("--prefix", default=DEFAULT_PREFIX, help="提交信息前缀")
    ap.add_argument("--note", default="", help="附加说明（如目标期号）")
    ap.add_argument("--no-push", action="store_true", help="只提交不推送")
    ap.add_argument("--allow-empty", action="store_true", help="无变更也建空提交")
    args = ap.parse_args(argv)

    res = auto_sync(prefix=args.prefix, note=args.note,
                    push=not args.no_push, allow_empty=args.allow_empty)
    icon = {"pushed": "✅", "committed": "📦", "no_changes": "ℹ️",
            "skipped": "⏭", "error": "❌"}.get(res.get("status"), "·")
    print(f"{icon} [自动同步] {res.get('status')} — {res.get('message', '')}")
    if res.get("sha"):
        print(f"   分支 {res.get('branch')} · 提交 {res['sha']}")
    return 0 if res.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())