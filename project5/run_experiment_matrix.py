#!/usr/bin/env python3
"""
Full ablation matrix: modes x tier1 x tier2 x setpoint profiles, optional skip-existing.

Example:
  sudo python3 run_experiment_matrix.py --trials 3 --rounds 2 --sudo --skip-existing
"""

import argparse
import os
import subprocess
import sys

MODES = ["baseline", "fdia_only", "typec_only", "combined"]

# Setpoint profiles (index 23, nominal 1.63 pu, tier-1 band [0.63, 2.63]):
# - benign_nominal: typical lab command; tier1+ tier2 pass
# - boundary_safe_both: inside band, tier2 below threshold (~0.05 < 0.1)
# - boundary_tier2_only: inside tier-1 band but tier-2 rejects (severity ~0.12 > 0.1)
#   - shows tier-2 value when tier-1 alone would pass
PROFILE_SETPOINTS = {
    "benign_nominal": 1.62,
    "boundary_safe_both": 2.0,
    "boundary_tier2_only": 2.5,
}


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


def main():
    ap = argparse.ArgumentParser(
        description="Run full Project5 ablation matrix (Mininet + run_test)."
    )
    ap.add_argument("--trials", type=int, default=3, help="Runs per combo cell.")
    ap.add_argument("--rounds", type=int, default=2, help="CC poll/control rounds.")
    ap.add_argument(
        "--modes",
        default=",".join(MODES),
        help="Comma-separated modes (default: all four).",
    )
    ap.add_argument(
        "--profiles",
        default=",".join(PROFILE_SETPOINTS.keys()),
        help="Comma-separated profile names (see PROFILE_SETPOINTS in script).",
    )
    ap.add_argument(
        "--tier1-values",
        default="1,0",
        help="Comma-separated 0/1 for tier-1 on/off (default full ablation).",
    )
    ap.add_argument(
        "--tier2-values",
        default="1,0",
        help="Comma-separated 0/1 for tier-2 on/off (default full ablation).",
    )
    ap.add_argument(
        "--raw-dir",
        default=os.path.join(os.path.dirname(__file__), "results", "raw"),
    )
    ap.add_argument("--control-index", type=int, default=23)
    ap.add_argument(
        "--sudo",
        action="store_true",
        help="Prefix mn and run_test with sudo -E (typical on Mininet hosts).",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip a cell if the log file exists and passes log_is_valid().",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned runs only.",
    )
    args = ap.parse_args()

    proj = os.path.abspath(os.path.dirname(__file__))
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

    prefix = ["sudo", "-E"] if args.sudo else []
    run_test = os.path.join(proj, "run_test.py")

    total = (
        len(modes)
        * len(tier1_opts)
        * len(tier2_opts)
        * len(profile_names)
        * args.trials
    )
    print(
        "Matrix: %d modes x %d tier1 x %d tier2 x %d profiles x %d trials = %d runs"
        % (
            len(modes),
            len(tier1_opts),
            len(tier2_opts),
            len(profile_names),
            args.trials,
            total,
        )
    )

    done = 0
    skipped = 0

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
                            mode,
                            1 if t1 else 0,
                            1 if t2 else 0,
                            pname,
                            t,
                        )
                        log_path = os.path.join(args.raw_dir, log_name)
                        if args.skip_existing and os.path.isfile(log_path):
                            if log_is_valid(log_path):
                                skipped += 1
                                print(
                                    "SKIP (valid): %s"
                                    % os.path.basename(log_path)
                                )
                                continue
                        cmd = prefix + [
                            sys.executable,
                            run_test,
                            "--mode",
                            mode,
                            "--rounds",
                            str(args.rounds),
                            "--control-index",
                            str(args.control_index),
                            "--control-setpoint",
                            str(sp),
                            "--profile",
                            pname,
                            "--log-file",
                            log_path,
                        ]
                        if not t1:
                            cmd.append("--no-tier1")
                        if not t2:
                            cmd.append("--no-tier2")
                        if args.dry_run:
                            print("WOULD RUN:", " ".join(cmd))
                            done += 1
                            continue
                        print(
                            "=== %s t1=%d t2=%d profile=%s trial=%d ==="
                            % (mode, t1, t2, pname, t)
                        )
                        subprocess.run(prefix + ["mn", "-c"], cwd=proj, check=False)
                        r = subprocess.run(cmd, cwd=proj)
                        if r.returncode != 0:
                            print(
                                "run_test failed with code %d" % r.returncode,
                                file=sys.stderr,
                            )
                            sys.exit(r.returncode)
                        done += 1

    print(
        "Done. runs=%d skipped=%d raw=%s"
        % (done, skipped, args.raw_dir)
    )
    print("Next: python3 analyze_results.py && python3 plot_results.py")


if __name__ == "__main__":
    main()
