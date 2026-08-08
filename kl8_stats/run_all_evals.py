# kl8_stats/run_all_evals.py
# -*- coding: utf-8 -*-
"""全系统置换检验：9 个子系统预测函数统一接入 kl8_stats.permutation.evaluate_lifts。

审计口径（快乐8 = 80 选 20，单号随机命中率 0.25）：
  - 每个子系统包一层 pred_fn(history_lines) -> list[int]，交给 evaluate_lifts。
  - 置换检验 200 次重排，seed=0 固定可复现。
  - Lift 带 95% Wilson CI 与经验 p 值；p>0.05 一律判「与随机不可区分」。
  - 无法独立运行的子系统（缺产物/依赖不可用）登记为文档化 skip 行，不伪造 p 值。

仅新增/修改本文件；不修改任何既有子系统代码。
"""
import argparse
import contextlib
import importlib.util
import io
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
DATA_FILE = BASE / "data" / "kl8_history_final.txt"

# rg 说明：本文件里的 _load_subsystem 用 importlib 路径加载中文/带连字符目录，
# 严禁对子目录用 `from X import Y`。


# ────────────────────────────────────────────────────────────────
# 通用工具
# ────────────────────────────────────────────────────────────────
def _raw_lines():
    """读取全部开奖文本行并转为时间升序（文件本身为最新在前）。"""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"开奖历史文件不存在: {DATA_FILE}")
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f if ln.strip()]
    return list(reversed(lines))


def _parse_line(ln):
    """解析单行 -> (period:int, date:str, numbers:list[int])。"""
    m = re.match(r"date:([^,]*),period:(\d+),numbers:([\d\-]+)", ln.strip())
    if not m:
        raise ValueError(f"无法解析开奖行: {ln[:80]}")
    return int(m.group(2)), m.group(1), [int(x) for x in m.group(3).split("-")]


@contextlib.contextmanager
def _quiet():
    """静音子系统 stdout/stderr 噪音（评估层不打印）。"""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        yield


