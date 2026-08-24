# -*- coding: utf-8 -*-
"""
预测结果汇总生成器 — 读取 9 个子系统最新输出，生成 10 段「可复制」汇总。
用法: python summary_report.py
输出: 本子系统目录(kl8-pwa) 预测结果汇总_YYYYMMDD.txt（同时打印到 stdout）
"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parents[1]

LEVEL_NOTE = {0: "信号强", 1: "信号中", 2: "信号较弱", 3: "信号弱"}
SEP = "─" * 65


def _read(path):
    """多编码安全读取，返回行列表；文件缺失返回 []。"""
    if not path.exists():
        return []
    for enc in ('utf-8', 'gbk', 'utf-8-sig'):
        try:
            return path.read_text(encoding=enc).splitlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def _latest(pattern):
    """取匹配 glob 的最新文件（按 mtime），无则 None。"""
    try:
        files = [p for p in BASE_DIR.glob(pattern) if p.is_file()]
    except Exception:
        return None
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def _fmt_nums(nums, pad=True):
    """号码列表 → 空格分隔字符串；pad=True 时补零为 2 位。"""
    out = []
    for n in nums:
        n = str(n).strip()
        if n.isdigit():
            out.append(f"{int(n):02d}" if pad else n)
    return " ".join(out)


def _extract_nums(text):
    """从文本中提取所有数字（含逗号/空格分隔、[a,b,c] 形式）。"""
    return re.findall(r'\d{1,2}', text)


def _mtime_hms(path):
    return datetime.fromtimestamp(path.stat().st_mtime).strftime('%H:%M') if path else "?"


# ══════════════════ 第 1 段：data 主流水线 ══════════════════
def sec_data():
    f = _latest("data/reports/daily_analysis_report_*.md")
    if not f:
        return "【1】data 主流水线（?）", ["  （未生成：data/reports/daily_analysis_report_*.md）"]
    lines = _read(f)
    text = "\n".join(lines)

    # 关键行: **极秘 Top 5**：`[36, 40, 44, 63, 64]`
    fields = {
        "极秘 Top 5": "三维融合极秘 Top5",
        "极秘 Top 12": "三维融合极秘 Top12",
        "Top 5 置信度精选": "传统AI 置信 Top5",
        "Top 12 综合拦截": "传统AI 置信 Top12",
        "高频共振集群": "多维共振号(Golden)",
        "mRMR Top 12": "mRMR Top12",
        "最终推荐 (5 码)": "Hidden Energy 5",
    }
    W = 18
    out = [f"【1】data 主流水线（{_mtime_hms(f)}）— 每日研判报告"]
    vals = {}
    for key, label in fields.items():
        m = re.search(rf"\*\*{re.escape(key)}\*\*[：:]\s*`?\[([\d,\s]+)\]", text)
        vals[label] = _fmt_nums(_extract_nums(m.group(1))) if m else "—"
        out.append(f"  {label:<{W}}: {vals[label]}")

    # 可复制精选块
    copy_map = {
        "最终精选爆发码（Top 5）": "方案2 爆发Top5",
        "重点防守号码（杀号 Top 3）": "防守杀Top3",
        "精选5码": "Excel 精选5码",
        "回避5码": "回避5码",
    }
    cp = {}
    for key, label in copy_map.items():
        m = re.search(rf"◎\s*{re.escape(key)}\s*\n\s*([\d,\s，、]+)", text)
        cp[label] = _fmt_nums(_extract_nums(m.group(1))) if m else "—"
    dang = re.search(r"\*\*高置信定胆 \(LR主推\)\*\*[：:]\s*`?\[([\d,\s]+)\]", text)
    pool = re.search(r"\*\*纯净池号码\*\*[：:]\s*`?\[([\d,\s]+)\]", text)
    dang_s = _fmt_nums(_extract_nums(dang.group(1))) if dang else "—"
    pool_s = _fmt_nums(_extract_nums(pool.group(1))) if pool else "—"
    out.append(f"  {'纯净池定胆(高置信)':<{W}}: {dang_s} | 纯净池: {pool_s}")
    out.append(f"  {'方案2 爆发Top5':<{W}}: {cp['方案2 爆发Top5']} | 防守杀Top3: {cp['防守杀Top3']}")
    out.append(f"  {'Excel 精选5码':<{W}}: {cp['Excel 精选5码']} | 回避5码: {cp['回避5码']}")
    # 目标期
    m = re.search(r"目标期\s*[:：]?\s*(\d{7})", text)
    # 规则选号器 (无前视验证信号) 输出
    rp = _latest("data/reports/rule_picker_*.txt")
    if rp:
        rlines = _read(rp)
        out.append("  ── 规则选号器（无前视验证信号）──")
        out.extend("\t" + ln for ln in rlines)
    return f"【1】data 主流水线（{_mtime_hms(f)}）— 每日研判报告", out[1:], (m.group(1) if m else None)


# ══════════════════ 第 2 段：双层LSTM ══════════════════
def sec_lstm():
    f = _latest("双层LSTM/outputs/predictions/prediction_*.txt")
    if not f:
        return ["【2】双层LSTM（?）", "  （未生成：双层LSTM/outputs/predictions/prediction_*.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    gold = re.search(r"金胆[:：]\s*(\d+)", text)
    silver = re.search(r"银胆[:：]\s*(\d+)", text)
    bronze = re.search(r"铜胆[:：]\s*(\d+)", text)
    top10 = re.search(r"Top10[:：]\s*([\d\-]+)", text)
    zones = []
    for ln in lines:
        m = re.match(r"\s*(\d)头\(\d+-\d+\)[:：]\s*预测\s*(\d+)\s*个", ln)
        if m:
            zones.append(f"{m.group(1)}头{m.group(2)}")
    out = [f"【2】双层LSTM（{_mtime_hms(f)}）"]
    g = f"{int(gold.group(1)):02d}" if gold else "—"
    s = f"{int(silver.group(1)):02d}" if silver else "—"
    b = f"{int(bronze.group(1)):02d}" if bronze else "—"
    out.append(f"  金胆: {g} | 银胆: {s} | 铜胆: {b}")
    out.append(f"  Top10: {top10.group(1) if top10 else '—'}")
    out.append(f"  分区: {' / '.join(zones) if zones else '—'}")
    return out


# ══════════════════ 第 3 段：顺口溜 Python 版 ══════════════════
def sec_abc():
    f = _latest("顺口溜/output/latest_predict.txt")
    if not f:
        return ["【3】顺口溜 Python 版（?）", "  （未生成：顺口溜/output/latest_predict.txt）"]
    lines = _read(f)
    text = "\n".join(lines)

    def take(line):
        m = re.search(r"[:：]\s*(.*)$", line)
        return m.group(1).strip() if m else ""

    strong = ref = core = ""
    for ln in lines:
        if not strong and re.match(r"\s*强推\s*[:：]", ln):
            strong = take(ln).replace("（暂无，可关注下方参考号）", "（暂无）")
        if not ref and re.match(r"\s*参考\s*[:：]", ln):
            ref = take(ln)
        if not core and "核心推荐 Top10" in ln:
            core = take(ln)
    # 参考 重排: 32(0.75|史15%) → 32(0.75)
    ref_pairs = re.findall(r"(\d{1,2})\(([\d.]+)\|史[\d.]+%\)", ref)
    ref = " ".join(f"{int(a):02d}({b})" for a, b in ref_pairs) if ref_pairs else ref

    # 触发规则明细
    rules = []
    for m in re.finditer(r"^\s*\d+\.\s+(\[R\d+\])\s*(?:\([^)]*\)\s*)?(.+)$", text, re.M):
        rid, desc = m.group(1), m.group(2).strip()
        seg = text[m.start():m.start() + 400]
        pm = re.search(r"→\s*预测\s+([\d\s,]+?)\s*\|\s*置信\s+(\d+)%", seg)
        hm = re.search(r"号码命中率([\d.]+)%", seg)
        if pm:
            preds = ", ".join(f"{int(n):02d}" for n in _extract_nums(re.sub(r"[^0-9,\s]", "", pm.group(1))))
            conf = pm.group(2)
            hist = f"{int(float(hm.group(1)) + 0.5)}%" if hm else "?"
            rules.append(f"    {f'{rid} {desc}':<28} → {preds:<6} 置信{conf}% 史{hist}")
    out = [f"【3】顺口溜 Python 版（{_mtime_hms(f)}）"]
    out.append(f"  ★强推: {strong if strong else '（暂无）'}")
    out.append(f"  参考: {ref if ref else '（暂无）'}")
    out.append(f"  核心推荐: {core if core else '（暂无）'}")
    out.append("  触发规则明细:")
    out.extend(rules if rules else ["    （无触发规则）"])
    return out


# ══════════════════ 第 4 段：顺口溜 C 版本 ══════════════════
def sec_abc_c():
    f = _latest("顺口溜/output/c/latest_c_predict.txt")
    if not f:
        return ["【4】顺口溜 C版本（?）", "  （未生成：顺口溜/output/c/latest_c_predict.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    total = re.search(r"规则总数[:：]\s*(\d+)", text)
    trig = re.search(r"触发规则[:：]\s*(\d+)", text)
    out = [f"【4】顺口溜 C版本（{_mtime_hms(f)}）— 与Python详细匹配"]
    out.append(f"  C版规则: {total.group(1) if total else '?'}条(数据挖掘·同出解读, 已排除A/B收录) | 触发{trig.group(1) if trig else '?'}条:")
    out.append("  触发规则:")
    n = 0
    for m in re.finditer(r"^\s*\[\d+\]\s+(#\d+[^\n]*)$", text, re.M):
        rule_text = m.group(1).strip()
        seg = text[m.start():m.start() + 300]
        tm = re.search(r"触发[:：]\s*[^\[]*\[([\d,\s，、]+)\]", seg)
        dm = re.search(r"推断[:：]\s*[^\[]*\[([\d,\s，、]+)\]", seg)
        trig_nums = ",".join(f"{int(n):02d}" for n in _extract_nums(tm.group(1))) if tm else "?"
        pred_nums = ",".join(f"{int(n):02d}" for n in _extract_nums(dm.group(1))) if dm else "?"
        out.append(f"    {rule_text}    触发[{trig_nums}] → {pred_nums}")
        n += 1
    if not n:
        out.append("    （无触发规则）")
    return out


# ══════════════════ 第 5 段：重点点位分析 ══════════════════
def sec_points():
    f = _latest("重点点位分析/logs/prediction_logs.txt")
    if not f:
        return ["【5】重点点位分析（?）", "  （未生成：重点点位分析/logs/prediction_logs.txt）"]
    lines = _read(f)
    # 以 ---- 分隔，取最后一个块（含时间戳头）
    blocks, cur = [], []
    for ln in lines:
        if re.match(r"^-{10,}$", ln.strip()):
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    block = blocks[-1] if blocks else []
    if not any(re.match(r"^\[\d{4}-\d{2}-\d{2}", ln) for ln in block):
        # 无分隔时退化为最后以时间戳开头的块
        for i, ln in enumerate(lines):
            if re.match(r"^\[\d{4}-\d{2}-\d{2}", ln):
                block = lines[i:]
    ts = ""
    for ln in block:
        m = re.match(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", ln)
        if m:
            ts = m.group(1)[11:]
            break
    sep = SEP
    out = [f"【5】重点点位分析（{ts}）— 完整预测日志原文"]
    out.append(sep)
    out.extend(block)
    out.append(sep)
    return out


# ══════════════════ 第 6 段：定金选2-分析 ══════════════════
def sec_dan2():
    f = _latest("定金选2-分析/logs/prediction_logs.txt")
    if not f:
        return ["【6】定金选2-分析（?）", "  （未生成：定金选2-分析/logs/prediction_logs.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    # 取最后一个「预测期号」起的块
    idx = text.rfind("预测期号:")
    block = text[idx:] if idx >= 0 else text
    dyn = re.search(r"动态金胆:\s*(\d+)", block)
    hot = re.search(r"热号金胆:\s*(\d+)", block)
    lvl = re.search(r"降级评级:\s*Level\s*(\d)", block)
    pool_size = re.search(r"温号池规模:\s*(\d+)", block)
    pool = re.search(r"温号池:\s*([\d\-]+)", block)
    alt = re.search(r"备选金胆:\s*(\d+)", block)
    mains = re.findall(r"Top (\d) 推荐组合\s*[:：]\s*\[([\d\-]+)\]\s*\|\s*综合评分[:：]?\s*([\d.]+)", block)
    hots = re.findall(r"热-Top (\d) 推荐组合\s*[:：]\s*\[([\d\-]+)\]\s*\|\s*综合评分[:：]?\s*([\d.]+)", block)
    out = [f"【6】定金选2-分析（{_mtime_hms(f)}）", SEP]
    lv = lvl.group(1) if lvl else "?"
    note = LEVEL_NOTE.get(int(lv), "") if lv.isdigit() else ""
    out.append(f"  动态金胆: {dyn.group(1) if dyn else '—'} | 热号金胆: {hot.group(1) if hot else '—'} | 降级: Level {lv}({note})")
    out.append("  主推组合: " + " | ".join(f"[{a}] {b}" for _, a, b in mains[:3]) if mains else "  主推组合: —")
    out.append("  热号组合: " + " | ".join(f"[{a}] {b}" for _, a, b in hots[:3]) if hots else "  热号组合: —")
    pool_nums = pool.group(1).split("-") if pool else []
    pool_s = _fmt_nums(pool_nums)
    out.append(f"  备选金胆: {alt.group(1) if alt else '—'} | 温号池{pool_size.group(1) if pool_size else '?'}号: {pool_s}" if pool_s else f"  备选金胆: {alt.group(1) if alt else '—'}")
    return out


# ══════════════════ 第 7 段：KillSeeker ══════════════════
def sec_kill():
    f = _latest("KillSeeker/logs/kill_report.txt")
    if not f:
        return ["【7】KillSeeker（?）", "  （未生成：KillSeeker/logs/kill_report.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    idx = text.rfind("[最新·待开奖]")
    block = text[idx:] if idx >= 0 else text
    conf = re.search(r"综合把握:\s*([\d.]+)%", block)
    groups = {
        "🔴高置信杀": re.search(r"🔴\s*高置信杀号[\s\S]*?$\n\s*([\d\s]+)", block, re.M),
        "🟡中置信杀": re.search(r"🟡\s*中置信杀号[\s\S]*?$\n\s*([\d\s]+)", block, re.M),
        "🟠观察区": re.search(r"🟠\s*观察区杀号[\s\S]*?$\n\s*([\d\s]+)", block, re.M),
        "🟢保留号": re.search(r"🟢\s*保留号[\s\S]*?$\n\s*([\d\s]+)", block, re.M),
    }
    stat = re.search(r"杀号统计[:：]\s*杀号(\d+)个\s*\|\s*保留(\d+)个\s*\|\s*排除[\d.]+%\s*\|\s*剩余可选(\d+)个", block)
    if conf:
        out = [f"【7】KillSeeker 杀号（{_mtime_hms(f)} · 综合把握{conf.group(1)}%）", SEP]
    else:
        out = [f"【7】KillSeeker 杀号（{_mtime_hms(f)}）", SEP]
    for label, m in groups.items():
        if m:
            out.append(f"  {label}: {_fmt_nums(_extract_nums(m.group(1)))}")
        else:
            out.append(f"  {label}: —")
    if stat:
        out.append(f"  排除 {stat.group(1)}/80 → 剩余可选 {stat.group(3)}")
    return out


# ══════════════════ 第 8 段：点位期数-追踪 ══════════════════
def sec_pointtrack():
    f = _latest("点位期数-追踪/output/点位每日分析_*_T*.md")
    if not f:
        return ["【8】点位期数-追踪（?）", "  （未生成：点位期数-追踪/output/点位每日分析_*_T*.md）"]
    lines = _read(f)
    text = "\n".join(lines)
    strong = re.search(r"★\s*强共振点位[^\n]*\n\s*([\d,\s，、]+)", text)
    overall = re.search(r"★\s*综合评估点位[^\n]*\n\s*([\d,\s，、]+)", text)

    def wrap(nums_s, width=46):
        cur, rows = "", []
        for tok in nums_s.split():
            nxt = f"{cur} {tok}".strip()
            if len(nxt) > width and cur:
                rows.append(cur)
                cur = tok
            else:
                cur = nxt
        if cur:
            rows.append(cur)
        return rows

    out = [f"【8】点位期数-追踪（{_mtime_hms(f)}）", SEP]
    indent = " " * 12
    if strong:
        rows = wrap(_fmt_nums(_extract_nums(strong.group(1))))
        out.append(f"  ★强共振(≥3路): {rows[0]}")
        for r in rows[1:]:
            out.append(f"{indent}{r}")
    else:
        out.append("  ★强共振(≥3路): —")
    if overall:
        rows = wrap(_fmt_nums(_extract_nums(overall.group(1))))
        out.append(f"  综合评估(≥1路): {rows[0]}")
        for r in rows[1:]:
            out.append(f"{indent}{r}")
    else:
        out.append("  综合评估(≥1路): —")
    return out


# ══════════════════ 第 9 段：gemini选2-预测 ══════════════════
def sec_gemini():
    f = _latest("数据汇总复盘/gemini金银铜数据分析-汇总.txt")
    if not f:
        return ["【9】gemini选2-预测（?）", "  （未生成：数据汇总复盘/gemini金银铜数据分析-汇总.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    m = re.search(r"^(\d{8}[:：].*?)(?=^\d{8}[:：]|\Z)", text, re.M | re.S)
    out = [f"【9】gemini选2-预测（{_mtime_hms(f)}）"]
    if m:
        out.extend("\t" + ln for ln in m.group(1).rstrip().split("\n"))
    else:
        out.append("\t（无可解析记录）")
    return out


# ══════════════════ 第 10 段：数据汇总复盘 ══════════════════
def sec_aggregate():
    f = _latest("数据汇总复盘/logs/分区深度聚合推荐_*.txt")
    if not f:
        return ["【10】数据汇总复盘（?）", "  （未生成：数据汇总复盘/logs/分区深度聚合推荐_*.txt）"]
    lines = _read(f)
    text = "\n".join(lines)
    ver = re.search(r"深度聚合推荐\s*(V[\d.]+)", text)
    out = [f"【10】数据汇总复盘 {ver.group(1) if ver else ''} 聚合（{_mtime_hms(f)}）", SEP]
    for key, label in [("核心定胆主推(2码)", "💎核心定胆(2码)"),
                       ("分区主推号码(16码)", "🔥分区主推(16码)"),
                       ("全球精英 Top-12", "🏆全球精英Top-12")]:
        m = re.search(rf"{re.escape(key)}[:：]\s*([\d\s]+)", text)
        out.append(f"  {label}: {_fmt_nums(_extract_nums(m.group(1))) if m else '—'}")
    # 防守/关注现成汇总行（数量动态，如 6码/11码）
    for key, label, fallback in [("防守号码", "🛡️防守", "7"),
                                 ("关注号码", "👁️关注", "12")]:
        m = re.search(rf"{re.escape(key)}\((\d+)码\)[:：]\s*([\d\s]+)", text)
        if m:
            out.append(f"  {label}({m.group(1)}码): {_fmt_nums(_extract_nums(m.group(2)))}")
        else:
            out.append(f"  {label}({fallback}码): —")
    # KillSeeker 仲裁
    hi = re.search(r"🔴高杀[:：]\s*([\d\s]+)", text)
    keep = re.search(r"🟢保留[:：]\s*([\d\s]+)", text)
    dbl = re.search(r"✅双重确认[^\n]*[:：]\s*([\d\s]+)", text)
    if hi:
        out.append(f"  ⚔️KillSeeker仲裁: 高杀 {_fmt_nums(_extract_nums(hi.group(1)))}")
        parts = []
        if keep:
            parts.append(f"保留 {_fmt_nums(_extract_nums(keep.group(1)))}")
        if dbl:
            parts.append(f"双重确认 {_fmt_nums(_extract_nums(dbl.group(1)))}")
        if parts:
            out.append("    " + " | ".join(parts))
    # 近10期（取「近10期命中率」段）
    m10 = re.search(r"近10期命中率.*?(?=近30期命中率|\Z)", text, re.S)
    if m10:
        seg = m10.group(0)
        ding = re.search(r"定胆[:：]\s*\d+/\d+\s*\(([\d.]+)%\)\s*Lift\s*[=:]?\s*([\d.]+)x", seg)
        zhu = re.search(r"主推[:：]\s*\d+/\d+\s*\(([\d.]+)%\)\s*Lift\s*[=:]?\s*([\d.]+)x", seg)
        concl = re.search(r"优化结论[:：]\s*([^，,]+)", seg)
        parts = []
        if ding:
            parts.append(f"定胆{ding.group(1)}%(Lift{ding.group(2)}x)")
        if zhu:
            parts.append(f"主推{zhu.group(1)}%")
        if concl:
            parts.append(f"状态: {concl.group(1).strip()}")
        if parts:
            out.append("  近10期: " + " | ".join(parts))
    return out


# ══════════════════ 第 11 段：信号审计 ══════════════════
def sec_audit():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from kl8_stats.run_all_evals import main as _unused  # noqa: 确保模块可导入
    f = _latest("数据汇总复盘/信号审计报告_*.md")
    if not f:
        return ["【11】信号审计（?）", "  （未生成：数据汇总复盘/信号审计报告_*.md）"]
    lines = _read(f)
    return [f"【11】信号审计（{_mtime_hms(f)}）", *["\t" + ln for ln in lines]]


def build(target=None):
    secs = [sec_data(), sec_lstm(), sec_abc(), sec_abc_c(), sec_points(),
            sec_dan2(), sec_kill(), sec_pointtrack(), sec_gemini(), sec_aggregate(),
            sec_audit()]
    if target is None:
        for s in secs:
            if isinstance(s, tuple) and len(s) > 2 and s[2]:
                target = s[2]
                break
    now = datetime.now()
    lines = []
    lines.append("═" * 60)
    lines.append(f"  快乐8 预测结果汇总（可复制） | 目标期 {target or '?'} | 生成 {now:%Y-%m-%d %H:%M}")
    lines.append("═" * 60)
    for s in secs:
        if isinstance(s, tuple):
            lines.append(s[0])
            lines.extend(s[1])
        else:
            lines.extend(s)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    target = None
    d = sec_data()
    if isinstance(d, tuple) and len(d) > 2:
        target = d[2]
    content = build(target)
    print(content)
    out_file = Path(__file__).resolve().parent / f"预测结果汇总_{datetime.now():%Y%m%d}.txt"
    out_file.write_text(content, encoding="utf-8")
    print(f"▶ 已保存: {out_file}")


if __name__ == "__main__":
    main()