import sys
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data_loader import DataLoader
from core.similarity_matcher import SimilarityMatcher
from core.density_detector import DensityDetector
from core.pattern_recognizer import PatternRecognizer
from core.curve_analyzer import CurveAnalyzer
from core.kill_predictor import KillPredictor
from config.model_config import ModelConfig

# Monkeypatch SimilarityMatcher to support optional normalization
def patch_similarity_matcher(normalize):
    if normalize:
        def _compute_multi_dimension_distance(self, current, historical):
            distances = {}
            # number_overlap
            current_nums = set()
            hist_nums = set()
            for d in current:
                current_nums |= d.number_set
            for d in historical:
                hist_nums |= d.number_set
            intersection = current_nums & hist_nums
            union = current_nums | hist_nums
            distances["number_overlap"] = 1.0 - len(intersection) / max(len(union), 1)

            # zone_distribution
            current_zones = np.array([d.zone_counts for d in current]).sum(axis=0).astype(float)
            hist_zones = np.array([d.zone_counts for d in historical]).sum(axis=0).astype(float)
            norm_c = np.linalg.norm(current_zones)
            norm_h = np.linalg.norm(hist_zones)
            if norm_c > 0 and norm_h > 0:
                distances["zone_distribution"] = float(1.0 - np.dot(current_zones, hist_zones) / (norm_c * norm_h))
            else:
                distances["zone_distribution"] = 1.0

            # trend_curve (Normalized!)
            current_sums = np.array([d.sum_value for d in current], dtype=float)
            hist_sums = np.array([d.sum_value for d in historical], dtype=float)
            # Max difference of single sum is ~1200, but typical is 200. Let's normalize by 300 * sqrt(L)
            max_diff = 300.0 * np.sqrt(len(current))
            distances["trend_curve"] = float(np.linalg.norm(current_sums - hist_sums) / max_diff)

            # matrix_shape
            current_matrix = sum(d.matrix_8x10 for d in current)
            hist_matrix = sum(d.matrix_8x10 for d in historical)
            current_matrix = current_matrix / max(current_matrix.max(), 1)
            hist_matrix = hist_matrix / max(hist_matrix.max(), 1)
            distances["matrix_shape"] = float(np.mean((current_matrix - hist_matrix) ** 2))

            return distances
        SimilarityMatcher._compute_multi_dimension_distance = _compute_multi_dimension_distance
    else:
        # Restore original
        def _compute_multi_dimension_distance(self, current, historical):
            distances = {}
            current_nums = set()
            hist_nums = set()
            for d in current:
                current_nums |= d.number_set
            for d in historical:
                hist_nums |= d.number_set
            intersection = current_nums & hist_nums
            union = current_nums | hist_nums
            distances["number_overlap"] = 1.0 - len(intersection) / max(len(union), 1)

            current_zones = np.array([d.zone_counts for d in current]).sum(axis=0).astype(float)
            hist_zones = np.array([d.zone_counts for d in historical]).sum(axis=0).astype(float)
            norm_c = np.linalg.norm(current_zones)
            norm_h = np.linalg.norm(hist_zones)
            if norm_c > 0 and norm_h > 0:
                distances["zone_distribution"] = float(1.0 - np.dot(current_zones, hist_zones) / (norm_c * norm_h))
            else:
                distances["zone_distribution"] = 1.0

            current_sums = np.array([d.sum_value for d in current], dtype=float)
            hist_sums = np.array([d.sum_value for d in historical], dtype=float)
            distances["trend_curve"] = float(np.linalg.norm(current_sums - hist_sums))

            current_matrix = sum(d.matrix_8x10 for d in current)
            hist_matrix = sum(d.matrix_8x10 for d in historical)
            current_matrix = current_matrix / max(current_matrix.max(), 1)
            hist_matrix = hist_matrix / max(hist_matrix.max(), 1)
            distances["matrix_shape"] = float(np.mean((current_matrix - hist_matrix) ** 2))

            return distances
        SimilarityMatcher._compute_multi_dimension_distance = _compute_multi_dimension_distance

def run_backtest_with_weights(data_loader, config, weights, n_periods=30):
    history = data_loader.history
    results = []
    
    config.kill.engine_weights = weights
    
    for i in range(n_periods):
        sim_history = history[i:]
        if len(sim_history) < 60:
            break
            
        target_period = str(int(sim_history[0].period) + 1)
        actual_set = None
        for draw in history:
            if draw.period == target_period:
                actual_set = draw.number_set
                break
        if not actual_set:
            continue
            
        try:
            recent = sim_history[:10]
            matcher = SimilarityMatcher(config.similarity)
            sim_result = matcher.find_similar(recent, sim_history)
            
            detector = DensityDetector(config.density)
            density_result = detector.detect(sim_history[:60])
            
            recognizer = PatternRecognizer(config.pattern)
            pattern_result = recognizer.recognize(sim_history[0])
            
            analyzer = CurveAnalyzer(config.curve)
            curve_result = analyzer.analyze(sim_history)
            
            predictor = KillPredictor(config.kill, config.defense, history=sim_history)
            predictor.weights = dict(weights)
            
            prediction = predictor.predict(
                period=target_period,
                sim_result=sim_result,
                density_result=density_result,
                pattern_result=pattern_result,
                curve_result=curve_result,
                history=sim_history,
            )
            
            all_kills = set(prediction.all_kills)
            high_kills = set(prediction.high_conf_kills)
            mid_kills = set(prediction.mid_conf_kills)
            
            kill_hit = len(all_kills - actual_set)
            high_hit = len(high_kills - actual_set)
            mid_hit = len(mid_kills - actual_set)
            
            results.append({
                "kill_hit": kill_hit,
                "kill_total": len(all_kills),
                "high_hit": high_hit,
                "high_total": len(high_kills),
                "mid_hit": mid_hit,
                "mid_total": len(mid_kills),
            })
        except Exception as e:
            continue
            
    if not results:
        return 0.0, 0.0, 0.0
        
    kill_rate = sum(r["kill_hit"] for r in results) / sum(r["kill_total"] for r in results)
    high_rate = sum(r["high_hit"] for r in results) / sum(r["high_total"] for r in results)
    mid_rate = sum(r["mid_hit"] for r in results) / sum(r["mid_total"] for r in results)
    return kill_rate, high_rate, mid_rate

def main():
    print("Loading data...", flush=True)
    data_loader = DataLoader()
    data_loader.load()
    config = ModelConfig()
    
    weights = {
        "similarity": 0.30,
        "density": 0.30,
        "pattern": 0.0,
        "curve": 0.40,
    }
    
    print("\n--- Running 30-period Normalization Backtests ---", flush=True)
    
    # 1. No norm change (Original trend_curve distance)
    patch_similarity_matcher(normalize=False)
    kr1, hr1, mr1 = run_backtest_with_weights(data_loader, config, weights, n_periods=30)
    print(f"Option A (Original distance)    | Total Kill Hit: {kr1:.2%} | High Conf Hit: {hr1:.2%} | Mid Conf Hit: {mr1:.2%}", flush=True)
    
    # 2. Normalized trend_curve distance
    patch_similarity_matcher(normalize=True)
    kr2, hr2, mr2 = run_backtest_with_weights(data_loader, config, weights, n_periods=30)
    print(f"Option A (Normalized distance)  | Total Kill Hit: {kr2:.2%} | High Conf Hit: {hr2:.2%} | Mid Conf Hit: {mr2:.2%}", flush=True)

if __name__ == "__main__":
    main()
