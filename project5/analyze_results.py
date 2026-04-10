#!/usr/bin/env python3
"""
Parse PROJECT5,* lines from experiment logs under results/raw/ and write:
  - results/summary.csv   (per-log aggregates)
  - results/events.csv    (paired relay + DA rows for confusion analysis)
"""

import argparse
import csv
import glob
import os
import re
import statistics
import sys

RELAY_RE = re.compile(
    r"^PROJECT5,RELAY_CONTROL,relay=(\d+),idx=(\d+),sp=([0-9.eE+-]+),"
    r"decision=(\w+),reason=([^,]+),severity=([^,]*),latency_ms=([0-9.eE+-]+)$"
)
DA_RE = re.compile(
    r"^PROJECT5,DA_CONTROL,mode=(\w+),idx=(\d+),orig_sp=([0-9.eE+-]+),"
    r"fwd_sp=([0-9.eE+-]+),type_c=(True|False),ack_status=(\d+),latency_ms=([0-9.eE+-]+)$"
)
CONFIG_RE_NEW = re.compile(
    r"^PROJECT5,CONFIG,mode=(\w+),fdia=(True|False),type_c=(True|False),"
    r"tier1_env=(\S+),tier2_env=(\S+)$"
)
CONFIG_RE_OLD = re.compile(
    r"^PROJECT5,CONFIG,mode=(\w+),fdia=(True|False),type_c=(True|False),tier2_env=(.+)$"
)
RUN_START_RE = re.compile(
    r"^PROJECT5,RUN_START,mode=(\w+),rounds=(\d+),tier1=([01]),tier2=([01]),"
    r"profile=([^,]+),sp=([0-9.eE+-]+)\s*$"
)
RUN_START_OLD = re.compile(
    r"^PROJECT5,RUN_START,mode=(\w+),rounds=(\d+)\s*$"
)


def _parse_float(s):
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_config_line(line):
    m = CONFIG_RE_NEW.match(line)
    if m:
        return {
            "mode": m.group(1),
            "fdia": m.group(2) == "True",
            "type_c": m.group(3) == "True",
            "tier1_env": m.group(4),
            "tier2_env": m.group(5),
        }
    m = CONFIG_RE_OLD.match(line)
    if m:
        return {
            "mode": m.group(1),
            "fdia": m.group(2) == "True",
            "type_c": m.group(3) == "True",
            "tier1_env": "",
            "tier2_env": m.group(4),
        }
    return None


def _parse_run_start_line(line):
    line = line.strip()
    m = RUN_START_RE.match(line)
    if m:
        return {
            "mode": m.group(1),
            "rounds": int(m.group(2)),
            "tier1_on": m.group(3) == "1",
            "tier2_on": m.group(4) == "1",
            "profile": m.group(5),
            "cc_sp": float(m.group(6)),
        }
    m = RUN_START_OLD.match(line)
    if m:
        return {
            "mode": m.group(1),
            "rounds": int(m.group(2)),
            "tier1_on": None,
            "tier2_on": None,
            "profile": "",
            "cc_sp": None,
        }
    return None


def parse_log(path):
    """Return dict with config, relay_rows, da_rows, run_start."""
    config = None
    relay_rows = []
    da_rows = []
    run_start = None
    with open(path, "r", encoding="utf-8", errors="replace") as fp:
        for line in fp:
            line = line.strip()
            if line.startswith("PROJECT5,RUN_START") and run_start is None:
                run_start = _parse_run_start_line(line)
                continue
            m = _parse_config_line(line)
            if m:
                config = m
                continue
            m = RELAY_RE.match(line)
            if m:
                sev_raw = m.group(6).strip()
                relay_rows.append(
                    {
                        "relay": int(m.group(1)),
                        "idx": int(m.group(2)),
                        "sp": float(m.group(3)),
                        "decision": m.group(4),
                        "reason": m.group(5),
                        "severity": _parse_float(sev_raw),
                        "latency_ms": float(m.group(7)),
                    }
                )
                continue
            m = DA_RE.match(line)
            if m:
                da_rows.append(
                    {
                        "mode": m.group(1),
                        "idx": int(m.group(2)),
                        "orig_sp": float(m.group(3)),
                        "fwd_sp": float(m.group(4)),
                        "type_c": m.group(5) == "True",
                        "ack_status": int(m.group(6)),
                        "latency_ms": float(m.group(7)),
                    }
                )
    return {
        "config": config,
        "relay": relay_rows,
        "da": da_rows,
        "run_start": run_start,
    }


