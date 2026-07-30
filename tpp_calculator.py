"""
tpp_calculator.py  —  BIS ECCN 3A090 export-control classifier (starter scaffold)

Reconstructs the numerical control lines from the regulatory text
so every downstream classification/chart inherits one audited definition.

Regulatory definitions:
  * TPP  = 2 * MacTOPS * bit_length, aggregated over all processing units,
           evaluated PER precision on DENSE (no-sparsity) matrices.
           In practice 2*MacTOPS == the dense TOPS/FLOPS a datasheet reports, so
           TPP(precision) = dense_throughput(precision) * bit_length.
  * Performance density = TPP / applicable_die_area_mm^2
           (applicable die area = logic die on a non-planar/FinFET+ node, SRAM
            included, HBM memory stacks excluded).
  * 3A090.a controlled if:  TPP >= 4800
                            OR (TPP >= 1600 AND density >= 5.92)

"""

from __future__ import annotations

from dataclasses import dataclass, field


# --- Time-versioned thresholds (extend as rules change) ----------------------
# Encode the lines as they stood on each date so a chip's status can migrate.
THRESHOLDS = {
    "2023-10-17": {"tpp_control": 4800, "tpp_density_floor": 1600, "density": 5.92},
    # 2022-10-07 original rule used a different metric (bits x TOPS); model
    # separately if you extend the timeline back that far.
}
CURRENT = "2023-10-17"


@dataclass
class Chip:
    name: str
    # dense throughput (TOPS or TFLOP/s, NO sparsity) keyed by bit length
    dense_throughput: dict          # {bit_length: dense_tops}
    die_area_mm2: float | None      # applicable (logic, non-planar node) die area
    nonplanar_node: bool = True     # FinFET/GAA -> die area counts toward density
    interconnect_gbps: float | None = None      # bidirectional I/O rate (2022 rule)
    memory_bandwidth_gbps: float | None = None   # DRAM bandwidth (2026 license overlay)
    release_date: str | None = None              # "YYYY-MM"
    market: str = ""                             # "global" | "china"
    source_notes: str = ""

    def tpp(self) -> float:
        # per-precision TPP = dense_throughput * bit_length; take the max
        return max(tops * bits for bits, tops in self.dense_throughput.items())

    def performance_density(self) -> float | None:
        if not self.nonplanar_node or not self.die_area_mm2:
            return None
        return self.tpp() / self.die_area_mm2

    def classify(self, rule: str = CURRENT) -> dict:
        t = THRESHOLDS[rule]
        tpp = self.tpp()
        pd = self.performance_density()
        controlled_by_tpp = tpp >= t["tpp_control"]
        controlled_by_density = (
            pd is not None and tpp >= t["tpp_density_floor"] and pd >= t["density"]
        )
        return {
            "tpp": round(tpp, 1),
            "density": round(pd, 2) if pd is not None else None,
            "controlled": controlled_by_tpp or controlled_by_density,
            "trigger": (
                "TPP" if controlled_by_tpp
                else "density" if controlled_by_density
                else "none"
            ),
        }


# --- Validation set: 3 chips with KNOWN ground-truth status ------------------
# Ground truth: A100 controlled (defined the original line), H100 controlled
# (far above), H20 purpose-built to be exportable to China (must come back legal).
CHIPS = [
    Chip(
        name="NVIDIA A100 (SXM 80GB)",
        dense_throughput={16: 312, 8: 624},   # FP16 312 TFLOPS, INT8 624 TOPS (dense)
        die_area_mm2=826.0,                    # GA100, TSMC N7 (FinFET)
        source_notes="Illustrative. A100 sits right on the original line -> validates boundary.",
    ),
    Chip(
        name="NVIDIA H100 (SXM)",
        dense_throughput={16: 989, 8: 1979},   # dense; NOTE sparsity headline is 2x these
        die_area_mm2=814.0,                     # GH100, TSMC N4
        source_notes="Illustrative. Exact TPP is sensitive to sparsity/variant; status robustly 'controlled'.",
    ),
    Chip(
        name="NVIDIA H20",
        dense_throughput={16: 148},             # deliberately low; ~2500 TPP class part
        die_area_mm2=814.0,                     # same GH100 die
        source_notes="Illustrative. Purpose-built below 4800 and below density prong -> exportable to China.",
    ),
]


def main():
    print(f"Rule vintage: {CURRENT}")
    print(f"Lines: TPP>={THRESHOLDS[CURRENT]['tpp_control']}  |  "
          f"TPP>={THRESHOLDS[CURRENT]['tpp_density_floor']} AND "
          f"density>={THRESHOLDS[CURRENT]['density']}\n")
    header = f"{'Chip':28} {'TPP':>8} {'Density':>8} {'Trigger':>9}  Controlled"
    print(header)
    print("-" * len(header))
    for c in CHIPS:
        r = c.classify()
        dens = f"{r['density']:.2f}" if r["density"] is not None else "  n/a"
        print(f"{c.name:28} {r['tpp']:>8.0f} {dens:>8} {r['trigger']:>9}  "
              f"{'YES' if r['controlled'] else 'no'}")
    print("\nExpected ground truth: A100 YES, H100 YES, H20 no")


if __name__ == "__main__":
    main()
