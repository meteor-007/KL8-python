import sys
from pathlib import Path
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data_loader import DataLoader
from core.similarity_matcher import SimilarityMatcher
from core.density_detector import DensityDetector
from core.pattern_recognizer import PatternRecognizer
from core.curve_analyzer import CurveAnalyzer
from core.kill_predictor import KillPredictor
from config.model_config import ModelConfig

def run_backtest_with_weights(data_loader, config, weights, normalize_curve=False, use_adaptive=True):
    history = data_loader.history
    n_periods = 50
    results = []
    
    # Apply custom weights
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
            
            # If we want to test normalized curve distance
            if normalize_curve:
                # We monkeypatch the distance computation or manually adjust it
                pass
                
            detector = DensityDetector(config.density)
            density_result = detector.detect(sim_history[:60])
            
            recognizer = PatternRecognizer(config.pattern)
            pattern_result = recognizer.recognize(sim_history[0])
            
            analyzer = CurveAnalyzer(config.curve)
            curve_result = analyzer.analyze(sim_history)
            
            predictor = KillPredictor(config.kill, config.defense, history=sim_history)
            
            # Apply weights directly
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
            # print(f"Error at period {target_period}: {e}")
            continue
            
    if not results:
        return 0.0, 0.0, 0.0
        
    kill_rate = sum(r["kill_hit"] for r in results) / sum(r["kill_total"] for r in results)
    high_rate = sum(r["high_hit"] for r in results) / sum(r["high_total"] for r in results)
    mid_rate = sum(r["mid_hit"] for r in results) / sum(r["mid_total"] for r in results)
    return kill_rate, high_rate, mid_rate

def main():
    print("Loading data...")
    data_loader = DataLoader()
    data_loader.load()
    config = ModelConfig()
    
    # Test cases: (name, weights_dict)
    test_cases = [
        ("Baseline (Original)", {
            "similarity": 0.008,
            "density": 0.278,
            "pattern": 0.698,
            "curve": 0.016,
        }),
        ("Equal weights (no pattern)", {
            "similarity": 0.33,
            "density": 0.33,
            "pattern": 0.0,
            "curve": 0.34,
        }),
        ("Focus similarity + curve (no pattern)", {
            "similarity": 0.40,
            "density": 0.10,
            "pattern": 0.0,
            "curve": 0.50,
        }),
        ("Only similarity + curve (equal)", {
            "similarity": 0.50,
            "density": 0.0,
            "pattern": 0.0,
            "curve": 0.50,
        }),
        ("Only curve", {
            "similarity": 0.0,
            "density": 0.0,
            "pattern": 0.0,
            "curve": 1.0,
        }),
        ("Only similarity", {
            "similarity": 1.0,
            "density": 0.0,
            "pattern": 0.0,
            "curve": 0.0,
        }),
        ("Only density", {
            "similarity": 0.0,
            "density": 1.0,
            "pattern": 0.0,
            "curve": 0.0,
        })
    ]
    
    print("\n--- Running 50-period Backtests ---")
    for name, weights in test_cases:
        kr, hr, mr = run_backtest_with_weights(data_loader, config, weights)
        print(f"{name:<45} | Total Kill Hit: {kr:.2%} | High Conf Hit: {hr:.2%} | Mid Conf Hit: {mr:.2%}")

if __name__ == "__main__":
    main()
