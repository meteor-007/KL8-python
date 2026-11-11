# -*- coding: utf-8 -*-
"""残差改错预测模块导出接口"""
from backend.modules.error_correction.residual_engine import (
    ResidualCorrectionEngine,
    TRAIN_WINDOW,
    CORRECTION_LAMBDA,
)
from backend.modules.error_correction.service import (
    run_error_correction_pipeline,
    get_latest_error_correction_data,
    get_error_correction_review,
)

__all__ = [
    "ResidualCorrectionEngine",
    "TRAIN_WINDOW",
    "CORRECTION_LAMBDA",
    "run_error_correction_pipeline",
    "get_latest_error_correction_data",
    "get_error_correction_review",
]
