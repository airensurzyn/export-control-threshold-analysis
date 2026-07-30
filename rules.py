"""
rules.py  —  time-versioned BIS advanced-computing classifier.

Scores each chip under successive rule VINTAGES so status *migration* becomes
visible -- e.g. the A800/H800 are free under the Oct-2022 rule but caught by the
Oct-2023 TPP rule (the interconnect loophole being closed).

Vintages modeled:

  2022-10-07  Original ECCN 3A090. Controlled IFF BOTH:
                TPP >= 4800  AND  interconnect >= 600 GB/s.
              The AND is the whole story: cutting NVLink to 400 GB/s (A800/H800)
              dropped below the interconnect prong -> escaped control.

  2023-10-17  Revised 3A090. Interconnect parameter DELETED; performance-density
              prong added. Controlled IFF:
                TPP >= 4800  OR  (TPP >= 1600 AND performance_density >= 5.92).
              A800/H800 kept full compute -> now caught.

  2026-01-15  3A090 control unchanged from 2023. Adds a China/Macau LICENSE-REVIEW
              overlay: a controlled chip is "case-by-case" eligible IFF
                TPP < 21000  AND  DRAM_bandwidth < 6500 GB/s,
              otherwise "presumption of denial".
              SIMPLIFIED: the real policy named specific SKUs (H200, MI325X) and
              layered KYC/testing/supply conditions on top. See ledger.

Run:  python3 rules.py
"""

from __future__ import annotations

from load_chips import load_chips


# --- individual rule vintages -------------------------------------------------

def classify_2022(chip) -> str:
    tpp = chip.tpp()
    ic = chip.interconnect_gbps
    controlled = tpp >= 4800 and (ic is not None and ic >= 600)
    return "CONTROLLED" if controlled else "free"


def classify_2023(chip) -> str:
    tpp = chip.tpp()
    pd = chip.performance_density()
    by_tpp = tpp >= 4800
    by_density = pd is not None and tpp >= 1600 and pd >= 5.92
    return "CONTROLLED" if (by_tpp or by_density) else "free"


def classify_2026_cn(chip) -> str:
    # Control status is the 2023 test; the 2026 change is a licensing overlay
    # applied to CONTROLLED chips headed to China/Macau.
    if classify_2023(chip) == "free":
        return "free"
    tpp = chip.tpp()
    dram = chip.memory_bandwidth_gbps
    eligible = tpp < 21000 and (dram is not None and dram < 6500)
    return "case-by-case" if eligible else "denial"


VINTAGES = [
    ("2022-10-07", classify_2022),
    ("2023-10-17", classify_2023),
    ("2026-01-15 (CN)", classify_2026_cn),
]


def status_row(chip) -> list[str]:
    return [fn(chip) for _, fn in VINTAGES]


def main():
    chips = load_chips()
    cols = [label for label, _ in VINTAGES]

    # --- matrix: chips x vintages ---
    name_w = max(len(c.name) for c in chips) + 2
    col_w = 16
    print("Control status by rule vintage\n")
    header = f"{'Chip':{name_w}}{'TPP':>8}  " + "".join(f"{c:>{col_w}}" for c in cols)
    print(header)
    print("-" * len(header))
    for c in chips:
        row = status_row(c)
        line = f"{c.name:{name_w}}{c.tpp():>8.0f}  " + "".join(f"{s:>{col_w}}" for s in row)
        print(line)

    # --- migration report: status changes between consecutive vintages ---
    print("\nStatus migrations (chip changed classification when the rule changed):")
    found = False
    for c in chips:
        row = status_row(c)
        for i in range(1, len(row)):
            if row[i] != row[i - 1]:
                found = True
                print(f"  {c.name}: {cols[i-1]} [{row[i-1]}]  ->  {cols[i]} [{row[i]}]")
    if not found:
        print("  (none)")


if __name__ == "__main__":
    main()