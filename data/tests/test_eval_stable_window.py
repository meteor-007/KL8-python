# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.aggregation.stable_evaluator import top_freq_in_window, walk_forward_stable, is_lookahead_free

def test_top_freq():
    draws = [{1, 2, 3}, {2, 3, 4}, {3, 4, 5}]
    top = top_freq_in_window(draws, t=3, window=2, top_n=2)
    assert 3 in top and (2 in top or 4 in top)
    print('test_top_freq passed')

def test_walk_forward():
    draws = [{i for i in range(1, 21)} for _ in range(50)]
    res = walk_forward_stable(draws, window=10, top_n=5, min_history=20)
    assert res['n_periods'] == 30
    assert is_lookahead_free(25, 10, 50)
    print('test_walk_forward passed')

if __name__ == '__main__':
    test_top_freq()
    test_walk_forward()
    print('ALL AGGREGATION UNIT TESTS PASSED!')
