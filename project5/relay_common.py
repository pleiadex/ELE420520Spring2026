"""
Shared relay logic: poll vs control dispatch and P2 tier-1 (HotSoS-style) checks.

Nominal real-power injections (pu, 100 MVA base) from docs/project3 Table 1 / calculate_fdia.m
"""

import util

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

# Allowed deviation from nominal (simplified operating envelope)
MARGIN_PU = 1.0


def p2_tier1_check(target_index, setpoint):
    """
    Return (ok: bool, reason: str).
    Reject if index is not a controllable P-injection or outside nominal +/- MARGIN_PU.
    """
    if target_index not in NOMINAL_P_INJECTION:
        return False, "not a P-injection index (specification whitelist)"
    nominal = NOMINAL_P_INJECTION[target_index]
    if abs(float(setpoint) - nominal) > MARGIN_PU + 1e-9:
        return (
            False,
            "setpoint %.4f outside safe band [%.4f, %.4f]"
            % (setpoint, nominal - MARGIN_PU, nominal + MARGIN_PU),
        )
    return True, ""


def handle_message(data, measurements):
    """
    Process one DNP3m request from the data aggregator.
    Returns (response_bytes, kind_str).
    """
    op = util.message_opcode(data)
    if op == util.REQ_POLL:
        req_indices = util.unpack_dnp3m_request(data)
        return util.pack_dnp3m_response(req_indices, measurements), "poll"
    if op == util.REQ_CONTROL:
        target_index, setpoint = util.unpack_dnp3m_control(data)
        if target_index not in measurements:
            print(
                "Control rejected: index %d not served by this relay."
                % target_index
            )
            return util.pack_control_ack(util.STATUS_REJECT), "control"
        ok, reason = p2_tier1_check(target_index, setpoint)
        if ok:
            measurements[target_index] = setpoint
            print("Control accepted: index %d set to %.4f" % (target_index, setpoint))
            return util.pack_control_ack(util.STATUS_OK), "control"
        print(
            "Malicious Command Rejected: Predicted Physical Violation! (%s)" % reason
        )
        return util.pack_control_ack(util.STATUS_REJECT), "control"
    raise ValueError("Unknown opcode: %s" % (op,))
