"""
daily_run_guard.py — 每日幂等校验（跨子系统共享）V1.0
=====================================
职责：每个子系统当天已执行过时，提示「直接跳过 or 重新执行」。
 - 交互终端：弹 y/n 提示（默认跳过）
 - 非交互（调度器/网页触发，无 tty 或 KL8_NON_INTERACTIVE=1）：默认跳过
 - KL8_FORCE_RERUN=1：强制重跑（跳过提示，直接执行）
 - KL8_TARGET_DATE=YYYY-MM-DD：指定本次运行的「目标日期」（PWA 补跑历史时注入，
   校验/写状态均按该日期而非真实今天进行；正常日跑不设置则行为不变）
状态记录在 <仓库根>/daily_run_state.json（可用 KL8_RUN_STATE_FILE 覆盖，便于测试）。

用法（子系统入口）：
    from daily_run_guard import guard_daily_run, mark_daily_run_done
    if guard_daily_run("定金选2-分析", period=target_period, interactive=not args.no_interactive):
        return          # 命中跳过 → 提前退出
    ... 每日主流程 ...
    mark_daily_run_done("定金选2-分析", period=target_period)

CLI：python daily_run_guard.py [--status]  → 查看今日各系统执行状态
"""

import json
import os
import shutil
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

# GBK 控制台兜底：本模块输出含 emoji（⏭️/✅/🔄 等），Windows 默认 GBK 编码
# 打印会抛 UnicodeEncodeError 崩溃（PWA 一键执行里任何子系统触发跳过都会炸）。
# 打印前 reconfigure stdout/stderr 为 errors=replace，保证跳过提示永远可打印。
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    try:
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

# 仓库根 = 本模块所在目录（各子系统入口把根加入 sys.path 后 import 本模块）
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.environ.get(
    "KL8_RUN_STATE_FILE",
    os.path.join(REPO_ROOT, "daily_run_state.json"),
)

# 状态值
STATUS_RUNNING = "running"   # 已开始执行（崩溃残留时下次视为未完成，放行重跑）
STATUS_OK = "ok"             # 成功完成

# 状态文件保留天数
KEEP_DAYS = 31


