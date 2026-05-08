#!/usr/bin/env python3
"""
[A4 - AI-Generated]

Automated Mininet test: start relays, data aggregator, run control_center (auto demo).
Requires: mininet. Run: sudo python3 run_test.py [--mode ...]

Modes set PROJECT5_* for the child processes (data aggregator, control center).
"""

import argparse
import os
import subprocess
import sys
import time

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJ_DIR)


def _resolve_log_path(log_file_arg):
    """Absolute path anchored to this script's directory (not process cwd)."""
    if not log_file_arg:
        return ""
    if os.path.isabs(log_file_arg):
        return os.path.normpath(log_file_arg)
    return os.path.normpath(os.path.join(PROJ_DIR, log_file_arg))


def build_child_env(mode, control_index, control_sp, tier1, tier2):
    """Merge experiment flags into environment for hosts."""
    e = os.environ.copy()
    e["PROJECT5_MODE"] = mode
    e["PROJECT5_CONTROL_INDEX"] = str(control_index)
    e["PROJECT5_CONTROL_SP"] = str(control_sp)
    e["PROJECT5_TIER1"] = "1" if tier1 else "0"
    e["PROJECT5_TIER2"] = "1" if tier2 else "0"
    if mode == "baseline":
        e["PROJECT5_FDIA"] = "0"
        e["PROJECT5_TYPE_C"] = "0"
    elif mode == "fdia_only":
        e["PROJECT5_FDIA"] = "1"
        e["PROJECT5_TYPE_C"] = "0"
    elif mode == "typec_only":
        e["PROJECT5_FDIA"] = "0"
        e["PROJECT5_TYPE_C"] = "1"
    elif mode == "combined":
        e["PROJECT5_FDIA"] = "1"
        e["PROJECT5_TYPE_C"] = "1"
    else:
        # default: keep prior behavior
        e.setdefault("PROJECT5_FDIA", "1")
        e.setdefault("PROJECT5_TYPE_C", "0")
    return e


def main():
    parser = argparse.ArgumentParser(description="Mininet smoke / experiment harness.")
    parser.add_argument(
        "--mode",
        default="default",
        choices=[
            "default",
            "baseline",
            "fdia_only",
            "typec_only",
            "combined",
        ],
        help="Experiment mode (sets PROJECT5_FDIA / TYPE_C / MODE).",
    )
    parser.add_argument("--rounds", type=int, default=1, help="CC poll/control cycles.")
    parser.add_argument(
        "--control-index", type=int, default=23, help="Control target index."
    )
    parser.add_argument(
        "--control-setpoint",
        type=float,
        default=1.62,
        help="Benign control setpoint (pu).",
    )
    parser.add_argument(
        "--tier2",
        action="store_true",
        default=True,
        help="Enable tier-2 check in relays (default on).",
    )
    parser.add_argument(
        "--no-tier1",
        action="store_true",
        help="Set PROJECT5_TIER1=0 for ablation (default: tier-1 on).",
    )
    parser.add_argument(
        "--no-tier2",
        action="store_true",
        help="Set PROJECT5_TIER2=0 for ablation.",
    )
    parser.add_argument(
        "--profile",
        default="",
        help="Experiment profile tag (logged in RUN_START for analysis).",
    )
    parser.add_argument(
        "--log-file",
        default="",
        help="Append all stdout/stderr to this file.",
    )
    args = parser.parse_args()
    tier2 = not args.no_tier2
    tier1 = not args.no_tier1

    child_env = build_child_env(
        args.mode, args.control_index, args.control_setpoint, tier1, tier2
    )

    log_fp = None
    log_path = _resolve_log_path(args.log_file)
    if log_path:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        # Truncate once, then use append for parent + relays/DA so appends are visible
        # (keeping O_TRUNC open while children append can hide their writes on some setups).
        with open(log_path, "w", encoding="utf-8"):
            pass
        log_fp = open(log_path, "a", encoding="utf-8")
        child_env["PROJECT5_LOG_FILE"] = log_path

    def tee(line):
        sys.stdout.write(line)
        sys.stdout.flush()
        if log_fp:
            log_fp.write(line)
            log_fp.flush()

    def tee_stdout_only(line):
        """Console-only (avoid duplicating PROJECT5 lines already in the log file)."""
        sys.stdout.write(line)
        sys.stdout.flush()

    prof = args.profile or "unspecified"
    tee(
        "PROJECT5,RUN_START,mode=%s,rounds=%d,tier1=%d,tier2=%d,profile=%s,sp=%.6f\n"
        % (
            args.mode,
            args.rounds,
            1 if tier1 else 0,
            1 if tier2 else 0,
            prof,
            float(args.control_setpoint),
        )
    )

    from mininet.net import Mininet
    from mininet.node import Controller, OVSSwitch
    from mininet.log import setLogLevel

    setLogLevel("warning")

    net = Mininet(controller=Controller, switch=OVSSwitch)
    net.addController("c1")

    s1 = net.addSwitch("s1", mac=11)
    s2 = net.addSwitch("s2", mac=12)
    s3 = net.addSwitch("s3", mac=13)
    cc = net.addHost("cc", ip="10.0.0.1")
    da = net.addHost("da", ip="10.0.0.20")
    relay1 = net.addHost("relay1", ip="10.0.0.11")
    relay2 = net.addHost("relay2", ip="10.0.0.12")
    relay3 = net.addHost("relay3", ip="10.0.0.13")
    relay4 = net.addHost("relay4", ip="10.0.0.14")

    net.addLink(s1, s2)
    net.addLink(s2, s3)
    net.addLink(cc, s1)
    net.addLink(da, s2)
    net.addLink(relay1, s3)
    net.addLink(relay2, s3)
    net.addLink(relay3, s3)
    net.addLink(relay4, s3)

    net.start()
    proj_dir = PROJ_DIR

    try:
        for host, script in [
            (relay1, "relay1.py"),
            (relay2, "relay2.py"),
            (relay3, "relay3.py"),
            (relay4, "relay4.py"),
        ]:
            host.popen(
                ["python3", os.path.join(proj_dir, script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=child_env,
            )
            time.sleep(0.15)

        time.sleep(0.4)
        da.popen(
            ["python3", os.path.join(proj_dir, "data_aggregator.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=child_env,
        )
        time.sleep(0.5)

        cc_proc = cc.popen(
            [
                "python3",
                os.path.join(proj_dir, "control_center.py"),
                "--rounds",
                str(args.rounds),
                "--control-index",
                str(args.control_index),
                "--control-setpoint",
                str(args.control_setpoint),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=proj_dir,
            env=child_env,
        )
        out, _ = cc_proc.communicate(timeout=120)
        text = out.decode(errors="replace")
        tee(text)
        if log_path and os.path.isfile(log_path):
            with open(log_path, "r", encoding="utf-8") as fp:
                tail = fp.read()
            if "PROJECT5,RELAY_CONTROL" in tail:
                tee_stdout_only("\n--- Relay log excerpts (same file) ---\n")
                for ln in tail.splitlines():
                    if "PROJECT5,RELAY_CONTROL" in ln or "PROJECT5,CONFIG" in ln:
                        tee_stdout_only(ln + "\n")
    finally:
        net.stop()

    tee("PROJECT5,RUN_END,mode=%s\n" % args.mode)
    if log_fp:
        log_fp.close()
        log_fp = None


if __name__ == "__main__":
    main()
