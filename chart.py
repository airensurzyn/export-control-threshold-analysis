"""
chart.py  —  the headroom figure.

Plots each chip by release date (x) against its TPP (y, log) with the BIS control
lines drawn across, so the "designed to the threshold" story is visible: the
throttled China SKUs appear right after each rule and hug the 4,800 line from below,
while the global flagships tower above it.

  * horizontal lines  = the numerical thresholds (1600 floor, 4800 control, 21000 ceiling)
  * vertical lines     = when each rule took effect
  * marker shape       = market (circle = global, diamond = China SKU)
  * marker color       = control status under the CURRENT (2023) rule

Run:  python3 chart.py   ->   figures/headroom.png
"""

from __future__ import annotations

import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from load_chips import load_chips
from rules import classify_2023

OUT = os.path.join(os.path.dirname(__file__), "figures")
os.makedirs(OUT, exist_ok=True)

# thresholds (label, value, color, style)
HLINES = [
    ("Density-prong floor (1,600)", 1600, "#9aa0a6", ":"),
    ("3A090 control line (4,800)", 4800, "#c5221f", "-"),
    ("2026 case-by-case ceiling (21,000)", 21000, "#7b1fa2", "--"),
]
# rule effective dates (label, date)
RULES = [
    ("Oct 2022 rule", "2022-10"),
    ("Oct 2023 rule", "2023-10"),
    ("Jan 2026 rule", "2026-01"),
]


def short(name: str) -> str:
    return name.replace("NVIDIA ", "").split(" (")[0]


def to_dt(ym: str) -> datetime:
    return datetime.strptime(ym, "%Y-%m")


def main():
    chips = [c for c in load_chips() if c.release_date]

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.set_yscale("log")

    # shaded "controlled" band above the 4,800 line
    ax.axhspan(4800, 1e6, color="#c5221f", alpha=0.05, zorder=0)

    # threshold lines
    for label, val, color, style in HLINES:
        ax.axhline(val, color=color, linestyle=style, linewidth=1.4, zorder=1)
        ax.text(to_dt("2026-08"), val * 1.08, label, color=color,
                fontsize=8, va="bottom", ha="right")

    # rule effective-date verticals
    for label, ym in RULES:
        d = to_dt(ym)
        ax.axvline(d, color="#5f6368", linestyle="-", linewidth=0.8, alpha=0.5, zorder=1)
        ax.text(d, 1.15e6, label, rotation=90, fontsize=7.5,
                color="#5f6368", va="top", ha="right")

    # chip points
    for c in chips:
        controlled = classify_2023(c) == "CONTROLLED"
        color = "#c5221f" if controlled else "#188038"
        marker = "D" if c.market == "china" else "o"
        x, y = to_dt(c.release_date), c.tpp()
        ax.scatter(x, y, s=130, c=color, marker=marker,
                   edgecolors="black", linewidths=0.6, zorder=3)
        ax.annotate(f"{short(c.name)}\nTPP {y:,.0f}", (x, y),
                    textcoords="offset points", xytext=(10, 6),
                    fontsize=8.5, zorder=4)

    ax.set_ylim(1000, 2e6)
    ax.set_xlim(to_dt("2020-06"), to_dt("2026-09"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_ylabel("Total Processing Performance (TPP, log scale)")
    ax.set_xlabel("Release date")
    ax.set_title("Design-to-threshold: NVIDIA accelerators vs. BIS control lines over time",
                 fontsize=13, weight="bold")

    # legend (manual proxies)
    from matplotlib.lines import Line2D
    legend = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#c5221f",
               markeredgecolor="black", markersize=11, label="Controlled (2023 rule)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#188038",
               markeredgecolor="black", markersize=11, label="Not controlled"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#5f6368",
               markeredgecolor="black", markersize=11, label="Global SKU"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor="#5f6368",
               markeredgecolor="black", markersize=11, label="China SKU"),
    ]
    ax.legend(handles=legend, loc="upper left", fontsize=8.5, framealpha=0.95)

    fig.tight_layout()
    path = os.path.join(OUT, "headroom.png")
    fig.savefig(path, dpi=150)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
