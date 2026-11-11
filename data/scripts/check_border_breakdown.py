# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.modules.sixteen.folk_sixteen_engine import FolkSixteenEngine

engine = FolkSixteenEngine()
res_262 = engine.analyze_window(target_period=2026262)
picks = res_262["picks"]
border = picks["red_border_core"]
profiles = res_262["ball_profiles"]

print(f"{'Num':>4}  {'Hit?':>5}  {'Freq':>5}  {'Om':>4}  {'Rep?':>5}  {'012':>4}  {'Zone':>5}")
actual = res_262["hit_audit"]["actual_draw"]
for n in border:
    is_hit = "YES" if n in actual else "no"
    p = profiles[n]
    print(f"{n:>4}  {is_hit:>5}  {p['freq']:>5}  {p['omission']:>4}  {str(p['is_repeat']):>5}  {p['r012']:>4}  {p['zone']:>5}")
