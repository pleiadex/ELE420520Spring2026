"""
Shared relay logic: poll vs control dispatch, P2 tier-1 band check, and optional
tier-2 linearized DC state sensitivity (from calculate_fdia.m H, W).
"""

import os
import time
import util

try:
    import physics_model

    _HAS_PHYSICS = physics_model.HAS_NUMPY
except ImportError:
    _HAS_PHYSICS = False

# Nominal P-injection setpoints (Table 1, Project 3)
NOMINAL_P_INJECTION = {
    13: 0.67,
    23: 1.63,
    33: 0.85,
    43: 0.00,
    53: -0.90,
    63: 0.00,
    73: -1.00,
    83: 0.00,
    93: -1.25,
}

MARGIN_PU = 1.0


def _tier2_enabled():
    v = os.environ.get("PROJECT5_TIER2", "1").lower()
    return v not in ("0", "false", "no", "off")


def _tier1_enabled():
    v = os.environ.get("PROJECT5_TIER1", "1").lower()
    return v not in ("0", "false", "no", "off")


def p2_tier1_check(target_index, setpoint):
    """Return (ok: bool, reason: str)."""
    if target_index not in NOMINAL_P_INJECTION:
        return False, "not_a_P_injection_index"
    nominal = NOMINAL_P_INJECTION[target_index]
    if abs(float(setpoint) - nominal) > MARGIN_PU + 1e-9:
        return False, "tier1_band_violation"
    return True, ""


def p2_tier2_check(target_index, setpoint):
    """
    Return (ok, reason, severity or None).
    If numpy unavailable, ok=True and reason tier2_skipped.
    """
    if not _HAS_PHYSICS:
        return True, "tier2_skipped_no_physics", None
    if not _tier2_enabled():
        return True, "tier2_disabled_env", None
    sev, detail = physics_model.tier2_severity(target_index, setpoint)
    if detail != "ok":
        return True, "tier2_skipped_%s" % detail, None
    thr = physics_model.tier2_threshold()
    if sev > thr + 1e-12:
        return False, "tier2_predicted_state_deviation", sev
    return True, "tier2_ok", sev


def _log_control_line(relay_id, target_index, setpoint, decision, reason, severity, t0):
    """CSV-friendly single line for experiment logs."""
    dt_ms = (time.time() - t0) * 1000.0
    sev = "" if severity is None else "%.6f" % severity
    line = (
        "PROJECT5,RELAY_CONTROL,relay=%d,idx=%d,sp=%.6f,decision=%s,reason=%s,severity=%s,latency_ms=%.3f"
        % (
            relay_id,
            target_index,
            float(setpoint),
            decision,
            reason,
            sev,
            dt_ms,
        )
    )
    print(line, flush=True)
    log_path = os.environ.get("PROJECT5_LOG_FILE")
    if log_path:
        try:
            with open(log_path, "a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except OSError:
            pass


def handle_message(data, measurements, relay_id=0):
    """
    Process one DNP3m request from the data aggregator.
    Returns (response_bytes, kind_str).
    """
    t0 = time.time()
    op = util.message_opcode(data)
    if op == util.REQ_POLL:
        req_indices = util.unpack_dnp3m_request(data)
        return util.pack_dnp3m_response(req_indices, measurements), "poll"
    if op == util.REQ_CONTROL:
        target_index, setpoint = util.unpack_dnp3m_control(data)
        if target_index not in measurements:
            _log_control_line(
                relay_id, target_index, setpoint, "reject", "wrong_relay", None, t0
            )
            return util.pack_control_ack(util.STATUS_REJECT), "control"

        if _tier1_enabled():
            ok1, r1 = p2_tier1_check(target_index, setpoint)
            if not ok1:
                print(
                    "Malicious Command Rejected: Predicted Physical Violation! (%s)"
                    % r1
                )
                _log_control_line(
                    relay_id, target_index, setpoint, "reject", r1, None, t0
                )
                return util.pack_control_ack(util.STATUS_REJECT), "control"
        else:
            r1 = "tier1_disabled_skip"

        ok2, r2, sev = p2_tier2_check(target_index, setpoint)
        if not ok2:
            print(
                "Malicious Command Rejected: Predicted Physical Violation! (%s, severity=%s)"
                % (r2, sev)
            )
            _log_control_line(
                relay_id, target_index, setpoint, "reject", r2, sev, t0
            )
            return util.pack_control_ack(util.STATUS_REJECT), "control"

        measurements[target_index] = setpoint
        print(
            "Control accepted: index %d set to %.4f (%s)"
            % (target_index, setpoint, r2)
        )
        _log_control_line(
            relay_id, target_index, setpoint, "accept", r2, sev, t0
        )
        return util.pack_control_ack(util.STATUS_OK), "control"
    raise ValueError("Unknown opcode: %s" % (op,))