def _load_subsystem(pkg_dir, module_path):
    """以 BASE/pkg_dir 为 sys.path[0] 加载 BASE/pkg_dir/module_path.py。

    module_path 形如 "main" 或 "core/data_loader"（相对 pkg_dir 的路径）。
    模块以唯一名 `<pkg_dir>::<module_path>` 注册，内部 `from config.paths import`
    等相对 pkg_dir 的导入经 sys.path 首部解析到本子系统，避免跨子系统
    config/core 包名冲突（评估结束后由 _teardown_subsystem 清理）。
    """
    abs_dir = str(BASE / pkg_dir)
    sys.path.insert(0, abs_dir)
    reg_name = f"{pkg_dir}::{module_path.replace('/', '.')}"
    spec = importlib.util.spec_from_file_location(
        reg_name, BASE / pkg_dir / f"{module_path}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[reg_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _teardown_subsystem(pkg_dir):
    """移除 pkg_dir 产生的 sys.path 条目与 sys.modules 内模块。

    必须连 `config`/`core` 等普通名模块一并移除，否则残留的
    KillSeeker.config 会劫持后续子系统的 `from config import ...`。
    评估层严格串行：任一时刻只有一个子系统的模块在 sys.modules 中。
    """
    abs_dir = str(BASE / pkg_dir)
    while abs_dir in sys.path:
        sys.path.remove(abs_dir)
    for name in [n for n in list(sys.modules)]:
        m = sys.modules.get(name)
        f = getattr(m, "__file__", None)
        if f and str(f).startswith(abs_dir):
            del sys.modules[name]


def _top_k(scores, k):
    """dict 号码->得分，取得分最高的 k 个号码（保序）。"""
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [n for n, _ in ranked[:k]]


def _eval_ctx(pkg_dir, module_name, draws, history_len, n_perm, seed, build_pred):
    """加载子系统 -> 构造 pred -> 跑置换；全程隔离，返回结果 dict。"""
    mod = _load_subsystem(pkg_dir, module_name)
    try:
        pred = build_pred(mod)
        from kl8_stats.permutation import evaluate_lifts

        r = evaluate_lifts(
            pred, draws, history_len=history_len, n_perm=n_perm, seed=seed
        )
        return r
    finally:
        _teardown_subsystem(pkg_dir)


# ────────────────────────────────────────────────────────────────
# 1. 顺口溜 — rule_engine.predict_next_period(records, rules)
# ────────────────────────────────────────────────────────────────
def _eval_shunkouliu(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        re_mod = _load_subsystem("顺口溜", "rule_engine")
        rules = re_mod.load_rules(BASE / "顺口溜" / "顺口溜_rules.txt")

        def pred(hist_lines):
            records = []
            for ln in hist_lines:
                period, date, nums = _parse_line(ln)
                records.append(re_mod.DrawRecord(date, period, frozenset(nums)))
            if not records:
                return []
            with _quiet():
                _, hits, scores = re_mod.predict_next_period(records, rules)
            if not scores:
                return []
            return _top_k(scores, 10)

        return pred

    return _eval_ctx(
        "顺口溜", "rule_engine", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 2. KillSeeker — main.run_kill_prediction(data_loader, config)
#    杀号系统输出 safe_numbers（保留号 Top8）作为预测号。
# ────────────────────────────────────────────────────────────────
def _eval_killseeker(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        main_mod = mod  # 已加载 KillSeeker/main.py
        loader_mod = _load_subsystem("KillSeeker", "core/data_loader")
        config_mod = _load_subsystem("KillSeeker", "config/model_config")
        # 评估期间禁止写生产日志
        main_mod.save_kill_prediction = lambda *a, **k: None
        main_mod.generate_detailed_report = lambda *a, **k: None

        def pred(hist_lines):
            draws_desc = []
            for ln in reversed(hist_lines):
                period, date, nums = _parse_line(ln)
                draws_desc.append(loader_mod.KL8Draw(date, str(period), nums))
            dl = loader_mod.DataLoader()
            dl._history = draws_desc
            dl._loaded = True
            cfg = config_mod.ModelConfig()
            with _quiet():
                out = main_mod.run_kill_prediction(dl, cfg, with_cross_feed=False)
            pred_obj = out.get("prediction")
            if not pred_obj:
                return []
            safe = list(pred_obj.safe_numbers)
            return safe or []

        return pred

    return _eval_ctx(
        "KillSeeker", "main", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 3. 点位期数-追踪 — tracking.reduce_points(...) 综合共振
#    预测点位 -> 展开为点位覆盖号 {p-1, p, p+1}（点位语义=区域开出）。
# ────────────────────────────────────────────────────────────────
def _eval_point_tracking(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        tracking = mod  # 已加载 tracking.py
        point_map = _load_subsystem("点位期数-追踪", "point_map")

        def pred(hist_lines):
            records = []
            for ln in hist_lines:
                period, date, nums = _parse_line(ln)
                records.append({"period": period, "numbers": nums})
            ps = point_map.build_point_status(records)
            if not ps:
                return []
            T = max(ps) + 1
            R = T - 1
            try:
                with _quiet():
                    ge = {}
                    for gap in (1, 2, 3, 4):
                        cand, _, _ = tracking.gap_tracking(ps, T, gap)
                        ge[f"隔{gap}期"] = cand
                    legacy, _ = tracking.legacy_tracking(ps, T, R)
                    stats, _ = tracking.omission_stats(ps, T)
                    repeat, _ = tracking.repeat_candidates(ps, T, stats)
                    _, _, summary = tracking.reduce_points(
                        ps, T, ge, repeat, stats, legacy_rows=legacy
                    )
                pool = summary.get("eval_pool") or []
                covers = set()
                for p in pool[:10]:
                    covers.update(point_map.point_covers(p))
                return sorted(covers) or []
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "点位期数-追踪", "tracking", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 4. 双层LSTM — core.predictor.Predictor.load_model().predict()
#    模型加载一次（懒加载），逐窗口推理。
# ────────────────────────────────────────────────────────────────
_LSTM_PREDICTOR = None


def _eval_lstm(draws, history_len=60, n_perm=200, seed=0):
    global _LSTM_PREDICTOR

    def build(mod):
        predictor_mod = mod  # 已加载 core/predictor.py

        def get_predictor():
            global _LSTM_PREDICTOR
            if _LSTM_PREDICTOR is None:
                with _quiet():
                    p = predictor_mod.Predictor()
                    p.load_model()
                    _LSTM_PREDICTOR = p
            return _LSTM_PREDICTOR

        def pred(hist_lines):
            draws_numbers = []
            for ln in hist_lines:
                _, _, nums = _parse_line(ln)
                draws_numbers.append(nums)
            if len(draws_numbers) < 30:
                return []
            try:
                with _quiet():
                    p = get_predictor()
                    prob_num, prob_zone, prob_tail = p.predict(draws_numbers)
                    top10, _, _, _, _ = p.analyze_fusion(prob_num, prob_zone, prob_tail)
                return list(top10)
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "双层LSTM", "core/predictor", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 5. 定金选2 — ReverseTrendEngine.run_daily_pipeline 双金胆配对
#    预测=推荐组合（combo "n1-n2"）号码并集。
# ────────────────────────────────────────────────────────────────
def _eval_dingjin(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        engine_mod = mod  # 已加载 model_engine.py
        scoring_mod = _load_subsystem("定金选2-分析", "config/scoring_config")
        paths_mod = _load_subsystem("定金选2-分析", "config/paths")

        def pred(hist_lines):
            history = {}
            for ln in hist_lines:
                period, _, nums = _parse_line(ln)
                history[str(period)] = nums
            if not history:
                return []
            latest = max(history, key=int)
            T = max(int(p) for p in history) + 1
            try:
                with _quiet():
                    cfg = scoring_mod.ScoringConfig(
                        param_store_path=paths_mod.PARAM_STORE_FILE
                    )
                    engine = engine_mod.ReverseTrendEngine(
                        history_data=history,
                        config=cfg,
                        persist_recent_dans=False,
                    )
                    res = engine.run_daily_pipeline(
                        latest_period=latest,
                        target_dan=None,
                        hot_trends=[],
                        next_period=str(T),
                    )
                if "status" in res and "Aborted" in res["status"]:
                    return []
                nums = set()
                for rec in res.get("recommendations", []):
                    for part in rec.get("combo", "").split("-"):
                        if part.isdigit():
                            nums.add(int(part))
                return sorted(nums) or []
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "定金选2-分析", "model_engine", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 6. gemini选2-预测 — k8_quant_engine.score_numbers (纯离线统计算子)
# ────────────────────────────────────────────────────────────────
def _eval_gemini(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        eng = mod  # 已加载 k8_quant_engine.py

        def pred(hist_lines):
            rows = []
            for ln in reversed(hist_lines):  # 引擎要求 history[0]=最新
                period, date, nums = _parse_line(ln)
                rows.append(eng.Draw(date, period, nums))
            try:
                with _quiet():
                    report = eng.scan_anomalies(rows)
                    scores, _ = eng.score_numbers(rows, report, mode="algo1")
                return _top_k(scores, 10)
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "gemini选2-预测", "k8_quant_engine", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 7. data — core.feature_optimizer.get_all_layer_a_scores
#    严格未来隔离：history_only=True + is_future=False。
# ────────────────────────────────────────────────────────────────
def _eval_data(draws, history_len=60, n_perm=200, seed=0):
    def build(mod):
        fo = mod  # 已加载 feature_optimizer.py

        def pred(hist_lines):
            hist = []
            for ln in hist_lines:
                period, date, nums = _parse_line(ln)
                hist.append(
                    {
                        "issue": str(period),
                        "date": date,
                        "numbers": nums,
                        "draw_order": list(nums),
                    }
                )
            hist.sort(key=lambda h: h["issue"], reverse=True)  # 最新在前
            try:
                with _quiet():
                    scores = fo.get_all_layer_a_scores(
                        history=hist, history_only=True, is_future=False
                    )
                return _top_k(scores, 10)
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "data", "core/feature_optimizer", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 8. 重点点位 — model_engine.train_and_predict + 下游精排/推荐
#    需 daily_points.txt 提供点位；目标期 T 必须有点位，否则跳过。
# ────────────────────────────────────────────────────────────────
_ZD_POINTS_DF = None


def _eval_zdpoint(draws, history_len=60, n_perm=200, seed=0):
    global _ZD_POINTS_DF

    def build(mod):
        me_mod = mod  # 已加载 model_engine.py
        dl_mod = _load_subsystem("重点点位分析", "data_loader")
        fe_mod = sys.modules.get("feature_engineering") or _load_subsystem(
            "重点点位分析", "feature_engineering"
        )
        build_dataset = fe_mod.build_dataset

        def get_points():
            global _ZD_POINTS_DF
            if _ZD_POINTS_DF is None:
                with _quiet():
                    _ZD_POINTS_DF = dl_mod.parse_daily_points(
                        BASE / "data" / "daily_points.txt"
                    )
            return _ZD_POINTS_DF

        def pred(hist_lines):
            periods, nums_rows = [], []
            for ln in hist_lines:
                period, _, nums = _parse_line(ln)
                periods.append(period)
                nums_rows.append({"period": period, "winning_numbers": nums})
            T = periods[-1] + 1
            pts = get_points()
            if not ((pts["period"] == T).any()):
                return []  # 目标期无点位，与生产无法对齐，跳过
            try:
                with _quiet():
                    import pandas as pd

                    points_df = pts[pts["period"] <= T].copy()
                    history_df = pd.DataFrame(nums_rows)
                    merged = dl_mod.merge_and_align_data(history_df, points_df)
                    merged, candidate_pool, target_period = (
                        dl_mod.build_prediction_pool(merged)
                    )
                    train_df, predict_df = build_dataset(
                        merged, max_train_periods=150
                    )
                    if len(predict_df) == 0:
                        return []
                    raw_predict_df, wf = me_mod.train_and_predict(
                        train_df, predict_df
                    )
                    corrected_df, level = (
                        me_mod.apply_multiple_testing_correction(raw_predict_df)
                    )
                    final_predict_df = me_mod.apply_tanh_damper(corrected_df, level)
                    final_predict_df = me_mod.rank_numbers_in_zones(
                        final_predict_df, merged
                    )
                    base_points = merged[merged["period"] == T]["base_points"].iloc[0]
                    recs = me_mod.generate_recommendations(
                        final_predict_df,
                        level,
                        base_points,
                        reverse_coverage_max_period=T,
                    )
                pred_pts = []
                for r in recs:
                    p = r.get("point")
                    if p:
                        pred_pts.append(int(p))
                return list(dict.fromkeys(pred_pts)) or []
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "重点点位分析", "model_engine", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 9. 聚合 — aggregate_predictions.ZoneDeepAggregator.aggregate_period
#    聚合其他子系统生产预测记录；目标期无记录则跳过（无预测）。
# ────────────────────────────────────────────────────────────────
_AGG_CTX = None


def _eval_aggregate(draws, history_len=60, n_perm=200, seed=0):
    global _AGG_CTX

    def build(mod):
        agg_mod = mod  # 已加载 aggregate_predictions.py

        def get_ctx():
            global _AGG_CTX
            if _AGG_CTX is None:
                with _quiet():
                    history = agg_mod.load_history()
                    collector = agg_mod.UnifiedDataCollector(
                        date_period_map=agg_mod.build_date_period_map()
                    )
                    collector.collect_all()
                    _AGG_CTX = (collector, history)
            return _AGG_CTX

        def pred(hist_lines):
            periods = [_parse_line(ln)[0] for ln in hist_lines]
            T = str(periods[-1] + 1)
            try:
                collector, history = get_ctx()
                if not collector.get_records_by_period(T):
                    return []  # 目标期无生产预测记录，聚合无输入
                with _quiet():
                    # 严格未来隔离：为每个目标期 T 重建分析器，仅用 ≤T 的记录与开奖。
                    # StableHitAnalyzer 的"近期窗口"取 self.all_periods 中最新 20 期；
                    # 若用全量索引，对过去的 T 会取到 T 之后的未来期（开奖泄漏）。
                    # 故按 T 过滤记录与 history，使稳定命中特征只基于 ≤T-1 数据。
                    records_le = [
                        r for r in collector.get_deduped_records() if r.period <= T
                    ]
                    history_le = {p: s for p, s in history.items() if p <= T}

                    class _LeCollector:
                        def get_deduped_records(self):
                            return records_le

                        def get_all_periods(self):
                            return {r.period for r in records_le}

                        def get_records_by_period(self, period):
                            return [r for r in records_le if r.period == period]

                    analyzer_le = agg_mod.StableHitAnalyzer(
                        _LeCollector(), history_le, window=20
                    )
                    aggregator_le = agg_mod.ZoneDeepAggregator(
                        _LeCollector(), analyzer_le, history_le
                    )
                    res = aggregator_le.aggregate_period(T)
                return [c["num"] for c in res.get("global_elite_12", [])] or []
            except Exception:
                return []

        return pred

    return _eval_ctx(
        "数据汇总复盘", "aggregate_predictions", draws, history_len, n_perm, seed, build
    )


# ────────────────────────────────────────────────────────────────
# 报告渲染
# ────────────────────────────────────────────────────────────────
def _wilson_lift_ci(hits, n, mean_hits):
    """在「单号码命中率」上取 Wilson 95% CI，再换算到 Lift 标度。

    每次预测的每个号码是一次伯努利试验：总试验数 = 总预测号码数
    = mean_hits / 0.25（mean_hits = 总预测号数 × 20/80）。基线命中率 0.25。
    """
    from kl8_stats.ci import wilson_ci

    if n == 0 or mean_hits <= 0:
        return (0.0, 0.0)
    trials = mean_hits / 0.25  # 总预测号码数
    lo, hi = wilson_ci(int(round(hits)), int(round(trials)))
    return (lo / 0.25, hi / 0.25)


def _fmt_ci(ci):
    """格式化 95%CI 为 `lo~hi`。ci 恒为 (lo, hi) 二元组。"""
    return f"{ci[0]:.2f}~{ci[1]:.2f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description="全系统置换检验")
    ap.add_argument("--only", default=None, help="只跑某个子系统便于调试")
    ap.add_argument("--nperm", type=int, default=200, help="置换次数")
    ap.add_argument("--history-len", type=int, default=60, help="历史窗口长度")
    ap.add_argument("--draws", type=int, default=0, help="仅用最近 N 行(0=全部)")
    args = ap.parse_args(argv)

    n_perm = args.nperm
    history_len = args.history_len
    # --only 只过滤子系统；置换次数始终尊重 --nperm（调试时用 --nperm 5 快速探针）
    N = n_perm

    draws = _raw_lines()
    if args.draws:
        draws = draws[-args.draws:]

    entries = [
        ("顺口溜", _eval_shunkouliu, "规则引擎 Top10 加权得分", None,
         "命中优势集中于 2023-24 单时段（其余时段≈基线），"
         "疑为规则针对该时段样本内调参；且 9 系统多重比较下偶发显著属正常波动，不构成可证伪信号"),
        ("KillSeeker", _eval_killseeker, "保留号 Top8（杀号系统反向）", 360, None),
        ("点位期数-追踪", _eval_point_tracking, "多路共振点位展开覆盖号", None, None),
        ("双层LSTM", _eval_lstm, "双LSTM 融合 Top10（仅最新15%校验段）", 304,
         "预测集近似恒定（采样 35 期仅 4 种不同 Top10），置换检验功效有限"),
        ("定金选2-分析", _eval_dingjin, "双金胆推荐组合并集", 300, None),
        ("gemini选2-预测", _eval_gemini, "score_numbers(algo1) Top10", None, None),
        ("data", _eval_data, "layerA 6维规则+深度方案 Top10", 400, None),
        ("重点点位分析", _eval_zdpoint, "Stacking 区域预测→推荐点位", 80, None),
        ("聚合", _eval_aggregate, "全局共识聚合 Elite12（生产记录）", 120, None),
    ]

    rows = []
    for name, fn, note, slice_n, low_p_caveat in entries:
        if args.only and args.only not in name:
            continue
        d = draws if slice_n is None else draws[-slice_n:]
        t0 = datetime.now()
        try:
            r = fn(d, history_len=history_len, n_perm=N, seed=0)
            n = r.get("n", 0)
            hits = r.get("hits", 0)
            lift = r.get("lift")
            p = r.get("p_value")
            mean_hits = r.get("mean_hits", 0)
            ci = _wilson_lift_ci(hits, n, mean_hits)
            if p is None:
                verdict = "待补置换检验"
            elif p < 0.05:
                if low_p_caveat:
                    verdict = f"名义 p<0.05，但{low_p_caveat}"
                else:
                    verdict = "**超越随机**" if lift and lift > 1 else "显著但方向存疑"
            else:
                verdict = "与随机不可区分"
            rows.append(
                {
                    "name": name, "lift": lift, "ci": ci, "p": p,
                    "n": n, "hits": hits, "mean_hits": mean_hits,
                    "verdict": verdict, "note": note, "ok": True,
                }
            )
        except Exception as e:
            rows.append(
                {
                    "name": name, "lift": None, "ci": (0, 0), "p": None,
                    "n": 0, "hits": 0, "mean_hits": 0,
                    "verdict": f"跳过：{e.__class__.__name__}: {e}",
                    "note": note, "ok": False, "caveat": low_p_caveat,
                }
            )
        dt = (datetime.now() - t0).total_seconds()
        rows[-1]["runtime"] = dt
        if rows[-1]["ok"]:
            rows[-1]["caveat"] = low_p_caveat

    _render_report(rows, args)


def _render_report(rows, args):
    out = []
    out.append("═" * 78)
    out.append("  快乐8 信号审计报告 | 全系统置换检验 | 生成 %s"
               % datetime.now().strftime("%Y-%m-%d %H:%M"))
    out.append("═" * 78)
    out.append("基线：随机 Top-k 期望命中 = k×20/80；Lift=1.0 即随机。")
    out.append("方法：walk-forward 每期用 ≤T-1 历史预测 T 期，200 次重排求经验 p 值。")
    out.append("口径：Lift 带 95% Wilson CI；p>0.05 → 与随机不可区分。")
    out.append("")
    out.append("| 子系统 | Lift | 95%CI | p值 | 期数 | 命中 | 结论 |")
    out.append("|---|---:|---:|---:|---:|---:|---|")
    for r in rows:
        if r["ok"]:
            out.append(
                "| {name} | {lift:.2f} | {ci} | {p:.3f} | {n} | {hits} | {verdict} |"
                .format(name=r["name"], lift=r["lift"], ci=_fmt_ci(r["ci"]),
                        p=r["p"], n=r["n"], hits=r["hits"], verdict=r["verdict"])
            )
        else:
            out.append(f"| {r['name']} | 跳过 | — | — | — | — | {r['verdict']} |")
    out.append("")
    out.append("### 运行详情")
    for r in rows:
        if r["ok"]:
            extra = f" | 备注：{r['caveat']}" if r["caveat"] else ""
            out.append(
                f"- **{r['name']}**：{r['note']} | 期数={r['n']} 命中={r['hits']} "
                f"期望={r['mean_hits']:.1f} | 用时={r['runtime']:.1f}s{extra}"
            )
        else:
            out.append(f"- **{r['name']}**：{r['note']} | {r['verdict']}")
    content = "\n".join(out) + "\n"
    print(content)
    today = datetime.now().strftime("%Y%m%d")
    dest = BASE / "数据汇总复盘" / f"信号审计报告_{today}.md"
    dest.write_text(content, encoding="utf-8")
    print(f"▶ 已保存: {dest}")


if __name__ == "__main__":
    main()