"""
[A4 - AI-Generated]

DC state-estimation linear model from project5/calculate_fdia.m (H, W, z).

Tier-2 severity: predicted change in angle state ||?x||_inf when one P-injection
in z is hypothetically set to the commanded setpoint (other injections nominal).
"""

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# z order matches z_ind in calculate_fdia.m (P injections, pu)
Z_INDICES = [13, 23, 33, 43, 53, 63, 73, 83, 93]

# Nominal injection vector z (from calculate_fdia.m)
Z_NOMINAL = np.array(
    [0.67, 1.63, 0.85, 0.0, -0.90, 0.0, -1.00, 0.0, -1.25], dtype=float
)

# H matrix 9x8 (DC measurement Jacobian)
H = np.array(
    [
        [0, 0, -17.3611, 0, 0, 0, 0, 0],
        [16.0000, 0, 0, 0, 0, 0, -16.0000, 0],
        [0, 17.0648, 0, 0, -17.0648, 0, 0, 0],
        [0, 0, 39.9954, -10.8696, 0, 0, 0, -11.7647],
        [0, 0, -10.8696, 16.7519, -5.8824, 0, 0, 0],
        [0, -17.0648, 0, -5.8824, 32.8678, -9.9206, 0, 0],
        [0, 0, 0, 0, -9.9206, 23.8095, -13.8889, 0],
        [-16.0000, 0, 0, 0, 0, -13.8889, 36.1001, -6.2112],
        [0, 0, -11.7647, 0, 0, 0, -6.2112, 17.9759],
    ],
    dtype=float,
)

W = np.diag([100.0] * 9)

# G such that x_est = G @ z (8x9)
_G = None


def _get_gain_matrix():
    global _G
    if not HAS_NUMPY:
        return None
    if _G is not None:
        return _G
    gain = H.T @ W @ H
    _G = np.linalg.inv(gain) @ H.T @ W
    return _G


def index_to_z_row(target_index):
    """Map measurement index (13,23,...) to row 0..8 in z vector."""
    if target_index not in Z_INDICES:
        return None
    return Z_INDICES.index(target_index)


def tier2_severity(target_index, proposed_setpoint):
    """
    Return (severity_inf_norm, ok_detail).
    severity = || G @ (z' - z) ||_inf where z' replaces one P injection.
    """
    if not HAS_NUMPY:
        return None, "numpy_unavailable"
    row = index_to_z_row(target_index)
    if row is None:
        return None, "not_in_z_vector"
    G = _get_gain_matrix()
    dz = np.zeros(9, dtype=float)
    dz[row] = float(proposed_setpoint) - Z_NOMINAL[row]
    dx = G @ dz
    severity = float(np.linalg.norm(dx, ord=np.inf))
    return severity, "ok"


def tier2_threshold():
    """Threshold on inf-norm of predicted delta state; tuned for course demo."""
    return 0.10
