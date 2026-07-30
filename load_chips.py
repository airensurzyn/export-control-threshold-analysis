"""
load_chips.py  —  build Chip objects from the provenance-tracked CSVs and classify.

Data now lives in data/*.csv (one number = one row = one source), NOT hardcoded in
Python. To add a chip: append rows to data/chips.csv and data/throughput.csv with a
source for every value. No code changes needed.

  data/chips.csv       one row per chip   (die area, node, source)
  data/throughput.csv  one row per (chip, precision)  (dense throughput, source)

Run:  python3 load_chips.py
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict

from tpp_calculator import Chip, CURRENT  # reuse the audited model + thresholds

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in {"true", "1", "yes", "y"}


def load_chips(data_dir: str = DATA_DIR) -> list[Chip]:
    # 1) throughput: group dense values by chip -> {bit_length: dense_tops}
    throughput: dict[str, dict[int, float]] = defaultdict(dict)
    with open(os.path.join(data_dir, "throughput.csv"), newline="") as f:
        for row in csv.DictReader(f):
            if _to_bool(row["with_sparsity"]):
                # TPP is defined on DENSE matrices; refuse sparse numbers loudly
                raise ValueError(
                    f"{row['name']} @ {row['bit_length']}b is flagged with_sparsity=true. "
                    "TPP requires dense values -- halve it and set the flag to false."
                )
            # A chip can list several precisions at the same bit length
            # (e.g. FP32 & TF32 at 32b). TPP takes the MAX, so keep the highest.
            bits = int(row["bit_length"])
            val = float(row["dense_tops"])
            prev = throughput[row["name"]].get(bits, 0.0)
            throughput[row["name"]][bits] = max(prev, val)

    # 2) chip metadata -> build Chip objects
    chips: list[Chip] = []
    with open(os.path.join(data_dir, "chips.csv"), newline="") as f:
        for row in csv.DictReader(f):
            name = row["name"]
            die = row["die_area_mm2"].strip()
            mem = row.get("memory_bandwidth_gbps", "").strip()
            ic = row.get("interconnect_gbps", "").strip()
            chips.append(Chip(
                name=name,
                dense_throughput=throughput.get(name, {}),
                die_area_mm2=float(die) if die else None,
                nonplanar_node=_to_bool(row["nonplanar_node"]),
                interconnect_gbps=float(ic) if ic else None,
                memory_bandwidth_gbps=float(mem) if mem else None,
                release_date=(row.get("release_date", "").strip() or None),
                market=row.get("market", "").strip(),
                source_notes=row.get("die_area_source", ""),
            ))
    return chips


# Ground-truth expectations for the validation set (regression test).
GROUND_TRUTH = {
    "NVIDIA A100 (SXM 80GB)": True,
    "NVIDIA H100 (SXM)": True,
    "NVIDIA H20": False,
    # A800/H800 kept full compute -> caught by the 2023 TPP rule (loophole closed)
    "NVIDIA A800 (SXM 80GB)": True,
    "NVIDIA H800 (SXM)": True,
    # Newer parts: all well above 4800 TPP -> controlled under 2023
    "NVIDIA H200 (SXM)": True,
    "NVIDIA B200": True,
    "AMD MI300X": True,
    "AMD MI325X": True,
}


def main():
    chips = load_chips()
    print(f"Loaded {len(chips)} chips from {DATA_DIR}\n")
    header = f"{'Chip':28} {'TPP':>8} {'Density':>8} {'Trigger':>9}  Controlled"
    print(header)
    print("-" * len(header))
    for c in chips:
        r = c.classify(CURRENT)
        dens = f"{r['density']:.2f}" if r["density"] is not None else "  n/a"
        print(f"{c.name:28} {r['tpp']:>8.0f} {dens:>8} {r['trigger']:>9}  "
              f"{'YES' if r['controlled'] else 'no'}")

    # Validation: fail loudly if any known chip is misclassified.
    print("\nValidation vs ground truth:")
    ok = True
    for c in chips:
        if c.name in GROUND_TRUTH:
            got = c.classify(CURRENT)["controlled"]
            want = GROUND_TRUTH[c.name]
            status = "pass" if got == want else "FAIL"
            if got != want:
                ok = False
            print(f"  [{status}] {c.name}: got controlled={got}, want {want}")
    print("\nAll validations passed." if ok else "\n*** VALIDATION FAILED ***")


if __name__ == "__main__":
    main()
