#!/usr/bin/env python3
"""
Generate figures from results/summary_by_mode.csv and results/events.csv.
Requires: matplotlib (pip install matplotlib).
"""

import argparse
import csv
import os
import sys


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def plot_accept_latency(by_mode_path, out_dir):
    import matplotlib.pyplot as plt

    rows = _read_csv(by_mode_path)
    if not rows:
        print("Empty %s" % by_mode_path, file=sys.stderr)
        return
    modes = [r["mode"] for r in rows]
    acc = [float(r["mean_accept_rate"]) if r.get("mean_accept_rate") else 0.0 for r in rows]
    lat = [
        float(r["median_of_median_relay_latency_ms"])
        if r.get("median_of_median_relay_latency_ms")
        else 0.0
        for r in rows
    ]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = range(len(modes))
    axes[0].bar(x, acc, color="steelblue")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(modes, rotation=25, ha="right")
    axes[0].set_ylabel("Mean accept rate")
    axes[0].set_title("Acceptance rate by mode")
    axes[0].set_ylim(0, 1.05)

    axes[1].bar(x, lat, color="darkseagreen")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(modes, rotation=25, ha="right")
    axes[1].set_ylabel("Median relay latency (ms)")
    axes[1].set_title("Median control latency by mode")

    fig.tight_layout()
    path = os.path.join(out_dir, "accept_rate_and_latency.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("Wrote", path)


def plot_severity_events(events_path, out_dir):
    import matplotlib.pyplot as plt

    rows = _read_csv(events_path)
    sev_acc = []
    sev_rej = []
    for r in rows:
        s = r.get("severity", "").strip()
        if not s:
            continue
        try:
            v = float(s)
        except ValueError:
            continue
        if r.get("relay_decision") == "accept":
            sev_acc.append(v)
        elif r.get("relay_decision") == "reject":
            sev_rej.append(v)

    fig, ax = plt.subplots(figsize=(7, 4))
    lbl = []
    data = []
    if sev_acc:
        data.append(sev_acc)
        lbl.append("accepted")
    if sev_rej:
        data.append(sev_rej)
        lbl.append("rejected")
    if data:
        ax.boxplot(data, labels=lbl)
    else:
        ax.text(0.5, 0.5, "no severity values in log", ha="center", va="center")
    ax.set_ylabel("Tier-2 severity (L-inf norm of dx)")
    ax.set_title("Severity distribution: accepted vs rejected")
    fig.tight_layout()
    path = os.path.join(out_dir, "severity_boxplot.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("Wrote", path)


def plot_confusion(events_path, out_dir):
    """Heatmap-style counts: attack vs benign x blocked vs allowed."""
    import matplotlib.pyplot as plt

    rows = _read_csv(events_path)
    # Rows: actual benign vs attack intent at relay (fwd reflects attack)
    # Cols: relay blocked vs forwarded (accept)
    tb = {"benign_allow": 0, "benign_block": 0, "attack_allow": 0, "attack_block": 0}
    for r in rows:
        attack = r.get("type_c_attack", "").lower() == "true"
        blocked = r.get("relay_decision") == "reject"
        if not attack and not blocked:
            tb["benign_allow"] += 1
        elif not attack and blocked:
            tb["benign_block"] += 1
        elif attack and not blocked:
            tb["attack_allow"] += 1
        else:
            tb["attack_block"] += 1

    mat = [
        [tb["benign_allow"], tb["benign_block"]],
        [tb["attack_allow"], tb["attack_block"]],
    ]
    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(mat, cmap="Blues")
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["forwarded (accept)", "blocked (reject)"])
    ax.set_yticklabels(["Benign (no Type-C)", "Attack (Type-C override)"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(mat[i][j]), ha="center", va="center", color="navy", fontsize=12)
    ax.set_title("Command outcomes (confusion-style counts)")
    fig.colorbar(im, ax=ax, fraction=0.046)
    fig.tight_layout()
    path = os.path.join(out_dir, "confusion_counts.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("Wrote", path)


def plot_ablation_combo(combo_path, out_dir):
    """Bar charts from summary_by_combo.csv (tier1 x tier2 x profile)."""
    import matplotlib.pyplot as plt

    rows = _read_csv(combo_path)
    if not rows:
        print("Empty %s" % combo_path, file=sys.stderr)
        return
    labels = []
    pol = []
    atk = []
    ben = []
    lat = []
    for r in rows:
        t1 = "1" if str(r.get("tier1_on")).lower() in ("true", "1") else "0"
        t2 = "1" if str(r.get("tier2_on")).lower() in ("true", "1") else "0"
        labels.append(
            "%s|%s|t1=%s,t2=%s"
            % (r.get("mode", ""), r.get("profile", ""), t1, t2)
        )
        pol.append(float(r["mean_pair_policy_accuracy"] or 0))
        atk.append(float(r["mean_attack_block_rate"] or 0))
        ben.append(float(r["mean_benign_false_block_rate"] or 0))
        lat.append(float(r["median_of_median_relay_latency_ms"] or 0))

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    x = range(len(labels))
    axes[0, 0].bar(x, pol, color="steelblue")
    axes[0, 0].set_xticks(list(x))
    axes[0, 0].set_xticklabels(labels, rotation=60, ha="right", fontsize=6)
    axes[0, 0].set_ylabel("Mean policy accuracy")
    axes[0, 0].set_title("Policy accuracy by combo")
    axes[0, 0].set_ylim(0, 1.05)

    axes[0, 1].bar(x, atk, color="coral")
    axes[0, 1].set_xticks(list(x))
    axes[0, 1].set_xticklabels(labels, rotation=60, ha="right", fontsize=6)
    axes[0, 1].set_ylabel("Mean attack block rate")
    axes[0, 1].set_title("Attack block rate (Type-C events)")

    axes[1, 0].bar(x, ben, color="goldenrod")
    axes[1, 0].set_xticks(list(x))
    axes[1, 0].set_xticklabels(labels, rotation=60, ha="right", fontsize=6)
    axes[1, 0].set_ylabel("Benign false-block rate")
    axes[1, 0].set_title("Benign false blocks (non-attack)")

    axes[1, 1].bar(x, lat, color="darkseagreen")
    axes[1, 1].set_xticks(list(x))
    axes[1, 1].set_xticklabels(labels, rotation=60, ha="right", fontsize=6)
    axes[1, 1].set_ylabel("Median relay latency (ms)")
    axes[1, 1].set_title("Latency by combo")

    fig.tight_layout()
    path = os.path.join(out_dir, "ablation_by_combo.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("Wrote", path)


def plot_ablation_delta(delta_path, out_dir):
    """Bar chart of marginal deltas from ablation_delta.csv."""
    import matplotlib.pyplot as plt

    rows = _read_csv(delta_path)
    if not rows:
        return
    labels = [
        "%s|%s|%s" % (r.get("mode", ""), r.get("profile", ""), r.get("comparison", ""))
        for r in rows
    ]
    d_pol = [float(r.get("delta_pair_policy_accuracy") or 0) for r in rows]
    fig, ax = plt.subplots(figsize=(10, 5))
    x = range(len(labels))
    ax.bar(x, d_pol, color="slateblue")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=65, ha="right", fontsize=7)
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_ylabel("Delta policy accuracy (A - B)")
    ax.set_title("Marginal tier effects (see comparison labels)")
    fig.tight_layout()
    path = os.path.join(out_dir, "ablation_marginal_policy.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print("Wrote", path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--results-dir",
        default=os.path.join(os.path.dirname(__file__), "results"),
    )
    args = ap.parse_args()
    rd = args.results_dir
    fig_dir = os.path.join(rd, "figures")
    os.makedirs(fig_dir, exist_ok=True)

    try:
        import matplotlib  # noqa: F401
    except ImportError:
        print("Install matplotlib: pip install matplotlib", file=sys.stderr)
        sys.exit(1)

    by_mode = os.path.join(rd, "summary_by_mode.csv")
    by_combo = os.path.join(rd, "summary_by_combo.csv")
    ablation = os.path.join(rd, "ablation_delta.csv")
    events = os.path.join(rd, "events.csv")
    if os.path.isfile(by_mode):
        plot_accept_latency(by_mode, fig_dir)
    if os.path.isfile(by_combo):
        plot_ablation_combo(by_combo, fig_dir)
    if os.path.isfile(ablation):
        plot_ablation_delta(ablation, fig_dir)
    if os.path.isfile(events):
        plot_severity_events(events, fig_dir)
        plot_confusion(events, fig_dir)


if __name__ == "__main__":
    main()
