#!/usr/bin/env python3
"""Generate IEEE-styled figures for Project 5 paper.

Outputs PNG (300 dpi), PDF, and SVG to report/figures/.
Single-column figures sized ~3.5in x 2.2in with 7-9 pt fonts.
"""

import csv
import os
import sys
from collections import defaultdict

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import scienceplots  # noqa: F401

STYLE = ["science", "ieee", "no-latex"]

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.normpath(os.path.join(HERE, "..", "..", "results"))
OUT = HERE


def _save(fig, name):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(os.path.join(OUT, "%s.%s" % (name, ext)),
                    dpi=300, bbox_inches="tight")
    plt.close(fig)


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


# ----------------------------------------------------------------------
# Figure 1: per-mode aggregate accept rate, policy accuracy, latency
# ----------------------------------------------------------------------
def fig_mode_results():
    rows = load_csv(os.path.join(RESULTS, "summary_by_mode.csv"))
    order = ["baseline", "fdia_only", "typec_only", "combined"]
    rows = sorted(rows, key=lambda r: order.index(r["mode"]))
    modes = [r["mode"].replace("_", "\n") for r in rows]
    accept = [float(r["mean_accept_rate"]) for r in rows]
    policy = [float(r["mean_pair_policy_accuracy"]) for r in rows]
    lat = [float(r["median_of_median_relay_latency_ms"]) for r in rows]

    with plt.style.context(STYLE):
        fig, ax1 = plt.subplots(figsize=(3.5, 2.2))
        x = np.arange(len(modes))
        w = 0.35
        ax1.bar(x - w / 2, accept, w, label="Accept rate",
                color="#4C72B0", edgecolor="black", linewidth=0.4)
        ax1.bar(x + w / 2, policy, w, label="Policy accuracy",
                color="#55A868", edgecolor="black", linewidth=0.4)
        ax1.set_xticks(x)
        ax1.set_xticklabels(modes, fontsize=7)
        ax1.set_ylabel("Rate", fontsize=8)
        ax1.set_ylim(0, 1.08)
        ax1.tick_params(axis="y", labelsize=7)

        ax2 = ax1.twinx()
        ax2.plot(x, lat, marker="o", color="#C44E52",
                 linewidth=1.0, markersize=3.5, label="Latency (ms)")
        ax2.set_ylabel("Median latency (ms)", fontsize=8, color="#C44E52")
        ax2.tick_params(axis="y", labelsize=7, colors="#C44E52")
        ax2.set_ylim(0, max(lat) * 1.4)

        l1, lb1 = ax1.get_legend_handles_labels()
        l2, lb2 = ax2.get_legend_handles_labels()
        ax1.legend(l1 + l2, lb1 + lb2,
                   fontsize=6, loc="upper right", framealpha=0.9)
        ax1.grid(axis="y", linestyle=":", linewidth=0.4, alpha=0.6)
        _save(fig, "fig_mode_results")


# ----------------------------------------------------------------------
# Figure 2: confusion outcomes — 2x2 heatmap with counts AND row-rates
# ----------------------------------------------------------------------
def fig_confusion():
    rows = load_csv(os.path.join(RESULTS, "confusion_table.csv"))
    r = rows[0]
    bf, bb = int(r["benign_forwarded"]), int(r["benign_blocked"])
    af, ab = int(r["attack_forwarded"]), int(r["attack_blocked"])
    M = np.array([[bf, bb], [af, ab]], dtype=float)
    row_tot = M.sum(axis=1, keepdims=True)
    P = M / row_tot

    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(3.0, 2.0))
        im = ax.imshow(P, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
        ax.set_xticklabels(["Forwarded", "Blocked"], fontsize=8)
        ax.set_yticklabels(["Benign", "Attack"], fontsize=8)
        ax.set_xlabel("Relay decision", fontsize=8)
        ax.set_ylabel("Ground truth", fontsize=8)
        for i in range(2):
            for j in range(2):
                count = int(M[i, j])
                pct = P[i, j] * 100
                color = "white" if P[i, j] > 0.55 else "#222"
                ax.text(j, i - 0.10, "%d" % count,
                        ha="center", va="center", fontsize=10,
                        color=color, fontweight="bold")
                ax.text(j, i + 0.18, "(%.0f%%)" % pct,
                        ha="center", va="center", fontsize=7, color=color)
        # Highlight diagonal (correct outcomes)
        for k in (0, 1):
            ax.add_patch(mpatches.Rectangle((k - 0.49, k - 0.49), 0.98, 0.98,
                                            fill=False, edgecolor="#2E7D32",
                                            linewidth=1.2))
        cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.ax.tick_params(labelsize=6)
        cb.set_label("Row fraction", fontsize=7)
        _save(fig, "fig_confusion")


# ----------------------------------------------------------------------
# Figure 3: severity vs setpoint perturbation (analytical sweep)
# ----------------------------------------------------------------------
def fig_severity_sweep():
    rows = load_csv(os.path.join(RESULTS, "severity_sweep.csv"))
    sp = np.array([float(r["setpoint"]) for r in rows])
    sev = np.array([float(r["severity"]) for r in rows])

    NOMINAL = 1.63
    BAND = 1.0
    TAU = 0.10

    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(3.5, 2.3))
        # Tier-1 band shading
        ax.axvspan(NOMINAL - BAND, NOMINAL + BAND,
                   color="#7BB661", alpha=0.18,
                   label="Tier-1 band")
        # Tier-2 threshold
        ax.axhline(TAU, color="#C44E52", linestyle="--", linewidth=0.9,
                   label=r"Tier-2 threshold $\tau$")
        # Severity curve
        ax.plot(sp, sev, color="#1F4E79", linewidth=1.2,
                label=r"$\|\mathbf{G}\Delta\mathbf{z}\|_\infty$")

        markers = [
            (1.62, "benign",   "#2E7D32", "o"),
            (2.50, "stealthy", "#E65100", "^"),
            (8.00, "gross (8.0)", "#B71C1C", "X"),
        ]
        for x, lbl, col, m in markers:
            if x > sp.max():
                # off-chart; annotate at right edge
                ax.annotate("%s$\\to$" % lbl,
                            xy=(sp.max(), TAU * 6),
                            fontsize=7, color=col, ha="right")
                continue
            idx = int(np.argmin(np.abs(sp - x)))
            ax.scatter([sp[idx]], [sev[idx]], color=col, marker=m, s=24,
                       edgecolor="black", linewidths=0.4, zorder=5,
                       label=lbl)

        ax.set_xlabel("Commanded setpoint (pu)", fontsize=8)
        ax.set_ylabel(r"Severity $s$ (pu)", fontsize=8)
        ax.set_yscale("log")
        ax.set_ylim(5e-4, 5)
        ax.set_xlim(sp.min(), sp.max())
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=6, loc="upper left",
                  framealpha=0.9, ncol=2)
        ax.grid(True, which="both", linestyle=":", linewidth=0.3, alpha=0.5)
        _save(fig, "fig_severity_sweep")


