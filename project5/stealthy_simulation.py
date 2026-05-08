#!/usr/bin/env python3
"""
Direct (no-Mininet) simulation of stealthy Type-C attacks on the relay defense.

For each (malicious_setpoint, tier1_on, tier2_on) combination, invoke
`relay_common.handle_message` with a synthesized DNP3m control packet and
record the relay's accept/reject decision plus the predicted severity.

This isolates the defense logic from network emulation cost so we can sweep
many attack values quickly. The decision logic exercised here is the same
function used by relay1.py--relay4.py in the Mininet harness.
"""

import csv
import json
import os
import sys
import time

import util
import relay_common
import physics_model

# Index 23 (relay1, P-injection bus) — same target used in run_test.py
TARGET_INDEX = 23
NOMINAL = relay_common.NOMINAL_P_INJECTION[TARGET_INDEX]  # 1.63 pu

# Initial relay measurements (mirrors relay1.py defaults for index 23 area)
INIT_MEASUREMENTS = {13: 0.67, 23: 1.63, 33: 0.85}


def run_one(setpoint, tier1_on, tier2_on, label):
    os.environ["PROJECT5_TIER1"] = "1" if tier1_on else "0"
    os.environ["PROJECT5_TIER2"] = "1" if tier2_on else "0"

    sev, sev_detail = physics_model.tier2_severity(TARGET_INDEX, setpoint)

    measurements = dict(INIT_MEASUREMENTS)
    pkt = util.pack_dnp3m_control(TARGET_INDEX, float(setpoint))
    t0 = time.time()
    resp, kind = relay_common.handle_message(pkt, measurements, relay_id=1)
    latency_ms = (time.time() - t0) * 1000.0
    status = util.unpack_control_ack(resp)
    decision = "accept" if status == util.STATUS_OK else "reject"

    return {
        "label": label,
        "setpoint": float(setpoint),
        "delta_from_nominal": float(setpoint) - NOMINAL,
        "tier1_on": tier1_on,
        "tier2_on": tier2_on,
        "severity": None if sev is None else float(sev),
        "decision": decision,
        "latency_ms": latency_ms,
    }


def attack_scenarios():
    """Three attack types, each tested under all 4 tier configurations."""
    # Scenarios:
    # - benign: operator's intended setpoint (nominal +/- small jitter)
    # - stealthy: in-band but above tier-2 severity threshold
    # - gross: out-of-band malicious value (matches existing data_aggregator.py)
    return [
        ("benign",   1.62),
        ("stealthy", 2.50),   # inside [0.63, 2.63] but severity ~0.11 > 0.10
        ("gross",    8.00),   # original MALICIOUS_SETPOINT
    ]


def severity_sweep(lo=-1.5, hi=4.0, step=0.05):
    rows = []
    sp = lo
    while sp <= hi + 1e-9:
        sev, _ = physics_model.tier2_severity(TARGET_INDEX, sp)
        rows.append({
            "setpoint": float(sp),
            "delta_from_nominal": float(sp) - NOMINAL,
            "severity": None if sev is None else float(sev),
            "in_tier1_band": abs(sp - NOMINAL) <= relay_common.MARGIN_PU,
        })
        sp += step
    return rows


def main():
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)

    # 1) Ablation table — every (scenario x tier1 x tier2)
    ablation_rows = []
    for label, sp in attack_scenarios():
        for t1 in (True, False):
            for t2 in (True, False):
                ablation_rows.append(run_one(sp, t1, t2, label))

    abl_csv = os.path.join(out_dir, "stealthy_ablation.csv")
    with open(abl_csv, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(ablation_rows[0].keys()))
        w.writeheader()
        w.writerows(ablation_rows)
    print("Wrote", abl_csv, "(", len(ablation_rows), "rows )")

    # 2) Severity sweep — pure analytical, no relay invocation
    sweep_rows = severity_sweep()
    sweep_csv = os.path.join(out_dir, "severity_sweep.csv")
    with open(sweep_csv, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(sweep_rows[0].keys()))
        w.writeheader()
        w.writerows(sweep_rows)
    print("Wrote", sweep_csv, "(", len(sweep_rows), "rows )")

    # Console summary
    print("\nDecision matrix (scenario x tier config):")
    print("%-9s %-6s %-6s %-6s %-9s %-7s" %
          ("scenario", "T1", "T2", "decis", "severity", "lat_ms"))
    for r in ablation_rows:
        sev = "%.4f" % r["severity"] if r["severity"] is not None else "-"
        print("%-9s %-6s %-6s %-6s %-9s %-7s" %
              (r["label"], r["tier1_on"], r["tier2_on"],
               r["decision"], sev, "%.3f" % r["latency_ms"]))


if __name__ == "__main__":
    main()