def _run_date() -> str:
    """本次运行的目标日期：补跑时由 KL8_TARGET_DATE=YYYY-MM-DD 指定，否则为真实今天。

    校验/写状态都按该日期进行（PWA 补跑历史数据时注入），正常日跑不设置则行为不变。
    """
    d = os.environ.get("KL8_TARGET_DATE", "").strip()
    if d:
        try:
            return datetime.strptime(d, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print(f"⚠️ [每日校验] 忽略无效 KL8_TARGET_DATE={d}，使用今天")
    return date.today().isoformat()


def kl8_target_date():
    """返回补跑注入 KL8_TARGET_DATE=YYYY-MM-DD 的目标日期(date)，未设置/非法返回 None。

    供各子系统适配「数据新鲜度/目标期」等基于真实今天计算的逻辑：
    补跑时间旅行时，应以目标日-1 作为数据应更新到的下限，而非真实昨天。
    """
    d = os.environ.get("KL8_TARGET_DATE", "").strip()
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except ValueError:
        return None


def _load_state() -> dict:
    """加载状态文件（损坏/缺失时返回空 dict）"""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        return state if isinstance(state, dict) else {}
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ [每日校验] 状态文件读取失败，按未执行处理: {e}")
        return {}


def _save_state(state: dict) -> None:
    """原子化写回状态文件（含旧记录清理）"""
    today = date.today().isoformat()
    try:
        keep_from = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
        state = {d: v for d, v in state.items() if d == today or d >= keep_from}
    except Exception:
        pass  # 清理失败不阻断写盘
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    # Windows 上 os.replace 会因瞬时句柄占用（杀软扫描/并发读取）失败，
    # 重试几次再降级为直写，避免子系统主流程完成后因收尾标记失败而报错退出。
    for attempt in range(4):
        try:
            os.replace(tmp, STATE_FILE)
            return
        except PermissionError:
            if attempt < 3:
                time.sleep(0.2 * (attempt + 1))
    shutil.copyfile(tmp, STATE_FILE)
    os.remove(tmp)


def _today_record(system: str) -> dict:
    """返回目标日期该系统的记录（无则空 dict）"""
    state = _load_state()
    return state.get(_run_date(), {}).get(system, {})


def _set_record(system: str, period, status: str) -> None:
    """写入/更新目标日期该系统的记录"""
    state = _load_state()
    today = _run_date()
    day = state.setdefault(today, {})
    rec = day.setdefault(system, {})
    rec["period"] = str(period) if period is not None else rec.get("period")
    rec["ran_at"] = datetime.now().strftime("%H:%M:%S")
    rec["status"] = status
    _save_state(state)


def _print_skip(system: str, rec: dict) -> None:
    """打印跳过说明（非交互默认路径）"""
    period = rec.get("period", "?")
    ran_at = rec.get("ran_at", "?")
    run_date = _run_date()
    print("=" * 70)
    # 注意：「每日校验」与「跳过」必须同行 —— PWA 调度器/app.py 按
    # 「每日校验 + 跳过」同行标记判定 skip，跨行会漏判
    deduce = "目标日期(补跑)" if os.environ.get("KL8_TARGET_DATE") else "今天"
    print(f"⏭️ [每日校验] {system} {deduce} ({run_date}) 已执行过，跳过本次执行（期号 {period}, {ran_at}）")
    print("      冗余提示: 非交互模式默认跳过；如需强制重跑，设置 KL8_FORCE_RERUN=1 或调度器传 --force")
    print("=" * 70)


def _prompt_interactive(system: str, rec: dict) -> bool:
    """交互式弹窗：返回 True=跳过，False=重新执行"""
    period = rec.get("period", "?")
    ran_at = rec.get("ran_at", "?")
    run_date = _run_date()
    deduce = "目标日期(补跑)" if os.environ.get("KL8_TARGET_DATE") else "今天"
    print("=" * 70)
    print(f"[每日校验] {system} {deduce} ({run_date}) 已执行过（期号 {period}, {ran_at}）")
    try:
        ans = input("是否跳过本次执行？[Y=跳过 / N=重新执行] (默认 Y): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans in ("n", "no", "重新执行", "0"):
        print(f"  ▶ 选择重新执行 {system} ...")
        return False
    print("  ▶ 选择跳过，本次不重复执行。")
    return True


def guard_daily_run(system: str, period=None, interactive: bool = None) -> bool:
    """每日幂等校验入口

    返回 True  = 调用方应跳过本次执行（提前 return）
    返回 False = 继续执行（调用方需在成功收尾处调用 mark_daily_run_done）

    interactive: None=自动检测(sys.stdin.isatty() 且无 KL8_NON_INTERACTIVE=1)；
                 True=强制交互弹窗；False=按非交互处理（默认跳过）
    """
    # 1) 强制重跑优先
    if os.environ.get("KL8_FORCE_RERUN") == "1":
        print(f"♻️ [每日校验] {system}: 检测到 KL8_FORCE_RERUN=1，强制重跑（覆盖今日已执行记录）")
        _set_record(system, period, STATUS_RUNNING)
        return False

    rec = _today_record(system)

    # 2) 今日未执行过（或上次崩溃残留 running）→ 放行
    if not rec or rec.get("status") != STATUS_OK:
        _set_record(system, period, STATUS_RUNNING)
        return False

    # 3) 今日已成功执行 → 交互提示 / 非交互跳过
    if interactive is None:
        interactive = sys.stdin.isatty() and os.environ.get("KL8_NON_INTERACTIVE") != "1"
    if interactive:
        skip = _prompt_interactive(system, rec)
        if not skip:
            _set_record(system, period, STATUS_RUNNING)
        return skip
    _print_skip(system, rec)
    return True


def mark_daily_run_done(system: str, period=None) -> None:
    """成功收尾处调用：把今日记录置为 ok（放行后续跳过提示）"""
    _set_record(system, period, STATUS_OK)


def clean_pycache(root: str = None) -> int:
    """清理 root 下所有 __pycache__ 目录（共享环境清理，各子系统入口收尾调用）。
    root 缺省 = 本模块所在目录；返回清理数量。失败静默（绝不阻断主流程）。"""
    if root is None:
        root = REPO_ROOT
    removed = 0
    try:
        for cache_dir in list(Path(root).rglob("__pycache__")):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir, ignore_errors=True)
                if not cache_dir.exists():
                    removed += 1
    except Exception:
        pass
    if removed > 0:
        print(f"🧹 [环境清理] 已清理 {removed} 个 __pycache__ 目录（{root}）")
    return removed


def print_status() -> None:
    """打印目标日期各系统执行状态"""
    state = _load_state()
    today = _run_date()
    day = state.get(today, {})
    print("=" * 70)
    print(f" 每日幂等校验状态 — {today}  (状态文件: {STATE_FILE})")
    print("=" * 70)
    if not day:
        print("  (今日尚无任何子系统执行记录)")
    for system, rec in sorted(day.items()):
        icon = "✅" if rec.get("status") == STATUS_OK else "🔄"
        print(f"  {icon} {system}: 期号 {rec.get('period', '?')} @ {rec.get('ran_at', '?')} "
              f"[{rec.get('status', '?')}]")
    print("=" * 70)


if __name__ == "__main__":
    if "--status" in sys.argv or len(sys.argv) > 1:
        print_status()
    else:
        print(__doc__)