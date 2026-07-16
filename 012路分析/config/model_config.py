from dataclasses import dataclass
from typing import Tuple


@dataclass
class ModelConfig:
    window_short: int = 100
    window_long: int = 300
    ml_train_periods: int = 500
    lookback_k: int = 10
    w_markov: float = 0.35
    w_regress: float = 0.25
    w_ml: float = 0.40
    use_ml: bool = True
    rec_high: int = 8
    rec_mid: int = 8
    rec_low: int = 6
    kill_high: int = 8
    kill_mid: int = 7
    expected_road: Tuple[float, float, float] = (6.5, 6.75, 6.75)  # 26/27/27 * 20/80
    top_patterns: int = 10
    backtest_default: int = 30
    random_state: int = 42
