# -*- coding: utf-8 -*-
"""配置加载（§3.4 / §8.6）。

单一 schema，支持 `${VAR}` 与 `${VAR:-default}` 形式的环境变量展开。
路径解析顺序：显式配置 > 环境变量 KL8_DATA_DIR > 默认相对路径。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")

# 与 config.yaml 保持一致的默认值，缺键时兜底
DEFAULTS: dict[str, dict[str, Any]] = {
    "data": {
        "python_project": {
            "enabled": True,
            "dir": "${KL8_DATA_DIR:-../Python-Project/data}",
            "points_file": "daily_points.txt",
            "history_file": "kl8_history_final.txt",
            "mode": "read_only",
        },
        "upload_dir": "data/uploads",
        "seed_dir": "data/seed",
        "cache_dir": "data/cache",
        "state_dir": "data/state",
        "log_dir": "data/logs",
    },
    "fetch": {
        "enabled": True,
        "sources": ["cwl", "17500"],
        "timeout_sec": 10,
        "per_source_limit": 150,
        "backup_before_write": True,
    },
    "thresholds": {
        "norm_method": "rank",
        "signal_strong": 0.70,
        "signal_medium": 0.40,
        "contrarian_gate_z": 0.5,
        "contrarian_veto": 0.75,
        "adversarial_refute_max": 0.5,
        "cyclic_alpha": 0.05,
        "cyclic_correction": "bonferroni",
        "remainder_z_alert": 2.0,
        "entropy_low_quantile": 0.10,
        "alpha": 0.05,
        "fdr_method": "bh",
        "staleness_days_warn": 2,
        "staleness_days_critical": 4,
    },
    "scoring": {
        "weights": {"H1": 0.18, "H2": 0.18, "H3": 0.14, "H4": 0.14,
                    "H5": 0.12, "H6": 0.12, "H7": 0.12},
        "top_n": 5,
        "diversity_guard": True,
        "diversity_max_per_zone": 3,
    },
    "report": {"out_dir": "output", "defensive_picks": 2},
    "backtest": {"default_n": 60, "warmup_periods": 60,
                 "random_baseline_iters": 1000, "random_seed": 42},
    "online_learner": {
        "state_file": "data/state/online_learner_state.json",
        "algorithm": "exp3", "warmup_periods": 60,
        "gamma": 0.1, "weight_floor": 0.01,
    },
    "reproducibility": {"seed": 42},
}


def expand_env(value: Any) -> Any:
    """展开 `${VAR}` / `${VAR:-default}`。未设且无默认值时返回空串。"""
    if not isinstance(value, str):
        return value

    def _sub(m: re.Match) -> str:
        name, default = m.group(1), m.group(2)
        if name in os.environ and os.environ[name]:
            return os.environ[name]
        return default if default is not None else ""

    return ENV_PATTERN.sub(_sub, value)


class Section:
    """字典的属性访问包装，未知键返回 None 而非抛异常。"""

    def __init__(self, data: dict[str, Any]):
        self._data = data or {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._data:
            return None
        val = self._data[name]
        if isinstance(val, dict):
            return Section(val)
        if isinstance(val, list):
            return [Section(v) if isinstance(v, dict) else v for v in val]
        return val

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"Section({sorted(self._data)})"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    """全系统配置。各节通过属性访问。"""

    def __init__(self, raw: dict[str, Any], root: Path):
        self._raw = raw
        self.root = Path(root).resolve()
        self.data = Section(raw["data"])
        self.fetch = Section(raw["fetch"])
        self.thresholds = Section(raw["thresholds"])
        self.scoring = Section(raw["scoring"])
        self.report = Section(raw["report"])
        self.backtest = Section(raw["backtest"])
        self.online_learner = Section(raw["online_learner"])
        self.reproducibility = Section(raw["reproducibility"])
        self._file_overrides: dict[str, Path] = {}

    def override_files(self, points: str | None = None,
                       history: str | None = None) -> None:
        """§3.3：`--points/--history` 显式覆盖共享目录文件路径。"""
        if points:
            self._file_overrides["points"] = Path(expand_env(points)).resolve()
        if history:
            self._file_overrides["history"] = Path(expand_env(history)).resolve()

    # ── 路径解析 ──────────────────────────────────────────────
    def path(self, relative: str) -> Path:
        """把配置里的相对路径解析为项目根目录下的绝对路径。"""
        p = Path(expand_env(relative))
        return p if p.is_absolute() else (self.root / p).resolve()

    @property
    def shared_dir(self) -> Path:
        """共享数据目录（Python-Project/data）。"""
        return self.path(self.data.python_project.dir)

    @property
    def shared_points_file(self) -> Path:
        return (self._file_overrides.get("points")
                or self.shared_dir / self.data.python_project.points_file)

    @property
    def shared_history_file(self) -> Path:
        return (self._file_overrides.get("history")
                or self.shared_dir / self.data.python_project.history_file)

    @property
    def read_only(self) -> bool:
        return (self.data.python_project.mode or "read_only") != "read_write"

    @property
    def upload_dir(self) -> Path:
        return self.path(self.data.upload_dir)

    @property
    def seed_dir(self) -> Path:
        return self.path(self.data.seed_dir)

    @property
    def cache_dir(self) -> Path:
        return self.path(self.data.cache_dir)

    @property
    def state_dir(self) -> Path:
        return self.path(self.data.state_dir)

    @property
    def log_dir(self) -> Path:
        return self.path(self.data.log_dir)

    @property
    def out_dir(self) -> Path:
        return self.path(self.report.out_dir)

    @property
    def state_file(self) -> Path:
        return self.path(self.online_learner.state_file)

    @property
    def seed(self) -> int:
        return int(self.reproducibility.seed or 42)

    def ensure_dirs(self) -> None:
        for d in (self.upload_dir, self.seed_dir, self.cache_dir,
                  self.state_dir, self.log_dir, self.out_dir,
                  self.cache_dir / "backup"):
            d.mkdir(parents=True, exist_ok=True)

    def describe_paths(self) -> str:
        return (f"共享目录={self.shared_dir}\n"
                f"  点位文件={self.shared_points_file}\n"
                f"  开奖文件={self.shared_history_file}\n"
                f"  写入模式={'read_only' if self.read_only else 'read_write'}")


def load_config(path: str | os.PathLike | None = None,
                root: str | os.PathLike | None = None) -> Config:
    """加载并合并配置。未提供 path 时使用项目根目录下的 config.yaml。"""
    root_path = Path(root or Path(__file__).resolve().parent).resolve()
    cfg_path = Path(path) if path else root_path / "config.yaml"

    raw: dict[str, Any] = {}
    if cfg_path.exists():
        if yaml is None:
            raise RuntimeError("缺少 PyYAML，无法读取 config.yaml")
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    merged = _deep_merge(DEFAULTS, raw)
    cfg = Config(merged, root_path)
    cfg.ensure_dirs()
    return cfg
