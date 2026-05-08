#!/usr/bin/env python3
"""
[A4 - AI-Generated]

Full experiment runner for Project 5.

Phase 1 — Mode/profile matrix (164 runs):
  4 modes x 4 tier configs x 3 profiles x 3 trials
  Logs written to results/raw/

Phase 2 — Stealthy-attack ablation (36 runs):
  3 scenarios (benign / stealthy 2.5 pu / gross 8.0 pu)
    x 4 tier configs x 3 trials
  Logs written to results/stealthy_raw/
  Summary written to results/stealthy_mininet.csv

Usage (run as root for Mininet):
  sudo python3 run_experiment_matrix.py --trials 3 --rounds 2 --skip-existing
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Phase 1 constants
# ---------------------------------------------------------------------------
MODES = ["baseline", "fdia_only", "typec_only", "combined"]

PROFILE_SETPOINTS = {
    "benign_nominal": 1.62,
    "boundary_safe_both": 2.0,
    "boundary_tier2_only": 2.5,
}

# ---------------------------------------------------------------------------
# Phase 2 constants
# ---------------------------------------------------------------------------
STEALTHY_SCENARIOS = [
    # (name, mode, malicious_sp_or_None, operator_sp)
    ("benign",   "baseline",   None, 1.62),
    ("stealthy", "typec_only", 2.50, 1.62),
    ("gross",    "typec_only", 8.00, 1.62),
]

STEALTHY_TIERS = [(True, True), (True, False), (False, True), (False, False)]

RELAY_RE = re.compile(
    r"^PROJECT5,RELAY_CONTROL,relay=(\d+),idx=(\d+),sp=([0-9.eE+-]+),"
    r"decision=(\w+),reason=([^,]+),severity=([^,]*),latency_ms=([0-9.eE+-]+)"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log_is_valid(path):
    """Minimal validity: full run + structured relay and DA lines."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fp:
            s = fp.read()
    except OSError:
        return False
    return (
        "PROJECT5,RUN_START" in s
        and "PROJECT5,RUN_END" in s
        and "PROJECT5,RELAY_CONTROL" in s
        and "PROJECT5,DA_CONTROL" in s
    )


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
                    "relay":      int(m.group(1)),
                    "idx":        int(m.group(2)),
                    "sp":         float(m.group(3)),
                    "decision":   m.group(4),
                    "reason":     m.group(5),
                    "severity":   float(sev) if sev else None,
                    "latency_ms": float(m.group(7)),
                })
    return out


def clear_mininet(prefix):
    subprocess.run(prefix + ["mn", "-c"],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL,
                   check=False)


# ---------------------------------------------------------------------------
# Phase 1: mode/profile matrix
# ---------------------------------------------------------------------------

def run_matrix_phase(args, proj, prefix):
    run_test = os.path.join(proj, "run_test.py")
    os.makedirs(args.raw_dir, exist_ok=True)

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    profile_names = [p.strip() for p in args.profiles.split(",") if p.strip()]

    def parse_tier(s):
        out = []
        for x in s.split(","):
            x = x.strip()
            if x in ("0", "1"):
                out.append(x == "1")
        return out if out else [True, False]

    tier1_opts = parse_tier(args.tier1_values)
    tier2_opts = parse_tier(args.tier2_values)

    total = (len(modes) * len(tier1_opts) * len(tier2_opts)
             * len(profile_names) * args.trials)
    print("\n=== Phase 1: Mode/Profile Matrix ===")
    print("  %d modes x %d tier1 x %d tier2 x %d profiles x %d trials = %d runs"
          % (len(modes), len(tier1_opts), len(tier2_opts),
             len(profile_names), args.trials, total))

    done = skipped = 0
    for mode in modes:
        for t1 in tier1_opts:
            for t2 in tier2_opts:
                for pname in profile_names:
                    if pname not in PROFILE_SETPOINTS:
                        print("Unknown profile %r, skip." % pname, file=sys.stderr)
                        continue
                    sp = PROFILE_SETPOINTS[pname]
                    for t in range(1, args.trials + 1):
                        log_name = "%s_t1%d_t2%d_%s_t%03d.log" % (
                            mode, 1 if t1 else 0, 1 if t2 else 0, pname, t)
                        log_path = os.path.join(args.raw_dir, log_name)
                        if args.skip_existing and log_is_valid(log_path):
                            skipped += 1
                            print("SKIP (valid): %s" % os.path.basename(log_path))
                            continue
                        cmd = prefix + [
                            sys.executable, run_test,
                            "--mode", mode,
                            "--rounds", str(args.rounds),
                            "--control-index", str(args.control_index),
                            "--control-setpoint", str(sp),
                            "--profile", pname,
                            "--log-file", log_path,
                        ]
                        if not t1:
                            cmd.append("--no-tier1")
                        if not t2:
                            cmd.append("--no-tier2")
                        if args.dry_run:
                            print("WOULD RUN:", " ".join(cmd))
                            done += 1
                            continue
                        print("--- %s t1=%d t2=%d profile=%s trial=%d ---"
                              % (mode, t1, t2, pname, t))
                        clear_mininet(prefix)
                        r = subprocess.run(cmd, cwd=proj)
                        if r.returncode != 0:
                            print("run_test failed (code %d)" % r.returncode,
                                  file=sys.stderr)
                            sys.exit(r.returncode)
                        done += 1

    print("Phase 1 done: runs=%d skipped=%d" % (done, skipped))


# ---------------------------------------------------------------------------
# Phase 2: stealthy-attack ablation
# ---------------------------------------------------------------------------

