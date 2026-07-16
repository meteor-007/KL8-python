import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.road_mapper import road_of, numbers_of_road, all_roads, road_vector


def test_sizes():
    assert len(numbers_of_road(0)) == 26
    assert len(numbers_of_road(1)) == 27
    assert len(numbers_of_road(2)) == 27
    assert set(range(1, 81)) == set(all_roads().keys())


def test_road_of():
    assert road_of(3) == 0
    assert road_of(1) == 1
    assert road_of(2) == 2
    assert road_of(80) == 2


def test_road_vector_sums_20():
    nums = list(range(1, 21))
    r0, r1, r2 = road_vector(nums)
    assert r0 + r1 + r2 == 20
