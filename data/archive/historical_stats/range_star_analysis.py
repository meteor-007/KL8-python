#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Range star analysis for 热码统计 Excel files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
DATE_START = 20260409
DATE_END = 20260506
WINDOWS = ("All", "S50", "S25", "S10")
SHORT_WINDOWS = ("S50", "S25", "S10")
FIXED_COLS = {
    "All": {"num": 0, "hits": 1, "rank": 2},
    "S50": {"num": 4, "hits": 5, "rank": 6},
    "S25": {"num": 8, "hits": 9, "rank": 10},
    "S10": {"num": 12, "hits": 13, "rank": 14},
}


@dataclass
class WindowMetric:
    rank: Optional[float]
    hits: Optional[float]


@dataclass
class FileResult:
    file_name: str
    true_star_set: Set[int]
    parsed: Dict[int, Dict[str, WindowMetric]]
    col_map: Dict[str, Dict[str, int]]
    pred_sets: Dict[str, Set[int]]
    metrics: Dict[str, Dict[str, float]]


def extract_date_from_name(file_name: str) -> Optional[int]:
    match = re.match(r"^(\d{8})-", file_name)
    return int(match.group(1)) if match else None


def list_target_files(base_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(base_dir.glob("*.xlsx")):
        dt = extract_date_from_name(p.name)
        if dt is not None and DATE_START <= dt <= DATE_END:
            files.append(p)
    return files


def clean_str(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and np.isnan(v):
        return ""
    return str(v).strip()


def parse_num_cell(v: object) -> Tuple[Optional[int], bool]:
    s = clean_str(v).replace(" ", "")
    if not s:
        return None, False
    has_star = "*" in s
    s = s.replace("*", "")
    m = re.search(r"(\d{1,2})", s)
    if not m:
        return None, has_star
    n = int(m.group(1))
    if 1 <= n <= 80:
        return n, has_star
    return None, has_star


def parse_float(v: object) -> Optional[float]:
    s = clean_str(v)
    if not s:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def header_blob(df: pd.DataFrame, col: int, rows: int = 4) -> str:
    parts = [clean_str(df.iat[r, col]).lower() for r in range(min(rows, len(df)))]
    return " ".join([x for x in parts if x])


def numeric_ratio(series: Sequence[object]) -> float:
    valid = 0
    total = 0
    for v in series:
        s = clean_str(v)
        if not s:
            continue
        total += 1
        if parse_float(s) is not None:
            valid += 1
    return 0.0 if total == 0 else valid / total


def detect_number_columns(df: pd.DataFrame) -> List[int]:
    candidates: List[int] = []
    n_rows = min(len(df), 120)
    for col in range(df.shape[1]):
        count = 0
        for r in range(n_rows):
            n, _ = parse_num_cell(df.iat[r, col])
            if n is not None:
                count += 1
        if count >= 60:
            candidates.append(col)
    return sorted(candidates)


def detect_by_header(df: pd.DataFrame, num_cols: List[int]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    alias = {
        "All": ("1943", "all", "全量", "总", "全部"),
        "S50": ("50", "50期"),
        "S25": ("25", "25期"),
        "S10": ("10", "10期"),
    }
    for w in WINDOWS:
        best_col = None
        best_score = -1
        for c in num_cols:
            text = header_blob(df, c)
            score = sum(1 for k in alias[w] if k in text)
            if score > best_score:
                best_score = score
                best_col = c
        if best_col is not None and best_score > 0:
            mapping[w] = best_col
    return mapping


def pick_hits_rank_cols(df: pd.DataFrame, num_col: int) -> Tuple[int, int]:
    cols = [c for c in range(max(0, num_col - 1), min(df.shape[1], num_col + 4)) if c != num_col]
    if not cols:
        return num_col + 1, num_col + 2

    rows = list(range(1, min(len(df), 90)))
    col_data = {c: [df.iat[r, c] for r in rows] for c in cols}
    rank_hint = {c: ("rank" in header_blob(df, c)) or ("排名" in header_blob(df, c)) for c in cols}
    hits_hint = {c: ("hits" in header_blob(df, c)) or ("命中" in header_blob(df, c)) or ("次数" in header_blob(df, c)) for c in cols}

    rank_scores: Dict[int, float] = {}
    hits_scores: Dict[int, float] = {}
    for c in cols:
        vals = [parse_float(v) for v in col_data[c]]
        nums = [v for v in vals if v is not None]
        if not nums:
            rank_scores[c] = -1.0
            hits_scores[c] = -1.0
            continue
        ratio = numeric_ratio(col_data[c])
        in_1_80 = sum(1 for v in nums if 1 <= v <= 80) / len(nums)
        mean_v = float(np.mean(nums))
        rank_scores[c] = ratio * 0.4 + in_1_80 * 0.6 + (0.2 if rank_hint[c] else 0.0)
        hits_scores[c] = ratio * 0.5 + (0.2 if mean_v > 2 else 0.0) + (0.3 if hits_hint[c] else 0.0)

    rank_col = max(rank_scores, key=rank_scores.get)
    left = {c: s for c, s in hits_scores.items() if c != rank_col}
    hits_col = max(left, key=left.get) if left else cols[0]
    if rank_col == hits_col:
        hits_col = num_col + 1 if (num_col + 1) < df.shape[1] else num_col
    return hits_col, rank_col


def build_column_map(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    num_cols = detect_number_columns(df)
    header_map = detect_by_header(df, num_cols)
    col_map: Dict[str, Dict[str, int]] = {}
    for w in WINDOWS:
        if w in header_map:
            num_col = header_map[w]
        else:
            num_col = FIXED_COLS[w]["num"] if FIXED_COLS[w]["num"] < df.shape[1] else min(df.shape[1] - 1, 0)
            if num_cols and num_col not in num_cols:
                idx = WINDOWS.index(w)
                if idx < len(num_cols):
                    num_col = num_cols[idx]
        hits_col, rank_col = pick_hits_rank_cols(df, num_col)
        if FIXED_COLS[w]["hits"] < df.shape[1]:
            if "hits" in header_blob(df, hits_col) or abs(hits_col - num_col) > 3:
                hits_col = FIXED_COLS[w]["hits"]
        if FIXED_COLS[w]["rank"] < df.shape[1]:
            if "rank" in header_blob(df, rank_col) or abs(rank_col - num_col) > 3:
                rank_col = FIXED_COLS[w]["rank"]
        col_map[w] = {"num": num_col, "hits": hits_col, "rank": rank_col}
    return col_map


def parse_file(path: Path) -> FileResult:
    df = pd.read_excel(path, sheet_name=0, header=None)
    col_map = build_column_map(df)
    parsed: Dict[int, Dict[str, WindowMetric]] = {}
    true_star_set: Set[int] = set()

    for r in range(len(df)):
        all_num_col = col_map["All"]["num"]
        n0, star0 = parse_num_cell(df.iat[r, all_num_col])
        if n0 is not None and star0:
            true_star_set.add(n0)

        for w in WINDOWS:
            c = col_map[w]["num"]
            n, _ = parse_num_cell(df.iat[r, c])
            if n is None:
                continue
            hits = parse_float(df.iat[r, col_map[w]["hits"]])
            rank = parse_float(df.iat[r, col_map[w]["rank"]])
            parsed.setdefault(n, {})[w] = WindowMetric(rank=rank, hits=hits)

    pred_sets = {
        "RuleA": predict_rule_a(parsed),
        "RuleB": predict_rule_b(parsed, require_hits=False),
        "RuleBPrime": predict_rule_b(parsed, require_hits=True),
        "WeightedTop20": predict_weighted(parsed, top_k=20),
        "WeightedTop25": predict_weighted(parsed, top_k=25),
    }
    metrics = {k: calc_metrics(v, true_star_set) for k, v in pred_sets.items()}
    return FileResult(path.name, true_star_set, parsed, col_map, pred_sets, metrics)


def get_metric(parsed: Dict[int, Dict[str, WindowMetric]], n: int, w: str) -> WindowMetric:
    return parsed.get(n, {}).get(w, WindowMetric(rank=None, hits=None))


def predict_rule_a(parsed: Dict[int, Dict[str, WindowMetric]]) -> Set[int]:
    out: Set[int] = set()
    for n in range(1, 81):
        all_rank = get_metric(parsed, n, "All").rank
        if all_rank is not None and all_rank <= 15:
            out.add(n)
            continue
        for w in SHORT_WINDOWS:
            m = get_metric(parsed, n, w)
            if m.rank is not None and m.rank <= 15 and (m.hits or 0) > 1:
                out.add(n)
                break
    return out


def predict_rule_b(parsed: Dict[int, Dict[str, WindowMetric]], require_hits: bool) -> Set[int]:
    out: Set[int] = set()
    for n in range(1, 81):
        all_rank = get_metric(parsed, n, "All").rank
        if all_rank is not None and all_rank <= 5:
            out.add(n)
            continue
        c = 0
        for w in SHORT_WINDOWS:
            m = get_metric(parsed, n, w)
            ok = m.rank is not None and m.rank <= 10
            if require_hits:
                ok = ok and (m.hits or 0) > 1
            if ok:
                c += 1
        if c >= 2:
            out.add(n)
    return out


def weighted_score(m_all: WindowMetric, m50: WindowMetric, m25: WindowMetric, m10: WindowMetric) -> float:
    def rank_score(rank: Optional[float], cut: int) -> float:
        if rank is None:
            return 0.0
        return max(0.0, float(cut + 1 - rank))

    def hit_val(h: Optional[float]) -> float:
        return 0.0 if h is None else float(h)

    short_rank = rank_score(m50.rank, 15) + rank_score(m25.rank, 15) + rank_score(m10.rank, 15)
    short_hits = hit_val(m50.hits) + hit_val(m25.hits) + hit_val(m10.hits)
    all_rank = rank_score(m_all.rank, 20)
    all_hits = hit_val(m_all.hits)
    short_top10 = sum(1 for m in (m50, m25, m10) if m.rank is not None and m.rank <= 10)
    return short_rank * 1.0 + short_hits * 0.25 + all_rank * 1.2 + all_hits * 0.08 + short_top10 * 3.0


def predict_weighted(parsed: Dict[int, Dict[str, WindowMetric]], top_k: int) -> Set[int]:
    scores: Dict[int, float] = {}
    for n in range(1, 81):
        scores[n] = weighted_score(
            get_metric(parsed, n, "All"),
            get_metric(parsed, n, "S50"),
            get_metric(parsed, n, "S25"),
            get_metric(parsed, n, "S10"),
        )
    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return {n for n, _ in ranked[:top_k]}


def calc_metrics(pred: Set[int], true_set: Set[int]) -> Dict[str, float]:
    tp = len(pred & true_set)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(true_set) if true_set else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"size": float(len(pred)), "precision": p, "recall": r, "f1": f1}


def avg(values: Iterable[float]) -> float:
    vals = list(values)
    return float(np.mean(vals)) if vals else 0.0


def grid_search(all_results: List[FileResult]) -> Dict[str, float]:
    best: Dict[str, float] = {"f1": -1.0}
    for a in range(3, 11):
        for s in range(6, 16):
            for b in (1, 2, 3):
                arr_p: List[float] = []
                arr_r: List[float] = []
                arr_f1: List[float] = []
                arr_size: List[float] = []
                for fr in all_results:
                    pred: Set[int] = set()
                    for n in range(1, 81):
                        if (get_metric(fr.parsed, n, "All").rank or 9999) <= a:
                            pred.add(n)
                            continue
                        c = 0
                        for w in SHORT_WINDOWS:
                            m = get_metric(fr.parsed, n, w)
                            if (m.rank or 9999) <= s and (m.hits or 0) > 1:
                                c += 1
                        if c >= b:
                            pred.add(n)
                    m = calc_metrics(pred, fr.true_star_set)
                    arr_p.append(m["precision"])
                    arr_r.append(m["recall"])
                    arr_f1.append(m["f1"])
                    arr_size.append(m["size"])

                cur = {
                    "A": float(a),
                    "S": float(s),
                    "B": float(b),
                    "precision": avg(arr_p),
                    "recall": avg(arr_r),
                    "f1": avg(arr_f1),
                    "size": avg(arr_size),
                }
                if (
                    cur["f1"] > best["f1"]
                    or (abs(cur["f1"] - best["f1"]) < 1e-12 and cur["precision"] > best.get("precision", -1.0))
                    or (
                        abs(cur["f1"] - best["f1"]) < 1e-12
                        and abs(cur["precision"] - best.get("precision", -1.0)) < 1e-12
                        and cur["size"] < best.get("size", 1e9)
                    )
                ):
                    best = cur
    return best


def print_metric_block(title: str, ms: Dict[str, Dict[str, float]]) -> None:
    m = ms[title]
    print(f"  {title:<13} avg_size={m['size']:.2f}, avg_P={m['precision']:.4f}, avg_R={m['recall']:.4f}, avg_F1={m['f1']:.4f}")


def main() -> None:
    files = list_target_files(BASE_DIR)
    print("=" * 90)
    print("Range Star Analysis (20260409~20260506)")
    print("=" * 90)
    print(f"[1] file count: {len(files)}")
    if len(files) != 28:
        print("WARNING: expected 28 files in date range.")

    all_results = [parse_file(p) for p in files]
    star_counts = [len(fr.true_star_set) for fr in all_results]
    print(
        f"[2] star count stats: mean={np.mean(star_counts):.4f}, min={np.min(star_counts)}, "
        f"max={np.max(star_counts)}, std={np.std(star_counts):.4f}"
    )

    metric_names = ["RuleA", "RuleB", "RuleBPrime", "WeightedTop20", "WeightedTop25"]
    agg: Dict[str, Dict[str, float]] = {}
    for name in metric_names:
        agg[name] = {
            "size": avg(fr.metrics[name]["size"] for fr in all_results),
            "precision": avg(fr.metrics[name]["precision"] for fr in all_results),
            "recall": avg(fr.metrics[name]["recall"] for fr in all_results),
            "f1": avg(fr.metrics[name]["f1"] for fr in all_results),
        }

    print("[3] Rule A: all.rank<=15 OR any short rank<=15 and hits>1")
    print_metric_block("RuleA", agg)
    print("[4] Rule B: all.rank<=5 OR >=2 short windows rank<=10")
    print_metric_block("RuleB", agg)
    print("[5] Rule B': Rule B with short windows hits>1")
    print_metric_block("RuleBPrime", agg)
    print("[6] weighted strategies")
    print_metric_block("WeightedTop20", agg)
    print_metric_block("WeightedTop25", agg)

    best = grid_search(all_results)
    print("[7] grid search (A=3..10, S=6..15, B in {1,2,3})")
    print(
        f"  best: A={int(best['A'])}, S={int(best['S'])}, B={int(best['B'])}, "
        f"avg_size={best['size']:.2f}, avg_P={best['precision']:.4f}, "
        f"avg_R={best['recall']:.4f}, avg_F1={best['f1']:.4f}"
    )

    print("\nSanity checks (first 3 files):")
    for i, fr in enumerate(all_results[:3], start=1):
        print("-" * 90)
        print(f"[Sanity-{i}] {fr.file_name}")
        print(f"  true_star_set({len(fr.true_star_set)}): {sorted(fr.true_star_set)}")
        print(f"  column_map: {fr.col_map}")
        show_nums = sorted(fr.true_star_set)[:20]
        print("  starred number metrics (num: All(rank,hits)|S50|S25|S10):")
        for n in show_nums:
            parts = []
            for w in WINDOWS:
                m = get_metric(fr.parsed, n, w)
                parts.append(f"{w}({m.rank},{m.hits})")
            print(f"    {n:>2}: " + " | ".join(parts))
        if len(fr.true_star_set) > len(show_nums):
            print(f"    ... truncated {len(fr.true_star_set) - len(show_nums)} numbers")

    print("\nDone.")


if __name__ == "__main__":
    main()
