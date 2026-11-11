# -*- coding: utf-8 -*-
"""
点位012偏态压缩器服务层 (Point Road Compressor Service)
======================================================
为 Web 驾驶舱提供:
  1. 当期压缩票面 (金胆/最优3/精选5/十全防线/跨路选2/剪枝明细/012大盘偏态);
  2. 样本外滚动复盘 (引擎实测 30 期仅 0.05s, 直接按需现算, 无需缓存);
  3. 历史研报索引。

与流水线 run_daily 严格同源 (同一个 PointRoadCompressor 引擎)。
@since 2026-10-22
"""
from __future__ import annotations

import glob
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.utils.paths import get_outputs_dir
from backend.modules.point_road_compressor.engine import PointRoadCompressor

logger = logging.getLogger("k8quant.point_road.service")

_OUTPUT_DIR = os.path.join(get_outputs_dir(), "point_road_compressor")

# 进程内缓存: target_period -> payload
_latest_cache: Dict[str, Dict[str, Any]] = {}


def get_point_road_prediction(target_period: Optional[str] = None,
                              force: bool = False) -> Dict[str, Any]:
    """当期压缩票面。默认即时推演 (0.03s)，与流水线落盘 JSON 同源同构。"""
    compressor = PointRoadCompressor()
    if target_period and str(target_period) in _latest_cache and not force:
        return _latest_cache[str(target_period)]

    res = compressor.run_prediction(target_period=target_period)
    payload = res.to_dict()
    payload["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _latest_cache[str(payload.get("target_period"))] = payload
    return payload


def get_point_road_review(n_periods: int = 30) -> Dict[str, Any]:
    """严格无未来信息滚动样本外对账 (现算, 30期约 0.05s)。"""
    compressor = PointRoadCompressor()
    try:
        rev = compressor.run_walk_forward_review(n_periods=n_periods, verbose=False)
    except Exception as e:
        logger.warning("point_road 复盘失败: %s", e)
        return {"status": "error", "message": str(e)}
    rev["status"] = "ok"
    rev["requested_periods"] = n_periods
    rev["note"] = "逐期仅用当日前历史压缩点位并对照实开; 剪枝回避率=被剪号码确实未开出的比例"
    return rev


def get_point_road_history() -> List[Dict[str, Any]]:
    """历史期号 JSON 产物索引 (期号降序)。"""
    out: List[Dict[str, Any]] = []
    for path in glob.glob(os.path.join(_OUTPUT_DIR, "point_road_compressed_*.json")):
        fname = os.path.basename(path)
        m = re.search(r"point_road_compressed_(\d+)\.json", fname)
        if not m:
            continue
        try:
            st = os.stat(path)
            out.append({
                "filename": fname,
                "period": m.group(1),
                "size_bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            continue
    out.sort(key=lambda x: int(x["period"]), reverse=True)
    return out[:60]