def _env_is_on(s):
    if s is None or s == "":
        return True
    return str(s).lower() not in ("0", "false", "no", "off")


def summarize_file(path, data):
    """One summary row for summary.csv."""
    base = os.path.basename(path)
    cfg = data["config"] or {}
    rs = data.get("run_start") or {}
    rel = data["relay"]
    da = data["da"]

    tier1_on = rs.get("tier1_on")
    tier2_on = rs.get("tier2_on")
    if tier1_on is None:
        tier1_on = _env_is_on(cfg.get("tier1_env", "1"))
    if tier2_on is None:
        tier2_on = _env_is_on(cfg.get("tier2_env", "1"))
    profile = rs.get("profile") or ""
    cc_sp = rs.get("cc_sp")
    if cc_sp is None:
        cc_sp = ""
    n_rel = len(rel)
    n_acc = sum(1 for r in rel if r["decision"] == "accept")
    n_rej = sum(1 for r in rel if r["decision"] == "reject")
    lat_r = [r["latency_ms"] for r in rel]
    lat_d = [r["latency_ms"] for r in da]
    sev_acc = [r["severity"] for r in rel if r["decision"] == "accept" and r["severity"] is not None]
    sev_rej = [r["severity"] for r in rel if r["decision"] == "reject" and r["severity"] is not None]

    def med(xs):
        return statistics.median(xs) if xs else ""

    # Pair by order (same control rounds)
    paired = min(len(rel), len(da))
    correct = 0
    for i in range(paired):
        attack = da[i]["type_c"]
        blocked = rel[i]["decision"] == "reject"
        if attack and blocked:
            correct += 1
        if (not attack) and (not blocked):
            correct += 1
    pair_accuracy = correct / paired if paired else ""

    atk_tot = atk_blk = ben_tot = ben_blk = 0
    for i in range(paired):
        attack = da[i]["type_c"]
        blocked = rel[i]["decision"] == "reject"
        if attack:
            atk_tot += 1
            if blocked:
                atk_blk += 1
        else:
            ben_tot += 1
            if blocked:
                ben_blk += 1
    attack_block_rate = (atk_blk / atk_tot) if atk_tot else ""
    benign_false_block_rate = (ben_blk / ben_tot) if ben_tot else ""

    return {
        "log_file": base,
        "mode": cfg.get("mode", ""),
        "fdia": cfg.get("fdia", ""),
        "type_c": cfg.get("type_c", ""),
        "tier1_env": cfg.get("tier1_env", ""),
        "tier2_env": cfg.get("tier2_env", ""),
        "tier1_on": tier1_on,
        "tier2_on": tier2_on,
        "profile": profile,
        "cc_setpoint": cc_sp,
        "n_relay_lines": n_rel,
        "n_accept": n_acc,
        "n_reject": n_rej,
        "accept_rate": (n_acc / n_rel) if n_rel else "",
        "median_relay_latency_ms": med(lat_r),
        "median_da_latency_ms": med(lat_d),
        "median_severity_accepted": med([s for s in sev_acc if s is not None]),
        "median_severity_rejected": med([s for s in sev_rej if s is not None]),
        "paired_controls": paired,
        "pair_policy_accuracy": pair_accuracy,
        "attack_block_rate": attack_block_rate,
        "benign_false_block_rate": benign_false_block_rate,
    }


