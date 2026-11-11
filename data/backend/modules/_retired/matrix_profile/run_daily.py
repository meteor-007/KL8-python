# -*- coding: utf-8 -*-
"""Matrix Profile Daily Runner"""
import os
import sys

_PROJ_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_BACKEND_DIR = os.path.join(_PROJ_DIR, "backend")
for _p in [_BACKEND_DIR, _PROJ_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.modules._retired.matrix_profile.service import run_matrix_profile_pipeline


def main():
    print("=" * 70)
    print(" ⚡ [K8-QUANT] 矩阵轮廓 Matrix Profile 极速查重推演引擎启动")
    print("=" * 70)
    result = run_matrix_profile_pipeline()
    top5_str = "、".join(f"{x:02d}" for x in result.get("top3_gold") or result.get("top5_gold", []))
    top12_str = " ".join(f"{x:02d}" for x in result.get("top3_gold") or result.get("top12_elite", []))
    print(f"★ 目标期号: {result.get('target_issue')} ★")
    print(f"1. 👑 金胆 Top 5: 【 {top5_str} 】")
    print(f"2. 🛡️ 核心大底 Top 12: [ {top12_str} ]")
    print("=" * 70)


if __name__ == "__main__":
    main()
