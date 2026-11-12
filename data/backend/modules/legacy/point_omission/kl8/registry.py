# -*- coding: utf-8 -*-
"""方法注册表与调度。

把 13 个模块的加载、调用顺序与异常隔离集中在这里，
replay / main 共用同一套调度，保证回测与实盘走完全相同的代码路径。
"""
from __future__ import annotations

from typing import Callable

from .contracts import ModuleResult
from .data_io import Draw
from .ensemble import MAIN_METHODS
from .points import NumberStats
from . import observability

# 模块名 → (模块路径, 函数名)
MAIN_MODULES: dict[str, tuple[str, str]] = {
    "cluster":     ("kl8.cluster", "analyze"),
    "cyclic":      ("kl8.cyclic", "analyze"),
    "heatmap":     ("kl8.heatmap", "analyze"),
    "markov":      ("kl8.markov", "analyze"),
    "fibonacci":   ("kl8.fibonacci", "analyze"),
    "linalg_svd":  ("kl8.linalg_svd", "analyze"),
    "complex_fft": ("kl8.complex_fft", "analyze"),
    "graph_net":   ("kl8.graph_net", "analyze"),
    "volatility":  ("kl8.volatility", "analyze"),
    "remainder":   ("kl8.remainder", "analyze"),
    "entropy":     ("kl8.entropy", "analyze"),
}

META_MODULES: dict[str, tuple[str, str]] = {
    "contrarian":  ("kl8.contrarian", "analyze_contrarian"),
    "adversarial": ("kl8.adversarial", "gate"),
}


def load_analyzer(name: str) -> Callable | None:
    """按名加载模块函数。加载失败返回 None（并在日志中告警）。"""
    spec = MAIN_MODULES.get(name)
    if spec is None:
        return None
    import importlib
    try:
        mod = importlib.import_module(spec[0])
        return getattr(mod, spec[1])
    except (ImportError, AttributeError) as exc:
        observability.warn(f"加载方法 {name} 失败: {exc}")
        return None


def load_meta(name: str) -> Callable | None:
    spec = META_MODULES.get(name)
    if spec is None:
        return None
    import importlib
    try:
        return getattr(importlib.import_module(spec[0]), spec[1])
    except (ImportError, AttributeError) as exc:
        observability.warn(f"加载元模块 {name} 失败: {exc}")
        return None


def _safe_call(name: str, fn: Callable, *args) -> ModuleResult:
    """调用单个模块，异常隔离为 sufficient=False 的空结果。"""
    try:
        res = fn(*args)
    except Exception as exc:                       # 单模块失败不拖垮整条流水线
        observability.warn(f"方法 {name} 执行异常: {exc!r}")
        res = ModuleResult(name=name, scores={})
        res.degrade(f"执行异常: {exc}")
        return res
    if not isinstance(res, ModuleResult):
        observability.warn(f"方法 {name} 返回类型错误: {type(res).__name__}")
        bad = ModuleResult(name=name, scores={})
        bad.degrade("返回类型不符合契约")
        return bad
    res.name = name
    return res


def run_all(draws: list[Draw],
            expanded_set: set[int],
            base_stats: dict[int, NumberStats],
            cfg,
            names: list[str] | None = None,
            run_meta: bool = True) -> tuple[dict[str, ModuleResult], dict[int, float]]:
    """执行全部方法。返回 (结果字典, omission_z_rebound)。

    omission 先跑（contrarian 与 §5.4 备防码都依赖它）；
    11 个主分方法各自独立；contrarian 消费前两者的输出。
    """
    from .omission import analyze_omission

    want = list(names) if names else list(MAIN_METHODS)
    results: dict[str, ModuleResult] = {}

    # ① 底座：遗漏。无条件执行——H2、contrarian 与 §5.4 备防码都依赖它。
    try:
        omission_res, z_rebound = analyze_omission(draws, expanded_set,
                                                   base_stats, cfg)
    except Exception as exc:
        observability.warn(f"遗漏分析异常: {exc!r}")
        omission_res = ModuleResult(name="omission", scores={})
        omission_res.degrade(f"执行异常: {exc}")
        z_rebound = {n: 0.0 for n in range(1, 81)}

    results["omission"] = omission_res

    # ② 11 个主分方法（omission 不在 MAIN_METHODS 内，单独处理）
    for name in want:
        if name == "omission":
            continue
        fn = load_analyzer(name)
        if fn is None:
            miss = ModuleResult(name=name, scores={})
            miss.degrade("模块未实现或加载失败")
            results[name] = miss
            continue
        results[name] = _safe_call(name, fn, draws, expanded_set, base_stats, cfg)

    # ③ 元模块：反向博弈（不进主分）
    if run_meta:
        fn = load_meta("contrarian")
        if fn is not None:
            try:
                results["contrarian"] = fn(results, omission_res, cfg,
                                           z_rebound, base_stats, expanded_set)
                if not isinstance(results["contrarian"], ModuleResult):
                    raise TypeError("contrarian 返回类型错误")
            except Exception as exc:
                observability.warn(f"contrarian 异常: {exc!r}")
                c = ModuleResult(name="contrarian", scores={})
                c.degrade(f"执行异常: {exc}")
                results["contrarian"] = c

    return results, z_rebound
