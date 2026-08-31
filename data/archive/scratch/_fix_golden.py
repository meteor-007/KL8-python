import re
from pathlib import Path

for date, target in [
    ("20260730", "2026201"),
    ("20260731", "2026202"),
    ("20260801", "2026203"),
    ("20260802", "2026204"),
]:
    text = Path(f"reports/daily_analysis_report_{date}.md").read_text(encoding="utf-8")
    m = re.search(r"高频共振集群.*?`([^`]+)`", text)
    g = " ".join(f"{int(x):02d}" for x in re.findall(r"\d+", m.group(1))) if m else ""
    p = Path(f"reports/可复制推荐_{target}.txt")
    lines = p.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        if line.startswith("Golden"):
            out.append(f"Golden           {g}")
        else:
            out.append(line)
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(target, g)
