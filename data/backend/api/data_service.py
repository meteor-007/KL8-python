# -*- coding: utf-8 -*-
"""
K8-Quant Web Data Service Layer (Backend API Service)
负责解析历史数据、提炼最新预测分析报告、计算 80 码冷热态势与多维特征

方法体已拆分到 backend/modules/*/service.py 与 backend/api/service_core.py mixin；
本文件仅作 facade：QuantDataService 多继承聚合，保持 API 路由所用方法名不变。
"""
from backend.utils.paths import get_cache_dir, get_outputs_dir, get_reports_dir, get_reviews_dir
import os
import sys
import re
import json
import glob
import math
import logging
import collections
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("k8quant.service")

from backend.utils.paths import get_project_root, data_path, get_storage_dir, _ensure_project_path
_ensure_project_path()

PROJ_DIR = get_project_root()
if PROJ_DIR not in sys.path:
    sys.path.insert(0, PROJ_DIR)

from backend.api.service_core import CoreServiceMixin, _hit_leaderboard_cache, _all_modules_overview_cache
from backend.modules.legacy.genetic_algorithm.service import GeneticServiceMixin
from backend.modules.legacy.gold_pick2.service import GoldPick2ServiceMixin
from backend.modules.sixteen.service import SixteenServiceMixin
from backend.modules.formula_jingle.service import JingleServiceMixin
from backend.modules.point_suppression.service import SuppressionServiceMixin
from backend.modules.datasource.service import DatasourceServiceMixin
from backend.modules.legacy.point_omission.service import PointOmissionServiceMixin
from backend.modules.aggregation.service import AggregationServiceMixin
from backend.modules.tri_high.service import TriHighServiceMixin
from backend.modules.legacy.unified_brain.service import UnifiedBrainServiceMixin
from backend.modules.master_review.service import MasterReviewServiceMixin
from backend.modules.legacy.models.lstm.service import LstmServiceMixin
from backend.modules.legacy.gemini_pick2.service import GeminiServiceMixin
from backend.modules.legacy.follow.service import FollowServiceMixin
from backend.modules.legacy.spatial_points.service import SpatialPointsServiceMixin


class QuantDataService(
    CoreServiceMixin,
    GeneticServiceMixin,
    GoldPick2ServiceMixin,
    SixteenServiceMixin,
    JingleServiceMixin,
    SuppressionServiceMixin,
    DatasourceServiceMixin,
    PointOmissionServiceMixin,
    AggregationServiceMixin,
    TriHighServiceMixin,
    UnifiedBrainServiceMixin,
    MasterReviewServiceMixin,
    LstmServiceMixin,
    GeminiServiceMixin,
    FollowServiceMixin,
    SpatialPointsServiceMixin,
):
    def __init__(self, proj_dir: str = PROJ_DIR):
        self.proj_dir = proj_dir
        if self.proj_dir not in sys.path:
            sys.path.insert(0, self.proj_dir)
        self.history_file = data_path("kl8_history_final.txt")
        self.points_file = data_path("daily_points.txt")
        self.reports_dir = data_path("reports")
        self.param_file = data_path("param_store.json")
        self.config_file = data_path("model_config.json")
