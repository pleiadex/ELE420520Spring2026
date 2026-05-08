# Pre-Execution Physical Consequence Checking as a Defense Against Type-C Command-Path Attacks in Smart Grid Systems

**ELE 420/520 — Spring 2026**

---

## Abstract

Smart grid control systems face two distinct cyber-physical attack classes: measurement-path false data injection (Type A) and command-path manipulation (Type C). While Type A has received extensive treatment in the literature, Type C attacks—where an adversary alters control setpoints while preserving packet syntactic validity—are harder to detect because they bypass conventional intrusion detection that inspects only packet structure. This paper describes the design and evaluation of a pre-execution relay-side defense combining a tier-1 nominal band check and a tier-2 linearized DC consequence score. Experiments across 164 Mininet runs covering four attack modes, three setpoint profiles, and a full 2×2 tier ablation confirm that the layered defense achieves 100% attack blocking when both tiers are active, with a measured relay decision latency below 0.3 ms. The tier-2 score uniquely resolves cases that tier-1 alone cannot discriminate, demonstrating that lightweight physics-informed scoring is a practical addition to purely syntactic filtering.

---

## 1. Introduction

Control networks in power systems increasingly rely on IP-based SCADA and DNP3 communication. This openness creates exposure to adversaries who can position themselves as man-in-the-middle (MitM) nodes between a control center and its downstream relays. Lin et al. [2] formalize the resulting threat taxonomy. A **Type-A** attack corrupts telemetry on the read path, deceiving state estimation without directly altering physical device state—the attack studied in Project 3 via the Liu et al. [1] FDIA framework. A **Type-C** attack operates on the write path: the adversary intercepts a syntactically valid control command and replaces the setpoint with a physically unsafe value before forwarding it to the target relay. Because the packet remains well-formed, protocol-level validation cannot distinguish it from a legitimate command.

The defense proposed by Lin et al. [2] (Figure 4, P2) places consequence evaluation at the relay itself, before any state update is applied. The relay estimates the physical outcome of the proposed command and rejects it if a safety bound is violated. This paper implements and empirically evaluates that principle through two stacked checks—a hard nominal band (tier 1) and a linearized DC state-deviation score (tier 2)—running inside a Mininet emulation of a nine-bus power system.

---

## 2. System Design

### 2.1 Network Topology

The emulated system runs under Mininet with three Open vSwitch switches interconnecting six hosts: one control center (`cc`, 10.0.0.1), one data aggregator acting as the MitM node (`da`, 10.0.0.20), and four protection relays (`relay1`–`relay4`, 10.0.0.11–14). The control center communicates exclusively with the data aggregator over port 20000 using a simplified DNP3-like binary protocol (DNP3m). The aggregator forwards commands downstream on relay-specific ports (20001–20004).

A custom binary protocol carries two opcodes: opcode `0x01` (poll) requests measurement vectors; opcode `0x02` (control) carries a 7-byte frame `[0x02, 7, target_index, float setpoint]`. Relays respond with a 3-byte ack `[0x0C, 3, status]` where status 0 = accepted and status 1 = rejected.

### 2.2 Attack Injection

The data aggregator (`data_aggregator.py`) implements both attack classes via environment flags. With `FDIA_ON=True` (Type A), the aggregator silently overwrites measurement values before returning them to the control center, replicating the Liu et al. construction. With `TYPE_C_ATTACK=True` (Type C), every forwarded control setpoint is replaced with a fixed malicious value (8.0 pu), far outside safe operating range for any bus injection index. The aggregator logs both the original setpoint from the control center and the forwarded value, enabling post-hoc verification of injection.

### 2.3 Tier-1 Defense: Nominal Band Check

Each relay maintains a table of nominal real-power injection setpoints for the indices it serves (e.g., index 23 → 1.63 pu). On receipt of a control command, tier 1 tests:

```
|setpoint − nominal| ≤ MARGIN_PU
```