def write_events_csv(paths, out_path):
    """Per-control event rows for confusion-style analysis."""
    fieldnames = [
        "log_file",
        "event_index",
        "mode",
        "profile",
        "tier1_on",
        "tier2_on",
        "type_c_attack",
        "fwd_sp",
        "relay_decision",
        "relay_reason",
        "severity",
        "da_ack_status",
        "expected_block_attack",
        "policy_ok",
    ]
    rows = []
    for path in paths:
        data = parse_log(path)
        cfg = data["config"] or {}
        rs = data.get("run_start") or {}
        mode = cfg.get("mode", "")
        profile = rs.get("profile") or ""
        t1 = rs.get("tier1_on")
        t2 = rs.get("tier2_on")
        if t1 is None:
            t1 = _env_is_on(cfg.get("tier1_env", "1"))
        if t2 is None:
            t2 = _env_is_on(cfg.get("tier2_env", "1"))
        rel = data["relay"]
        da = data["da"]
        n = min(len(rel), len(da))
        for i in range(n):
            attack = da[i]["type_c"]
            dec = rel[i]["decision"]
            blocked = dec == "reject"
            if attack:
                policy_ok = blocked
                expected = "block_malicious_forward"
            else:
                policy_ok = not blocked
                expected = "allow_benign"
            rows.append(
                {
                    "log_file": os.path.basename(path),
                    "event_index": i,
                    "mode": mode,
                    "profile": profile,
                    "tier1_on": t1,
                    "tier2_on": t2,
                    "type_c_attack": attack,
                    "fwd_sp": da[i]["fwd_sp"],
                    "relay_decision": dec,
                    "relay_reason": rel[i]["reason"],
                    "severity": rel[i]["severity"] if rel[i]["severity"] is not None else "",
                    "da_ack_status": da[i]["ack_status"],
                    "expected_block_attack": expected,
                    "policy_ok": policy_ok,
                }
            )
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_confusion_table(events_path, out_path):
    """2x2 CSV: benign/attack x accept/reject counts + policy accuracy."""
    rows = []
    with open(events_path, newline="", encoding="utf-8") as fp:
        rows = list(csv.DictReader(fp))
    tb = {"benign_allow": 0, "benign_block": 0, "attack_allow": 0, "attack_block": 0}
    ok = 0
    for r in rows:
        attack = r.get("type_c_attack", "").lower() == "true"
        blocked = r.get("relay_decision") == "reject"
        if r.get("policy_ok", "").lower() == "true":
            ok += 1
        if not attack and not blocked:
            tb["benign_allow"] += 1
        elif not attack and blocked:
            tb["benign_block"] += 1
        elif attack and not blocked:
            tb["attack_allow"] += 1
        else:
            tb["attack_block"] += 1
    n = len(rows)
    acc = ok / n if n else 0.0
    fieldnames = [
        "benign_forwarded",
        "benign_blocked",
        "attack_forwarded",
        "attack_blocked",
        "n_events",
        "policy_accuracy",
    ]
    out = {
        "benign_forwarded": tb["benign_allow"],
        "benign_blocked": tb["benign_block"],
        "attack_forwarded": tb["attack_allow"],
        "attack_blocked": tb["attack_block"],
        "n_events": n,
        "policy_accuracy": acc,
    }
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        w.writerow(out)


def aggregate_by_mode(summary_rows):
    """Return list of dicts: one row per mode with pooled stats."""
    from collections import defaultdict

    by = defaultdict(list)
    for r in summary_rows:
        m = r.get("mode") or "unknown"
        by[m].append(r)

    agg = []
    for mode, rs in sorted(by.items()):
        n_logs = len(rs)
        acc_rates = [float(x["accept_rate"]) for x in rs if x["accept_rate"] != ""]
        med_rel = [
            float(x["median_relay_latency_ms"])
            for x in rs
            if x["median_relay_latency_ms"] != ""
        ]
        pair_acc = [
            float(x["pair_policy_accuracy"])
            for x in rs
            if x["pair_policy_accuracy"] != ""
        ]
        agg.append(
            {
                "mode": mode,
                "n_log_files": n_logs,
                "mean_accept_rate": statistics.mean(acc_rates) if acc_rates else "",
                "median_of_median_relay_latency_ms": statistics.median(med_rel) if med_rel else "",
                "mean_pair_policy_accuracy": statistics.mean(pair_acc) if pair_acc else "",
            }
        )
    return agg