# ----------------------------------------------------------------------
# Figure 4: stealthy-attack ablation matrix (the key result)
# ----------------------------------------------------------------------
def fig_stealthy_ablation():
    """Decision matrix from real Mininet runs (results/stealthy_mininet.csv).
    Aggregates trials by majority decision."""
    rows = load_csv(os.path.join(RESULTS, "stealthy_mininet.csv"))
    scenarios = ["benign", "stealthy", "gross"]
    sp_label = {"benign": "1.62", "stealthy": "2.50", "gross": "8.00"}
    combos = [(True, True), (True, False), (False, True), (False, False)]
    combo_lbl = ["T1+T2", "T1 only", "T2 only", "none"]

    def to_bool(s):
        return str(s).strip().lower() == "true"

    # Aggregate by (scenario, tier1, tier2): majority decision over trials
    from collections import Counter
    bucket = defaultdict(list)
    for r in rows:
        key = (r["scenario"], (to_bool(r["tier1_on"]), to_bool(r["tier2_on"])))
        bucket[key].append(r["decision"])
    decision = {k: Counter(v).most_common(1)[0][0] for k, v in bucket.items()}

    with plt.style.context(STYLE):
        fig, ax = plt.subplots(figsize=(3.5, 2.3))
        # Build grid: rows = scenarios, cols = configs
        grid = np.zeros((len(scenarios), len(combos)))
        labels = np.empty_like(grid, dtype=object)
        for i, sc in enumerate(scenarios):
            for j, cb in enumerate(combos):
                d = decision[(sc, cb)]
                expected_accept = (sc == "benign")
                # 1 = correct outcome, 0 = wrong
                correct = (d == "accept") == expected_accept
                grid[i, j] = 1 if correct else 0
                labels[i, j] = "ACC" if d == "accept" else "REJ"

        # Use red/green: green = correct policy outcome
        cmap = plt.cm.RdYlGn
        im = ax.imshow(grid, cmap=cmap, vmin=-0.1, vmax=1.1, aspect="auto")
        ax.set_xticks(range(len(combos)))
        ax.set_xticklabels(combo_lbl, fontsize=7)
        ax.set_yticks(range(len(scenarios)))
        ax.set_yticklabels(
            ["%s\n(sp=%s)" % (sc, sp_label[sc]) for sc in scenarios],
            fontsize=7)
        for i in range(len(scenarios)):
            for j in range(len(combos)):
                ax.text(j, i, labels[i, j], ha="center", va="center",
                        fontsize=8, fontweight="bold",
                        color="#222")
        ax.set_xlabel("Defense configuration", fontsize=8)
        ax.set_title("Relay decision (green = correct policy)",
                     fontsize=8, pad=4)
        # Outline the row of stealthy attacks (the discriminating case)
        ax.add_patch(mpatches.Rectangle((-0.5, 0.5), len(combos), 1.0,
                                        fill=False, edgecolor="#0D47A1",
                                        linewidth=1.4, linestyle="-"))
        _save(fig, "fig_stealthy_ablation")


def main():
    print("Writing figures to", OUT)
    fig_mode_results()
    fig_confusion()
    fig_severity_sweep()
    fig_stealthy_ablation()
    # Drop the old fig_ablation outputs to avoid confusion
    for ext in ("png", "pdf", "svg"):
        old = os.path.join(OUT, "fig_ablation." + ext)
        if os.path.exists(old):
            os.remove(old)
    print("Done.")


if __name__ == "__main__":
    main()
