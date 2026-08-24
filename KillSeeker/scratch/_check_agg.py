# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
d = Path(r"D:/Dpanqianyi/Python-Project/数据汇总复盘/logs")
period = "2026193"
for path in sorted(d.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:8]:
    text = path.read_text(encoding="utf-8", errors="replace")
    has_p = period in text
    has_p2 = "2026192" in text
    hits = []
    for pat in [
        r"今日目标期\s*\d+",
        r"核心定胆主推[^:：]*[:：]\s*([0-9\s]+)",
        r"分区主推号码[^:：]*[:：]\s*([0-9\s]+)",
        r"核心胆码[^:：]*[:：]\s*([0-9\s]+)",
        r"HE5|Trinity|纯净池",
    ]:
        if re.search(pat, text):
            hits.append(pat[:20])
    print(f"{path.name}: 6193={has_p} 6192={has_p2} pats={hits} size={len(text)}")
    if has_p or has_p2:
        # show a snippet around period
        idx = text.find(period) if has_p else text.find("2026192")
        print("  snippet:", repr(text[max(0, idx - 40) : idx + 120]).replace("\n", "\\n"))