def run_stealthy_phase(args, proj, prefix):
    run_test = os.path.join(proj, "run_test.py")
    raw_dir = os.path.join(proj, "results", "stealthy_raw")
    out_csv = os.path.join(proj, "results", "stealthy_mininet.csv")
    os.makedirs(raw_dir, exist_ok=True)

    total = len(STEALTHY_SCENARIOS) * len(STEALTHY_TIERS) * args.trials
    print("\n=== Phase 2: Stealthy-Attack Ablation ===")
    print("  %d scenarios x %d tier configs x %d trials = %d runs"
          % (len(STEALTHY_SCENARIOS), len(STEALTHY_TIERS), args.trials, total))

    rows = []
    for scenario, mode, mal_sp, control_sp in STEALTHY_SCENARIOS:
        for t1, t2 in STEALTHY_TIERS:
            for trial in range(1, args.trials + 1):
                label = "%s_t1%d_t2%d_t%02d" % (
                    scenario, 1 if t1 else 0, 1 if t2 else 0, trial)
                log_path = os.path.join(raw_dir, label + ".log")

                if args.skip_existing and log_is_valid(log_path):
                    print("SKIP (valid): %s" % os.path.basename(log_path))
                else:
                    cmd = [
                        sys.executable, run_test,
                        "--mode", mode,
                        "--rounds", str(args.rounds),
                        "--control-index", "23",
                        "--control-setpoint", str(control_sp),
                        "--profile", scenario,
                        "--log-file", log_path,
                    ]
                    if not t1:
                        cmd.append("--no-tier1")
                    if not t2:
                        cmd.append("--no-tier2")
                    if args.dry_run:
                        print("WOULD RUN:", " ".join(cmd))
                        continue
                    env = os.environ.copy()
                    if mal_sp is not None:
                        env["PROJECT5_MALICIOUS_SP"] = str(mal_sp)
                    print("--- %s t1=%d t2=%d trial=%d ---"
                          % (scenario, t1, t2, trial))
                    clear_mininet(prefix)
                    r = subprocess.run(cmd, env=env, cwd=proj)
                    if r.returncode != 0:
                        print("  WARN run_test exit=%d" % r.returncode,
                              file=sys.stderr)

                relay_rows = parse_relay_lines(log_path)
                if not relay_rows:
                    rows.append({
                        "scenario": scenario, "mode": mode,
                        "malicious_sp": mal_sp if mal_sp is not None else "",
                        "tier1_on": t1, "tier2_on": t2, "trial": trial,
                        "decision": "missing", "reason": "no_relay_log",
                        "severity": "", "fwd_sp": "", "latency_ms": "",
                    })
                    continue
                first = relay_rows[0]
                rows.append({
                    "scenario": scenario, "mode": mode,
                    "malicious_sp": mal_sp if mal_sp is not None else "",
                    "tier1_on": t1, "tier2_on": t2, "trial": trial,
                    "decision": first["decision"],
                    "reason":   first["reason"],
                    "severity": first["severity"] if first["severity"] is not None else "",
                    "fwd_sp":   first["sp"],
                    "latency_ms": first["latency_ms"],
                })

    if not args.dry_run and rows:
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("Phase 2 done: %d rows -> %s" % (len(rows), out_csv))

        # Quick decision matrix printout
        print("\nDecision matrix (first trial of each cell):")
        print("%-10s %-6s %-6s %-8s %-7s" %
              ("scenario", "T1", "T2", "decision", "lat_ms"))
        seen = set()
        for r in rows:
            k = (r["scenario"], r["tier1_on"], r["tier2_on"])
            if k in seen:
                continue
            seen.add(k)
            print("%-10s %-6s %-6s %-8s %-7s" %
                  (r["scenario"], r["tier1_on"], r["tier2_on"],
                   r["decision"], str(r["latency_ms"])))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if os.geteuid() != 0:
        print("Must run as root (Mininet). Try: sudo python3 run_experiment_matrix.py",
              file=sys.stderr)
        sys.exit(1)

    ap = argparse.ArgumentParser(
        description="Run all Project 5 experiments (matrix + stealthy ablation)."
    )
    ap.add_argument("--trials", type=int, default=3, help="Runs per cell.")
    ap.add_argument("--rounds", type=int, default=2, help="CC poll/control rounds.")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--profiles", default=",".join(PROFILE_SETPOINTS.keys()))
    ap.add_argument("--tier1-values", default="1,0")
    ap.add_argument("--tier2-values", default="1,0")
    ap.add_argument("--raw-dir",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "results", "raw"))
    ap.add_argument("--control-index", type=int, default=23)
    ap.add_argument("--sudo", action="store_true",
                    help="Prefix commands with sudo -E.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Skip valid existing log files.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print planned runs without executing.")
    ap.add_argument("--skip-stealthy", action="store_true",
                    help="Skip Phase 2 stealthy-attack ablation.")
    ap.add_argument("--skip-matrix", action="store_true",
                    help="Skip Phase 1 mode/profile matrix.")
    args = ap.parse_args()

    proj = os.path.abspath(os.path.dirname(__file__))
    prefix = ["sudo", "-E"] if args.sudo else []

    t0 = time.time()

    if not args.skip_matrix:
        run_matrix_phase(args, proj, prefix)

    if not args.skip_stealthy:
        run_stealthy_phase(args, proj, prefix)

    print("\nAll experiments complete in %.1fs." % (time.time() - t0))
    print("Next: python3 analyze_results.py")


if __name__ == "__main__":
    main()