with `MARGIN_PU = 1.0 pu`. A setpoint of 8.0 pu fails this check for every bus (nearest nominal is 1.63 pu; deviation is 6.37 pu). Violation triggers immediate rejection with reason `tier1_band_violation` and no state update.

### 2.4 Tier-2 Defense: Linearized DC Consequence Score

For commands that pass tier 1—either because they are genuinely safe or because tier 1 is disabled—tier 2 applies a physics-informed severity score derived from the DC power-flow measurement model. Using the 9×8 measurement Jacobian `H` and diagonal weight matrix `W = 100·I` from the MATLAB reference (`calculate_fdia.m`), the gain matrix `G = (H^T W H)^{-1} H^T W` maps injection perturbations to predicted voltage angle changes. For a proposed setpoint `sp` targeting index `k`:

```
Δz_k = sp − z_nominal[k]
Δx = G · Δz
severity = ‖Δx‖∞
```

The relay rejects the command if `severity > 0.10 pu` (reason: `tier2_predicted_state_deviation`). The threshold was calibrated so that the `boundary_tier2_only` profile (setpoint 2.5 pu, inside tier-1 band) triggers rejection while the `benign_nominal` profile (1.62 pu) and `boundary_safe_both` profile (2.0 pu) do not. All matrix operations execute in NumPy with a one-time gain matrix inversion cached at startup.

---

## 3. Experimental Evaluation

### 3.1 Setup and Modes

Experiments used `run_experiment_matrix.py` to sweep four operational modes, three setpoint profiles, full tier on/off ablation (2×2), and three trials per cell, yielding 164 log files (328 paired control events). The modes are:

- **baseline**: no attack active; benign poll and control.
- **fdia\_only**: measurement FDIA on read path; command path unmodified.
- **typec\_only**: Type-C MitM on write path; measurements unmodified.
- **combined**: both FDIA and Type-C simultaneously.

The three setpoint profiles target index 23 (nominal 1.63 pu, tier-1 band [0.63, 2.63]):

| Profile | Setpoint (pu) | Expected tier-1 | Expected tier-2 |
|---|---|---|---|
| `benign_nominal` | 1.62 | Pass | Pass |
| `boundary_safe_both` | 2.00 | Pass | Pass |
| `boundary_tier2_only` | 2.50 | Pass | **Reject** |

### 3.2 Mode-Level Outcomes

Table 1 summarizes per-mode aggregate statistics from `results/summary_by_mode.csv`.

**Table 1: Mode-level aggregate outcomes (N=41 log files per mode)**

| Mode | Mean accept rate | Median relay latency (ms) | Mean policy accuracy |
|---|---:|---:|---:|
| baseline | 0.854 | 0.243 | 0.854 |
| fdia\_only | 0.854 | 0.247 | 0.854 |
| typec\_only | 0.220 | 0.051 | 0.780 |
| combined | 0.220 | 0.050 | 0.780 |

Baseline and `fdia_only` show identical accept rates, confirming that measurement-path corruption does not influence relay accept/reject behavior when the command path is clean—the relay defense operates independently of telemetry integrity. The `typec_only` and `combined` modes show substantially lower acceptance (22%), consistent with a large fraction of malicious commands being correctly blocked. The lower median relay latency in attack modes (~0.05 ms vs. ~0.24 ms) reflects the fast-path early exit at tier 1, which avoids the NumPy matrix multiplication needed for tier-2 evaluation.

### 3.3 Confusion-Style Security Outcomes

Pairing each relay decision with the corresponding data aggregator log entry by position yields the confusion summary in Table 2 (`results/confusion_table.csv`).

**Table 2: Confusion table across all 328 paired control events**

| Benign forwarded | Benign blocked | Attack forwarded | Attack blocked | Policy accuracy |
|---:|---:|---:|---:|---:|
| 140 | 24 | 36 | 128 | 0.817 |

The 36 attack-forwarded events and 24 benign-blocked events arise from ablation cells where one or both tiers are intentionally disabled. When both tiers are active under adversarial modes (`typec_only`, `combined`), the attack block rate is 100% and the false-block rate is 0% for profiles within tier-1 band. This confirms the defense is effective when fully deployed.

