# -*- coding: utf-8 -*-
"""微信分桶原文完整性自检 (校验「精选数 + 剩余数 = 该频池规模」).

用法:
    python scripts/ops/verify_wechat_buckets.py [期号]
默认校验 storage/stats/folk_16_window_<期号>.txt。
"""
import os
import re
import sys
import collections

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.utils.paths import get_project_root, get_storage_dir  # noqa: E402

PROJ = get_project_root()


def load_window(period_hint=None, window=16):
    """按开奖历史取最近 window 期已开数据 (升序窗口), 返回频次表。"""
    rows = []
    path = os.path.join(get_storage_dir(), "raw", "kl8_history_final.txt")
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"period:(\d+),numbers:([\d\-]+)", line.strip())
            if m:
                rows.append((int(m.group(1)), set(int(x) for x in m.group(2).split("-"))))
    rows.sort(key=lambda r: r[0], reverse=True)
    if period_hint:
        # 窗口基准期 = period_hint - 1 (目标期未开, 用其前一期起算)
        rows = [r for r in rows if r[0] < int(period_hint)]
    win = rows[:window]
    cnt = collections.Counter()
    for _, s in win:
        for n in s:
            cnt[n] += 1
    return {n: cnt.get(n, 0) for n in range(1, 81)}, win[0][0] if win else None


def parse_buckets(text):
    """解析微信分桶文本 -> {频次: (精选列表, 剩余列表)}"""
    buckets = {}
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)个(\d+)\s*[:：]?(.*)$", line)
        if not m:
            continue
        head, freq, rest = int(m.group(1)), int(m.group(2)), m.group(3)
        sel_part = rest.split("。")[0].strip()
        sel = [int(x) for x in re.findall(r"\d+", sel_part)] if sel_part else []
        rm = re.search(r"剩余\s*(\d+)\s*个\s*[:：]?(.*)", rest)
        rem_claimed = int(rm.group(1)) if rm else 0
        rem = [int(x) for x in re.findall(r"\d+", rm.group(2))] if rm and rm.group(2) else []
        buckets[freq] = {"head": head, "sel": sel, "rem_claimed": rem_claimed, "rem": rem}
    return buckets


def main():
    period = sys.argv[1] if len(sys.argv) > 1 else None
    if not period:
        cand = [f for f in os.listdir(os.path.join(get_storage_dir(), "stats"))
                if f.startswith("folk_16_window_") and f.endswith(".txt")]
        cand.sort(reverse=True)
        if not cand:
            print("❌ 未找到 folk_16_window_*.txt")
            return 1
        period = re.search(r"folk_16_window_(\d+)", cand[0]).group(1)
        path = os.path.join(get_storage_dir(), "stats", cand[0])
    else:
        path = os.path.join(get_storage_dir(), "stats", f"folk_16_window_{period}.txt")

    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        return 1

    text = open(path, encoding="utf-8").read()
    buckets = parse_buckets(text)
    freq_table, base_period = load_window(period)

    true_pool = collections.defaultdict(list)
    for n, f in freq_table.items():
        true_pool[min(f, 8)].append(n)          # 8+ 归一到 8

    print(f"目标期: {period}   窗口基准期: {base_period}   文件: {os.path.relpath(path, PROJ)}")
    print("-" * 96)
    print("%-8s %-28s %-10s %-12s %-10s %s" % ("频次桶", "真实池规模", "精选", "列出剩余", "合计", "校验"))
    problems = []
    listed = set()
    for freq in sorted(buckets, reverse=True):
        b = buckets[freq]
        key = min(freq, 8)
        pool = sorted(true_pool.get(key, []))
        listed |= set(b["sel"]) | set(b["rem"])
        total = len(b["sel"]) + len(b["rem"])
        ok = (len(pool) == total) and (len(b["rem"]) == b["rem_claimed"])
        print("%-8s %-28d %-10d %-12d %-10d %s" % (
            f"{freq}个{'' if freq < 8 else '+'}", len(pool), len(b["sel"]),
            b["rem_claimed"], total, "✅ OK" if ok else "❌ 不符"))
        if not ok:
            problems.append(f"频次 {freq}: 真实池 {len(pool)} ≠ 精选{len(b['sel'])}+剩余{len(b['rem'])} (声明剩余 {b['rem_claimed']})")

    missing = sorted(set(range(1, 81)) - listed)
    extra = sorted(listed - set(freq_table))
    print("-" * 96)
    print(f"桶内列出号码总数: {len(listed)} / 80")
    if missing:
        print(f"⚠️  未在任一桶出现的号码 ({len(missing)}): {' '.join('%02d' % n for n in missing)}")
    if extra:
        print(f"❌ 越界号码: {extra}")
    if problems:
        print("❌ 校验失败:")
        for p in problems:
            print("   ·", p)
        return 1
    print("✅ 微信分桶「精选 + 剩余 = 频池规模」全桶校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