def aggregate_by_combo(summary_rows):
    """Pool stats by (mode, profile, tier1_on, tier2_on)."""
    from collections import defaultdict

    by = defaultdict(list)
    for r in summary_rows:
        key = (
            r.get("mode") or "",
            r.get("profile") or "",
            r.get("tier1_on"),
            r.get("tier2_on"),
        )
        by[key].append(r)

    agg = []
    for key in sorted(by.keys(), key=lambda x: (x[0], x[1], str(x[2]), str(x[3]))):
        mode, prof, t1, t2 = key
        rs = by[key]
        n_logs = len(rs)
        acc_rates = [float(x["accept_rate"]) for x in rs if x.get("accept_rate") != ""]
        pair_acc = [
            float(x["pair_policy_accuracy"])
            for x in rs
            if x.get("pair_policy_accuracy") != ""
        ]
        atk_br = [
            float(x["attack_block_rate"])
            for x in rs
            if x.get("attack_block_rate") != ""
        ]
        ben_fb = [
            float(x["benign_false_block_rate"])
            for x in rs
            if x.get("benign_false_block_rate") != ""
        ]
        med_rel = [
            float(x["median_relay_latency_ms"])
            for x in rs
            if x.get("median_relay_latency_ms") != ""
        ]

        def mean(xs):
            return statistics.mean(xs) if xs else ""

        agg.append(
            {
                "mode": mode,
                "profile": prof,
                "tier1_on": t1,
                "tier2_on": t2,
                "n_log_files": n_logs,
                "mean_accept_rate": mean(acc_rates),
                "mean_pair_policy_accuracy": mean(pair_acc),
                "mean_attack_block_rate": mean(atk_br),
                "mean_benign_false_block_rate": mean(ben_fb),
                "median_of_median_relay_latency_ms": statistics.median(med_rel)
                if med_rel
                else "",
            }
        )
    return agg


def _mean_field(rows, field):
    xs = [
        float(x[field])
        for x in rows
        if x.get(field) != "" and x.get(field) is not None
    ]
    return statistics.mean(xs) if xs else None


def write_ablation_delta(summary_rows, out_path):
    """
    Marginal effects: compare adjacent tier toggles at fixed other tier.
    Uses per-file summary rows grouped by (mode, profile, tier1_on, tier2_on).
    """
    from collections import defaultdict

    idx = defaultdict(list)
    for r in summary_rows:
        key = (
            r.get("mode"),
            r.get("profile") or "",
            r.get("tier1_on"),
            r.get("tier2_on"),
        )
        idx[key].append(r)

    keys_mp = set((r.get("mode"), r.get("profile") or "") for r in summary_rows)
    rows_out = []
    for mode, prof in sorted(keys_mp):

        def cell(t1, t2):
            k = (mode, prof, t1, t2)
            rs = idx.get(k)
            if not rs:
                return None
            return {
                "pol": _mean_field(rs, "pair_policy_accuracy"),
                "atk": _mean_field(rs, "attack_block_rate"),
                "ben": _mean_field(rs, "benign_false_block_rate"),
                "lat": _mean_field(rs, "median_relay_latency_ms"),
            }

        c11, c10, c01, c00 = cell(True, True), cell(True, False), cell(False, True), cell(
            False, False
        )

        def diff(a, b, name):
            if a is None or b is None:
                return
            rows_out.append(
                {
                    "mode": mode,
                    "profile": prof,
                    "comparison": name,
                    "delta_pair_policy_accuracy": (a["pol"] - b["pol"])
                    if a["pol"] is not None and b["pol"] is not None
                    else "",
                    "delta_attack_block_rate": (a["atk"] - b["atk"])
                    if a["atk"] is not None and b["atk"] is not None
                    else "",
                    "delta_benign_false_block_rate": (a["ben"] - b["ben"])
                    if a["ben"] is not None and b["ben"] is not None
                    else "",
                    "delta_median_relay_latency_ms": (a["lat"] - b["lat"])
                    if a["lat"] is not None and b["lat"] is not None
                    else "",
                }
            )

        # Tier-2 on vs off (marginal), holding tier-1 on
        if c11 and c10:
            diff(c11, c10, "tier2_on_minus_off_at_tier1_on")
        if c01 and c00:
            diff(c01, c00, "tier2_on_minus_off_at_tier1_off")
        # Tier-1 on vs off, holding tier-2 on
        if c11 and c01:
            diff(c11, c01, "tier1_on_minus_off_at_tier2_on")
        if c10 and c00:
            diff(c10, c00, "tier1_on_minus_off_at_tier2_off")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fieldnames = [
        "mode",
        "profile",
        "comparison",
        "delta_pair_policy_accuracy",
        "delta_attack_block_rate",
        "delta_benign_false_block_rate",
        "delta_median_relay_latency_ms",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)