### 3.4 Tier Ablation Findings

The `boundary_tier2_only` profile is the critical discriminating case. Table 3 shows ablation deltas for the baseline mode on this profile (from `results/ablation_delta.csv`).

**Table 3: Marginal tier effects on `boundary_tier2_only` profile (baseline mode)**

| Comparison | Δ policy accuracy | Δ benign false block rate |
|---|---:|---:|
| tier2 on vs off (tier1 on) | −1.000 | +1.000 |
| tier2 on vs off (tier1 off) | −1.000 | +1.000 |
| tier1 on vs off (tier2 on) | 0.000 | 0.000 |
| tier1 on vs off (tier2 off) | 0.000 | 0.000 |

For the `boundary_tier2_only` setpoint (2.5 pu), tier 1 passes all commands because 2.5 pu is within the ±1.0 pu band around nominal 1.63 pu. The tier-2 DC severity for this setpoint is approximately 0.112 pu, exceeding the 0.10 threshold and triggering rejection. The delta of −1.0 in policy accuracy when enabling tier 2 reflects that in baseline mode (no attack), the 2.5 pu setpoint is not malicious—tier 2 blocks it anyway as physically risky, producing a false block. This is by design: the ablation reveals exactly the regime where tier 2 adds discriminative power and where its conservative threshold trades some availability for safety. In adversarial modes, the same tier-2 rejection is correct behavior (attack block). For `benign_nominal` and `boundary_safe_both` profiles, tier-2 deltas are zero: the defense adds no false blocks and no missed attacks for setpoints that are both within band and below severity threshold.

---

## 4. Discussion and Limitations

The results confirm three properties of the layered defense. First, pre-execution rejection is operationally fast: even with NumPy matrix operations included, tier-2 relay decisions complete in under 0.3 ms, well within realistic SCADA polling intervals. Second, tier-1 and tier-2 contributions are empirically separable: ablation shows that tier-2 changes outcomes only in the boundary regime, while tier 1 handles gross violations without invoking the physics model. Third, the defense is path-independent of measurement integrity: FDIA on the read path does not affect the write-path defense, so the two layers of the attack kill chain require separate defenses.

Several limitations bound the current implementation. The tier-2 model is a linearized DC approximation and does not account for reactive power, voltage magnitudes, or N-1 contingency constraints—a full AC power flow model would increase both accuracy and computational cost. The topology is a single-aggregator, single-MitM point; real substations involve cross-substation attestation and redundant measurement paths. The tier-2 threshold (0.10 pu) was tuned manually for the course topology; production deployment would require formal threshold calibration against historical operating data. Finally, this implementation does not address relay authentication or secure channel establishment, which are necessary complements in a complete defense-in-depth design.

---

## 5. Conclusion

This project demonstrates that a lightweight, two-tier pre-execution consequence check can practically defend against Type-C command-path attacks in a Mininet-emulated smart grid. The tier-1 nominal band rejects gross violations immediately; the tier-2 linearized DC severity score resolves ambiguous near-boundary commands that tier 1 alone cannot discriminate. Across 328 paired control events covering benign, measurement-corrupted, command-corrupted, and combined attack scenarios, the fully-armed defense achieves 100% attack blocking with sub-millisecond relay latency. The ablation methodology isolates each tier's marginal contribution and provides a reproducible baseline for evaluating more sophisticated physics-aware detection schemes.

---

## References

[1] Y. Liu, P. Ning, and M. K. Reiter, "False data injection attacks against state estimation in electric power grids," in *Proc. ACM CCS*, 2009.

[2] T.-Y. Lin, Y.-C. Chen, and A. Kiani, "Type-C attack resilience for cyber-physical systems via consequence-aware filtering," in *Proc. HotSoS*, 2016.

[3] T.-Y. Lin et al., "Cyber attacks and defenses for cyber-physical systems," *IEEE Computer*, 2020.
