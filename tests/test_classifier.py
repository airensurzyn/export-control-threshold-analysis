"""
Regression + unit tests for the export-control classifier.

Run:  pytest            (from the repo root)
      pytest -v         (verbose, one line per case)

Covers three layers:
  1. The TPP / performance-density math on hand-computed values (pure unit tests).
  2. The dataset: every ground-truth chip classifies as expected under the 2023 rule.
  3. Rule vintages: the A800/H800 loophole closes, B200 breaches the 2026 ceiling, etc.
"""

import os
import sys

import pytest

# make the repo root importable whether pytest is run from root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tpp_calculator import Chip                       # noqa: E402
from load_chips import load_chips, GROUND_TRUTH       # noqa: E402
from rules import classify_2022, classify_2023, classify_2026_cn  # noqa: E402


# ---------------------------------------------------------------------------
# 1. Pure math: TPP and performance density
# ---------------------------------------------------------------------------

def test_tpp_takes_max_over_precisions():
    # 8-bit at 624 -> 4992 should beat 16-bit at 312 -> 4992 (tie) and 32-bit lower
    c = Chip("t", {32: 19.5, 16: 312, 8: 624}, die_area_mm2=None)
    assert c.tpp() == pytest.approx(4992)


def test_tpp_single_precision():
    c = Chip("t", {8: 1979}, die_area_mm2=None)
    assert c.tpp() == pytest.approx(15832)


def test_fp4_can_set_the_max():
    # Blackwell-style: 4-bit at 9000 -> 36000 beats 8-bit at 4500 -> 36000 (tie),
    # and must be considered at all.
    c = Chip("t", {16: 2250, 8: 4500, 4: 9000}, die_area_mm2=None)
    assert c.tpp() == pytest.approx(36000)


def test_performance_density_divides_by_die_area():
    c = Chip("t", {16: 312, 8: 624}, die_area_mm2=826.0)
    assert c.performance_density() == pytest.approx(4992 / 826.0, rel=1e-3)


def test_density_none_when_no_die_area():
    c = Chip("t", {8: 624}, die_area_mm2=None)
    assert c.performance_density() is None


def test_density_none_on_planar_node():
    c = Chip("t", {8: 624}, die_area_mm2=500.0, nonplanar_node=False)
    assert c.performance_density() is None


# ---------------------------------------------------------------------------
# 2. Dataset regression: ground truth holds under the current (2023) rule
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def chips_by_name():
    return {c.name: c for c in load_chips()}


@pytest.mark.parametrize("name,expected", sorted(GROUND_TRUTH.items()))
def test_ground_truth_2023(chips_by_name, name, expected):
    chip = chips_by_name[name]
    controlled = classify_2023(chip) == "CONTROLLED"
    assert controlled is expected, (
        f"{name}: TPP={chip.tpp():.0f} classified controlled={controlled}, expected {expected}"
    )


def test_loader_rejects_sparse_rows(tmp_path):
    # A with_sparsity=true row must raise -- the tripwire against sparse figures.
    chips_csv = tmp_path / "chips.csv"
    thr_csv = tmp_path / "throughput.csv"
    chips_csv.write_text(
        "name,die_area_mm2,nonplanar_node,node,memory_bandwidth_gbps,"
        "interconnect_gbps,release_date,market,die_area_source\n"
        "X,800,true,N4,3000,900,2024-01,global,test\n"
    )
    thr_csv.write_text(
        "name,precision,type,bit_length,dense_tops,with_sparsity,source\n"
        "X,FP16,float,16,1979,true,should-be-halved\n"
    )
    with pytest.raises(ValueError, match="with_sparsity"):
        load_chips(str(tmp_path))


# ---------------------------------------------------------------------------
# 3. Rule vintages: the migration story is mechanically true
# ---------------------------------------------------------------------------

def test_a800_loophole_closes_2022_to_2023(chips_by_name):
    a800 = chips_by_name["NVIDIA A800 (SXM 80GB)"]
    assert classify_2022(a800) == "free"          # escaped via cut interconnect
    assert classify_2023(a800) == "CONTROLLED"    # caught once interconnect dropped


def test_h800_loophole_closes_2022_to_2023(chips_by_name):
    h800 = chips_by_name["NVIDIA H800 (SXM)"]
    assert classify_2022(h800) == "free"
    assert classify_2023(h800) == "CONTROLLED"


def test_h20_free_under_all_vintages(chips_by_name):
    h20 = chips_by_name["NVIDIA H20"]
    assert classify_2022(h20) == "free"
    assert classify_2023(h20) == "free"
    assert classify_2026_cn(h20) == "free"


def test_b200_breaches_2026_ceiling(chips_by_name):
    b200 = chips_by_name["NVIDIA B200"]
    assert classify_2023(b200) == "CONTROLLED"
    assert classify_2026_cn(b200) == "denial"     # TPP 36000 > 21000 ceiling


def test_h200_and_mi325x_case_by_case(chips_by_name):
    for name in ("NVIDIA H200 (SXM)", "AMD MI325X"):
        chip = chips_by_name[name]
        assert classify_2026_cn(chip) == "case-by-case", name
