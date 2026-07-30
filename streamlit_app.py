"""
streamlit_app.py  —  "Classify your own chip" against BIS advanced-computing controls.

Interactive front end over the SAME model + rules the analysis and tests use, so the
tool can never drift from the audited classifier.

Run locally:   streamlit run streamlit_app.py
Deploy free:   push to GitHub -> share.streamlit.io -> point at streamlit_app.py
"""

import os
import sys

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tpp_calculator import Chip
from rules import classify_2022, classify_2023, classify_2026_cn
from load_chips import load_chips

# --- precisions offered in the UI (bit length -> label) ----------------------
PRECISIONS = [
    (4, "4-bit (FP4 / INT4)"),
    (8, "8-bit (FP8 / INT8)"),
    (16, "16-bit (FP16 / BF16)"),
    (32, "32-bit (FP32 / TF32)"),
    (64, "64-bit (FP64)"),
]

# --- a few presets (dense values) so users can start from a known chip -------
PRESETS = {
    "-- start blank --": {},
    "NVIDIA A100": {16: 312.0, 8: 624.0, 32: 156.0, "die": 826.0, "ic": 600.0, "mem": 2039.0},
    "NVIDIA H100": {16: 989.5, 8: 1979.0, 4: 0.0, "die": 814.0, "ic": 900.0, "mem": 3350.0},
    "NVIDIA H20": {16: 148.0, 8: 296.0, "die": 814.0, "ic": 900.0, "mem": 4000.0},
    "NVIDIA B200": {16: 2250.0, 8: 4500.0, 4: 9000.0, "die": 0.0, "ic": 1800.0, "mem": 7700.0},
    "AMD MI325X": {16: 1307.4, 8: 2614.9, "die": 0.0, "ic": 896.0, "mem": 6000.0},
}

STATUS_STYLE = {
    "CONTROLLED": ("#c5221f", "Controlled — license required (presumption of denial)"),
    "free": ("#188038", "Not controlled — no 3A090 license needed"),
    "case-by-case": ("#e37400", "Controlled; China/Macau license reviewed case-by-case"),
    "denial": ("#c5221f", "Controlled; China/Macau presumption of denial"),
}


def badge(col, label, status):
    color, expl = STATUS_STYLE[status]
    col.markdown(
        f"<div style='padding:10px;border-radius:8px;background:{color};color:white;"
        f"text-align:center'><b>{label}</b><br><span style='font-size:1.3em'>{status}</span></div>",
        unsafe_allow_html=True,
    )
    col.caption(expl)


def build_chip(name, values, sparsity, die, nonplanar, ic, mem):
    dense = {}
    for bits, _ in PRECISIONS:
        v = values.get(bits, 0.0)
        if v and v > 0:
            dense[bits] = v / 2 if sparsity else v
    return Chip(
        name=name or "Custom chip",
        dense_throughput=dense,
        die_area_mm2=die if die and die > 0 else None,
        nonplanar_node=nonplanar,
        interconnect_gbps=ic if ic and ic > 0 else None,
        memory_bandwidth_gbps=mem if mem and mem > 0 else None,
    )


def reference_plot(chip_tpp):
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.set_xscale("log")
    ax.set_xlim(1000, 1e6)
    ax.set_ylim(-1, 1)

    # y in axes-fraction so labels are always inside the box, regardless of data
    trans = ax.get_xaxis_transform()

    # shade the controlled region (TPP >= 4800)
    ax.axvspan(4800, 1e6, color="#c5221f", alpha=0.06, zorder=0)

    for val, color, label in [
        (1600, "#9aa0a6", "1,600 floor"),
        (4800, "#c5221f", "4,800 control"),
        (21000, "#7b1fa2", "21,000 ceiling"),
    ]:
        ax.axvline(val, color=color, linestyle="--", linewidth=1.2, zorder=1)
        ax.text(val, 0.9, label, transform=trans, rotation=90,
                fontsize=8, color=color, va="top", ha="right")

    # dataset chips as a grey reference row
    try:
        for c in load_chips():
            ax.scatter(c.tpp(), 0, s=45, c="#bbbbbb", zorder=2)
    except Exception:
        pass

    # the user's chip: big star + TPP label
    ax.scatter(chip_tpp, 0, s=320, marker="*", c="#1a73e8",
               edgecolors="black", linewidths=0.7, zorder=3, label="your chip")
    ax.annotate(f"{chip_tpp:,.0f}", (chip_tpp, 0), textcoords="offset points",
                xytext=(0, 14), ha="center", fontsize=9, weight="bold", color="#1a73e8")

    ax.set_yticks([])
    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)
    ax.set_xlabel("Total Processing Performance (TPP, log scale) — grey = dataset chips")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    return fig


