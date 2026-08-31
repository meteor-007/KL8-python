"""
KillSeeker V1.0 — 杀号系统超参配置
核心逻辑: 引擎评分越低 = 越不可能出 = 高置信杀号
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class SimilarityConfig:
    """引擎1: 相似走势匹配超参"""
    window_candidates: List[int] = field(default_factory=lambda: [3, 5, 8, 10])
    default_window: int = 5
    top_k: int = 5
    initial_weights: Dict[str, float] = field(default_factory=lambda: {
        "number_overlap": 0.25,
        "zone_distribution": 0.25,
        "trend_curve": 0.25,
        "matrix_shape": 0.25,
    })
    subsequent_periods: int = 3
    acf_significance: float = 0.05


@dataclass
class DensityConfig:
    """引擎2: 密集区域检测超参（纯 KDE，已移除无用的 hdbscan 参数）"""
    kde_bandwidth: str = "scott"
    cold_zone_percentile: float = 0.05
    cold_zone_consecutive_threshold: int = 10
    analysis_window: int = 60


@dataclass
class PatternConfig:
    """引擎3: 形态识别超参"""
    top_n_templates: int = 3
    tanh_smoothing_factor: float = 8.0
    tanh_center: float = 0.5
    horizontal_band_row_concentration: float = 0.7
    vertical_band_col_concentration: float = 0.7
    cluster_fill_ratio: float = 0.6
    scatter_entropy_threshold: float = 0.9
    scatter_min_components: int = 5
    full_cover_ratio: float = 0.5


@dataclass
class CurveConfig:
    """引擎4: 曲线分析超参"""
    sg_window: int = 7
    sg_polyorder: int = 2
    z_score_threshold: float = 2.0
    rolling_freq_window: int = 30
    trend_regression_window: int = 5
    fft_min_periods: int = 60


@dataclass
class MarkovConfig:
    """引擎5: 马尔可夫链超参

    设计依据（kl8_stats/markov.py 滚动 OOS，200 期）：
      - 杀号增益 z=+1.67（杀对率 76.0% vs 基线 75.0%），方向性被反向对照证实
      - 冷号回归假设被证伪（遗漏 L=0..12 条件概率平坦 0.25~0.259）
    → 信号诚实但微弱，权重从低（0.15），不单独决策。
    """
    max_k: int = 3
    prior: float = 0.25          # 单号随机开出率
    alpha: float = 12.0          # Beta 先验强度（伪计数）
    weights: tuple = (0.5, 0.3, 0.2)  # k=1/2/3 证据权重
    signal_scale: float = 1.0    # p 偏移放大倍数（×4 映射到信号 0..1）
    cold_curve_max_omission: int = 12


@dataclass
class KillConfig:
    """杀号系统核心配置"""
    # 引擎权重 (与原系统相同, 评分逻辑不变)
    # 2026-08-06: 按用户要求恢复形态识别引擎（原 pattern=0.0 为消融结论已归零，
    # 消融记录见 main.py 头部注释；代码路径已就绪）。四项重新归一化，总和保持 1.00：
    #   similarity 0.30→0.25 / density 0.30→0.25 / pattern 0.0→0.15 / curve 0.40→0.35
    # 若后续回测确认无增益，可再归零（改回 0.0 并恢复 0.30/0.30/0.40）。
    # 2026-08-09: 新增引擎5 马尔可夫链（OOS 杀号增益 z=+1.67，方向性已证）。
    # 五路重新归一化，总和保持 1.00（29 期回测：全部杀 72.8% / 高杀 73.4% / 保留 24.6%，
    # 均优于无马尔可夫口径 71.9%/72.4%/24.1%）：
    #   similarity 0.20 / density 0.20 / pattern 0.10 / curve 0.30 / markov 0.20
    engine_weights: Dict[str, float] = field(default_factory=lambda: {
        "similarity": 0.20,
        "density": 0.20,
        "pattern": 0.10,
        "curve": 0.30,
        "markov": 0.20,
    })
    # 杀号数量 (从10扩展到25, 覆盖更多低分号码)
    kill_count: int = 25
    # 高置信杀号数量 (最低分的N个)
    high_conf_kill_count: int = 10
    # 中置信杀号数量
    mid_conf_kill_count: int = 10
    # 低置信杀号数量 (观察区)
    low_conf_kill_count: int = 5
    # 保留号数量 (最高分的N个, 用于对比验证)
    # 回测: Top8 命中率约28.5% > Top20约23.6%(≈随机25%)，缩尾可提命中率
    safe_count: int = 8
    # 杀号空间均衡: 每个十年区间最多杀几个
    max_kill_per_decade: int = 4


@dataclass
class ModelConfig:
    """全局模型配置"""
    similarity: SimilarityConfig = field(default_factory=SimilarityConfig)
    density: DensityConfig = field(default_factory=DensityConfig)
    pattern: PatternConfig = field(default_factory=PatternConfig)
    curve: CurveConfig = field(default_factory=CurveConfig)
    markov: MarkovConfig = field(default_factory=MarkovConfig)
    kill: KillConfig = field(default_factory=KillConfig)
    # defense 已废弃（Hurst/FDR 防御链路已移除），保留属性避免旧脚本 AttributeError
    defense: object = None
