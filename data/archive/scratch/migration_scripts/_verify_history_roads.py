# -*- coding: utf-8 -*-
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.api.data_service import QuantDataService

s = QuantDataService()
d = s.get_history_paginated(1, 3)
print("total", d["total"])
for i in d["items"]:
    print(i["period"], i.get("road_ratio"), i.get("prime_ratio"), i.get("has_01"))

from fastapi.testclient import TestClient
from backend.api.api_server import app

c = TestClient(app)
c.post("/login", data={"passcode": "k8quant@2026"})
r = c.get("/api/quant/history-table?page=1&page_size=5")
print("api", r.status_code)
item0 = (r.json().get("items") or [{}])[0]
print("fields", {k: item0.get(k) for k in ("period", "road_ratio", "prime_ratio", "has_01")})
js = c.get("/static/js/app.js").text
print("js_histRoad", "const histRoad" in js, "histBallRoadClass" in js)
html = c.get("/").text
print("html_histRoad", "histRoad(row)" in html, "histBallRoadClass" in html)
