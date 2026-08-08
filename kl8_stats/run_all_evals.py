# kl8_stats/run_all_evals.py
# -*- coding: utf-8 -*-
"""运行全部子系统评估，输出统一信号审计报告。"""
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parents[1]


def main():
    rows = []
    # 已实现评估的子系统在此登记
    entries = [
        # (名称, 调用函数, 说明)
    ]
    out = []
    out.append("═" * 60)
    out.append("  快乐8 信号审计报告 | 生成 %s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    out.append("═" * 60)
    out.append("基线：随机 Top-k 期望命中 = k×20/80；Lift=1.0 即随机。")
    out.append("")
    out.append("| 子系统 | Lift | 95%CI | p值 | 结论 |")
    out.append("|---|---|---|---|---|")
    for name, fn, note in entries:
        try:
            r = fn()
            lift = r.get("lift")
            p = r.get("p_value")
            if p is None:
                verdict = "待补置换检验"
            elif p < 0.05:
                verdict = "**超越随机**" if lift and lift > 1 else "显著但方向存疑"
            else:
                verdict = "与随机不可区分"
            out.append(f"| {name} | {lift:.2f} | — | {p:.3f} | {verdict} |")
        except Exception as e:
            out.append(f"| {name} | 错误 | — | — | {e.__class__.__name__}: {e} |")
    content = "\n".join(out) + "\n"
    print(content)
    today = datetime.now().strftime("%Y%m%d")
    dest = BASE / "数据汇总复盘" / f"信号审计报告_{today}.md"
    dest.write_text(content, encoding="utf-8")
    print(f"▶ 已保存: {dest}")


if __name__ == "__main__":
    main()