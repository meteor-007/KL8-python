# -*- coding: utf-8 -*-
"""逐模块逐期复盘子系统 (Per-Module Per-Period Review)。

- harvester: 把各模块当期推荐号码收割进追加式前瞻账, 解决"覆盖式落盘无历史"问题;
- reviewer : 对指定已开奖期号输出逐模块命中明细 (md + json)。
"""
from backend.modules.daily_review.harvester import harvest, infer_target_period  # noqa: F401
from backend.modules.daily_review.reviewer import review_period  # noqa: F401

__all__ = ["harvest", "infer_target_period", "review_period"]