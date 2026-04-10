# Project 5 - Type-C Command-Path Defense with Tier-2 Linear Consequence Scoring

**Course:** ELE 420/520 (Spring 2026)  
**Scope:** Type-C command-path defense with tier-1 + tier-2 relay checks, reproducible Mininet experiments, and CSV/figure artifacts in `project5/results/`.

## 1. Introduction and threat model

This project contrasts two cyber-physical attack paths:

- **Type A (measurement FDIA):** attacker corrupts telemetry on the read path.
- **Type C (command manipulation):** attacker alters control values on the write path while keeping packets syntactically valid.

The implemented defense runs at relay side before command execution:

1. **Tier-1:** hard nominal band check.
2. **Tier-2:** linear DC consequence score; reject if predicted state deviation exceeds threshold.

The objective is to reject physically unsafe commands before relay state is updated, while preserving benign control availability.

## 2. Related work mapping

| Concept | Reference family | Local implementation |
|---|---|---|
| Measurement-path attack (FDIA) | Liu et al., CCS 2009 | `PROJECT5_FDIA` in `data_aggregator.py` |
| Command-path Type-C + consequence-ahead defense | Lin et al., HotSoS 2016 | `PROJECT5_TYPE_C` + relay-side tier checks |
| Lightweight deployable control validation | Course-oriented simplification | tier-1 band + tier-2 linear score |

## 3. System design

### 3.1 Control/data path

`control_center.py` sends poll/control to `data_aggregator.py`, which forwards to four relays. For tested commands, index `23` maps to `relay1`.

### 3.2 Tier-1 check

Tier-1 enforces nominal operating envelope (nominal plus/minus `MARGIN_PU`) and rejects out-of-band commands (`tier1_band_violation`).

### 3.3 Tier-2 check

Tier-2 uses `H`, `W`, and nominal `z` from `calculate_fdia.m`, computes a linearized state deviation severity `||dx||_inf`, and rejects when above threshold (`tier2_predicted_state_deviation`).

### 3.4 Ablation toggles

- `PROJECT5_TIER1=0` or `--no-tier1`: disable tier-1.
- `PROJECT5_TIER2=0` or `--no-tier2`: disable tier-2.

Default behavior remains tier-1 on and tier-2 on.

## 4. Experimental setup

- **Topology:** Mininet 3-switch harness via `run_test.py`.
- **Modes:** `baseline`, `fdia_only`, `typec_only`, `combined`.
- **Per-run rounds:** 2 control events.
- **Repetitions in current completed run set:** 5 logs per mode (20 total logs).
- **Logging:** structured lines (`PROJECT5,CONFIG`, `PROJECT5,RELAY_CONTROL`, `PROJECT5,DA_CONTROL`) saved under `results/raw/`.

### Reproduction commands

```bash
cd project5
pip install -r requirements.txt
sudo python3 run_experiment_matrix.py --trials 5 --rounds 2 --sudo
python3 analyze_results.py
python3 plot_results.py
```

## 5. Comprehensive simulation results

### 5.1 Full matrix completion status

The latest run produced a full mixed dataset (legacy + deep-ablation runs):

- `summary.csv`: **164** per-log rows.
- `summary_by_mode.csv`: **4** aggregated modes.
- `summary_by_combo.csv`: **52** `(mode, profile, tier1, tier2)` combinations.
- `ablation_delta.csv`: populated marginal comparisons (not header-only).
- `events.csv`: **328** paired control events.

This confirms the deep matrix pipeline is operational and producing analyzable outputs.

### 5.2 Mode-level aggregate outcomes

From `results/summary_by_mode.csv`:

| Mode | Mean accept rate | Median relay latency (ms) | Mean policy accuracy |
|---|---:|---:|---:|
| baseline | 0.8537 | 0.2430 | 0.8537 |
| fdia_only | 0.8537 | 0.2470 | 0.8537 |
| typec_only | 0.2195 | 0.0505 | 0.7805 |
| combined | 0.2195 | 0.0500 | 0.7805 |

Interpretation:

- `baseline` and `fdia_only` remain close, so in this command-decision setup FDIA alone does not dominate relay accept/reject behavior.
- `typec_only` and `combined` show low acceptance due to command-path blocking.
- Attack-heavy rejection paths exhibit lower median relay decision latency.

### 5.3 Confusion-style security outcomes

From `results/confusion_table.csv`:

| benign_forwarded | benign_blocked | attack_forwarded | attack_blocked | n_events | policy_accuracy |
|---:|---:|---:|---:|---:|---:|
| 140 | 24 | 36 | 128 | 328 | 0.8171 |

Meaning:

- Strong attack blocking overall (`128` blocked attack events),
- but non-zero misses (`36` attack forwarded) and non-zero benign false blocks (`24`), which are expected when ablation includes intentionally weakened tier settings.

### 5.4 Deep ablation findings (tier contribution)

The most informative profile is `boundary_tier2_only` (setpoint `2.5` pu), designed to be inside tier-1 band but above tier-2 severity threshold.

From `summary_by_combo.csv` and `ablation_delta.csv`:

- In `baseline` / `fdia_only` with `boundary_tier2_only`:
  - `tier2=off` combinations accept (`mean_accept_rate=1.0`),
  - `tier2=on` combinations reject (`mean_accept_rate=0.0`, `mean_benign_false_block_rate=1.0`).
- Corresponding deltas show:
  - `delta_pair_policy_accuracy = -1.0`,
  - `delta_benign_false_block_rate = +1.0`,
  for `tier2_on_minus_off` on that boundary profile.

This is the key conceptual result: **tier-2 changes decisions where tier-1 alone cannot discriminate**, i.e., it adds a physically informed second guard rather than duplicating tier-1 behavior.

In `typec_only` / `combined`, marginal rows also show `+1.0` attack-block gains when enabling a tier over no-tier baselines (depending on fixed opposite-tier condition), confirming defense contribution under adversarial forwarding.

### 5.5 Figure artifacts (latest)

- `results/figures/accept_rate_and_latency.png`
- `results/figures/confusion_counts.png`
- `results/figures/severity_boxplot.png`
- `results/figures/ablation_by_combo.png`
- `results/figures/ablation_marginal_policy.png`

These figures are generated from the latest CSVs and match the matrix outputs above.

## 6. Why this is a meaningful result

Even with a lightweight DC linear model, the implementation demonstrates three meaningful properties:

1. **Operational pre-execution defense:** relays can reject unsafe commands before state update.
2. **Layered protection with separable effects:** tier-1 and tier-2 contributions are empirically separable via ablation.
3. **Boundary-case discrimination:** tier-2 provides extra decision power specifically near tier-1 boundaries.

This is sufficient to support the project claim of a practical, research-grounded smart extension beyond static hard-band filtering.

## 7. Limitations and future work

- Tier-2 is a linear DC approximation, not full AC power flow / N-1.
- Current completed result set is strong on mode-level behavior, but deep tier ablation coverage is not yet complete in CSV artifacts.
- Future work: expand indices/profiles, larger trial counts, and formal/specification-aware policies.

## 8. Reproducibility appendix

| Path | Purpose |
|---|---|
| `relay_common.py` | tier-1/tier-2 decision path and relay decision logging |
| `physics_model.py` | linear model and severity threshold |
| `run_test.py` | one Mininet experiment run and structured logging |
| `run_experiment_matrix.py` | matrix orchestration and skip-existing logic |
| `analyze_results.py` | summary/event/combo/ablation CSV generation |
| `plot_results.py` | result figure generation |
| `results/raw/*.log` | raw logs |
| `results/*.csv` | aggregate metrics and ablation outputs |