def main():
    ap = argparse.ArgumentParser(description="Summarize Project5 experiment logs.")
    ap.add_argument(
        "--raw-dir",
        default=os.path.join(os.path.dirname(__file__), "results", "raw"),
        help="Directory containing *.log files",
    )
    ap.add_argument(
        "--summary",
        default=os.path.join(os.path.dirname(__file__), "results", "summary.csv"),
    )
    ap.add_argument(
        "--events",
        default=os.path.join(os.path.dirname(__file__), "results", "events.csv"),
    )
    ap.add_argument(
        "--by-mode",
        default=os.path.join(os.path.dirname(__file__), "results", "summary_by_mode.csv"),
    )
    ap.add_argument(
        "--confusion",
        default=os.path.join(os.path.dirname(__file__), "results", "confusion_table.csv"),
    )
    ap.add_argument(
        "--by-combo",
        default=os.path.join(os.path.dirname(__file__), "results", "summary_by_combo.csv"),
    )
    ap.add_argument(
        "--ablation-delta",
        default=os.path.join(os.path.dirname(__file__), "results", "ablation_delta.csv"),
    )
    args = ap.parse_args()

    pattern = os.path.join(args.raw_dir, "*.log")
    paths = sorted(glob.glob(pattern))
    if not paths:
        print("No logs matching %s" % pattern, file=sys.stderr)
        sys.exit(1)

    summary_rows = []
    for p in paths:
        data = parse_log(p)
        summary_rows.append(summarize_file(p, data))

    os.makedirs(os.path.dirname(args.summary) or ".", exist_ok=True)
    if summary_rows:
        keys = list(summary_rows[0].keys())
        with open(args.summary, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            w.writerows(summary_rows)

    write_events_csv(paths, args.events)
    write_confusion_table(args.events, args.confusion)

    agg = aggregate_by_mode(summary_rows)
    if agg:
        keys = list(agg[0].keys())
        with open(args.by_mode, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            w.writerows(agg)

    agg_combo = aggregate_by_combo(summary_rows)
    if agg_combo:
        keys = list(agg_combo[0].keys())
        with open(args.by_combo, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            w.writerows(agg_combo)

    write_ablation_delta(summary_rows, args.ablation_delta)

    print("Wrote %s (%d rows)" % (args.summary, len(summary_rows)))
    print("Wrote %s" % args.events)
    print("Wrote %s (%d modes)" % (args.by_mode, len(agg)))
    print("Wrote %s (%d combos)" % (args.by_combo, len(agg_combo)))
    print("Wrote %s" % args.ablation_delta)
    print("Wrote %s" % args.confusion)


if __name__ == "__main__":
    main()
