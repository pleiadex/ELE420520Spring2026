#!/usr/bin/env python3
"""
Mininet-based stealthy-attack ablation: drives run_test.py through every
(scenario x tier1 x tier2) cell, parses the resulting structured logs, and
emits a single CSV (results/stealthy_mininet.csv) consumed by the paper plot.

Usage:
    sudo python3 run_stealthy_mininet.py [--trials 3]

Scenarios:
    benign   : baseline mode, operator sets sp=1.62 (no MitM)
    stealthy : typec_only with MALICIOUS_SETPOINT=2.50 (in-band)
    gross    : typec_only with MALICIOUS_SETPOINT=8.00 (out-of-band)
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(PROJ, "results", "stealthy_raw")
OUT_CSV = os.path.join(PROJ, "results", "stealthy_mininet.csv")

SCENARIOS = [
    # name,    mode,         malicious_sp, control_sp
    ("benign",   "baseline",   None, 1.62),
    ("stealthy", "typec_only", 2.50, 1.62),
    ("gross",    "typec_only", 8.00, 1.62),
]

TIERS = [(True, True), (True, False), (False, True), (False, False)]

RELAY_RE = re.compile(
    r"^PROJECT5,RELAY_CONTROL,relay=(\d+),idx=(\d+),sp=([0-9.eE+-]+),"
    r"decision=(\w+),reason=([^,]+),severity=([^,]*),latency_ms=([0-9.eE+-]+)"
)


def run_one(scenario, mode, mal_sp, control_sp, t1, t2, trial):
    label = "%s_t1%d_t2%d_t%02d" % (
        scenario, 1 if t1 else 0, 1 if t2 else 0, trial,
    )
    log_path = os.path.join(RAW_DIR, label + ".log")
    cmd = [
        "python3", os.path.join(PROJ, "run_test.py"),
        "--mode", mode,
        "--rounds", "2",
        "--control-index", "23",
        "--control-setpoint", str(control_sp),
        "--profile", scenario,
        "--log-file", log_path,
    ]
    if not t1:
        cmd.append("--no-tier1")
    if not t2:
        cmd.append("--no-tier2")

    env = os.environ.copy()
    if mal_sp is not None:
        env["PROJECT5_MALICIOUS_SP"] = str(mal_sp)
    # Clean stale Mininet state before every run
    subprocess.run(["mn", "-c"], stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    print("=== %s ===" % label, flush=True)
    r = subprocess.run(cmd, env=env, cwd=PROJ)
    if r.returncode != 0:
        print("  WARN run_test exit=%d" % r.returncode, file=sys.stderr)
    return log_path


def parse_relay_lines(log_path):
    out = []
    if not os.path.isfile(log_path):
        return out
    with open(log_path, "r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            m = RELAY_RE.match(line.strip())
            if m:
                sev = m.group(6).strip()
                out.append({
                    "relay":   int(m.group(1)),
                    "idx":     int(m.group(2)),
                    "sp":      float(m.group(3)),
                    "decision": m.group(4),
                    "reason":  m.group(5),
                    "severity": float(sev) if sev else None,
                    "latency_ms": float(m.group(7)),
                })
    return out


def main():
    if os.geteuid() != 0:
        print("Must run as root (Mininet). Try: sudo python3 run_stealthy_mininet.py",
              file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    args = ap.parse_args()

    os.makedirs(RAW_DIR, exist_ok=True)
    rows = []
    t0 = time.time()
    for scenario, mode, mal_sp, control_sp in SCENARIOS:
        for t1, t2 in TIERS:
            for trial in range(1, args.trials + 1):
                log_path = run_one(scenario, mode, mal_sp, control_sp,
                                   t1, t2, trial)
                relay_rows = parse_relay_lines(log_path)
                # Use the first control event in each run as the canonical
                # observation (every round in our 2-round runs is identical).
                if not relay_rows:
                    rows.append({
                        "scenario": scenario,
                        "mode":     mode,
                        "malicious_sp": mal_sp if mal_sp is not None else "",
                        "tier1_on": t1,
                        "tier2_on": t2,
                        "trial":    trial,
                        "decision": "missing",
                        "reason":   "no_relay_log",
                        "severity": "",
                        "fwd_sp":   "",
                        "latency_ms": "",
                    })
                    continue
                first = relay_rows[0]
                rows.append({
                    "scenario": scenario,
                    "mode":     mode,
                    "malicious_sp": mal_sp if mal_sp is not None else "",
                    "tier1_on": t1,
                    "tier2_on": t2,
                    "trial":    trial,
                    "decision": first["decision"],
                    "reason":   first["reason"],
                    "severity": first["severity"] if first["severity"] is not None else "",
                    "fwd_sp":   first["sp"],
                    "latency_ms": first["latency_ms"],
                })

    fieldnames = list(rows[0].keys())
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    dt = time.time() - t0
    print("\nWrote %s (%d rows) in %.1fs" % (OUT_CSV, len(rows), dt))

    # Print decision matrix for quick inspection
    print("\nDecision matrix (first trial of each cell):")
    print("%-9s %-6s %-6s %-7s %-9s %-7s" %
          ("scenario", "T1", "T2", "decis", "fwd_sp", "lat_ms"))
    seen = set()
    for r in rows:
        k = (r["scenario"], r["tier1_on"], r["tier2_on"])
        if k in seen:
            continue
        seen.add(k)
        print("%-9s %-6s %-6s %-7s %-9s %-7s" %
              (r["scenario"], r["tier1_on"], r["tier2_on"],
               r["decision"], str(r["fwd_sp"]), str(r["latency_ms"])))


if __name__ == "__main__":
    main()