# =============================================================================
st.set_page_config(page_title="Chip Export-Control Classifier", page_icon="🧮", layout="centered")
st.title("🧮 Classify your own chip")
st.caption("Enter an accelerator's specs and see how it classifies under U.S. advanced-computing "
           "export controls (ECCN 3A090) across three rule vintages. Same engine as the analysis.")

with st.sidebar:
    st.header("Inputs")
    preset_name = st.selectbox("Preset", list(PRESETS.keys()))
    preset = PRESETS[preset_name]
    name = st.text_input("Chip name", value="" if preset_name.startswith("--") else preset_name)

    st.markdown("**Dense throughput** (TOPS / TFLOP·s, *no sparsity*). Leave 0 if unsupported.")
    sparsity = st.checkbox("My numbers include sparsity — halve them", value=False)
    values = {}
    for bits, label in PRECISIONS:
        values[bits] = st.number_input(label, min_value=0.0, value=float(preset.get(bits, 0.0)),
                                       step=1.0, format="%.1f")

    st.markdown("**Physical / other specs**")
    die = st.number_input("Applicable die area (mm², 0 = unknown)",
                          min_value=0.0, value=float(preset.get("die", 0.0)), step=1.0)
    nonplanar = st.checkbox("Non-planar node (FinFET/GAA) — counts toward density", value=True)
    ic = st.number_input("Interconnect bandwidth (GB/s, for 2022 rule)",
                         min_value=0.0, value=float(preset.get("ic", 0.0)), step=1.0)
    mem = st.number_input("DRAM bandwidth (GB/s, for 2026 overlay)",
                          min_value=0.0, value=float(preset.get("mem", 0.0)), step=1.0)

chip = build_chip(name, values, sparsity, die, nonplanar, ic, mem)

if not chip.dense_throughput:
    st.info("Enter at least one dense throughput value in the sidebar to classify a chip.")
    st.stop()

tpp = chip.tpp()
density = chip.performance_density()

c1, c2 = st.columns(2)
c1.metric("Total Processing Performance (TPP)", f"{tpp:,.0f}")
c2.metric("Performance density", f"{density:.2f}" if density is not None else "n/a (no die area)")

# which prong catches it (2023 rule)
if tpp >= 4800:
    trigger = "TPP ≥ 4,800 (primary prong)"
elif density is not None and tpp >= 1600 and density >= 5.92:
    trigger = "TPP ≥ 1,600 and density ≥ 5.92 (anti-chiplet prong)"
else:
    trigger = "neither prong — not controlled"
st.write(f"**Control trigger (2023 rule):** {trigger}")

st.subheader("Status by rule vintage")
b1, b2, b3 = st.columns(3)
badge(b1, "Oct 2022", classify_2022(chip))
badge(b2, "Oct 2023 (current)", classify_2023(chip))
badge(b3, "Jan 2026 (China/Macau)", classify_2026_cn(chip))

st.subheader("Where it lands")
st.pyplot(reference_plot(tpp))

with st.expander("How TPP is computed"):
    st.markdown(
        "`TPP = 2 × MacTOPS × bit_length`, evaluated per precision on **dense** matrices, "
        "taking the maximum. In practice that is `dense_throughput × bit_length` per precision:"
    )
    rows = "\n".join(
        f"- {label}: {chip.dense_throughput[bits]:,.1f} × {bits} = **{chip.dense_throughput[bits]*bits:,.0f}**"
        for bits, label in PRECISIONS if bits in chip.dense_throughput
    )
    st.markdown(rows)
    st.caption("The maximum across precisions is the chip's TPP. Thresholds: 3A090.a is "
               "controlled if TPP ≥ 4,800, or TPP ≥ 1,600 with performance density ≥ 5.92.")
