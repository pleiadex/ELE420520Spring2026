# Project 5 � Type-C command defense (pre-execution physical check)

Branch: **`project5`**. Code lives only in this directory; [`project3/`](../project3/) remains the reference for the original FDIA lab.

## Threat model (short)

- **Type A / false data injection (Liu et al., CCS 2009):** attacker alters **telemetry** on the read path � demonstrated in Project 3 (`FDIA_ON` in `data_aggregator.py`).
- **Type C (Lin et al., HotSoS 2016):** attacker alters **control fields** on the write path so packets stay **syntactically valid** but become **physically unsafe** � we inject this at the data aggregator with `TYPE_C_ATTACK` (MitM).

**Defense (HotSoS Figure 4, P2):** relays **estimate consequence ahead of time** using a **tier-1** envelope: real-power injection setpoints must stay within **nominal � `MARGIN_PU`** (see `relay_common.py`). Violations are rejected before updating local state. An optional **tier-2** linear DC score (`physics_model.py`) predicts state deviation from `H`, `W`, and nominal `z`; reject if `??x??` exceeds a threshold (`PROJECT5_TIER2`, default on).

## Protocol

- **Poll:** opcode `0x01` (unchanged).
- **Control:** opcode `0x02`, 7 bytes: `[0x02, 7, target_index, float setpoint]`.
- **Ack:** opcode `0x0C`, 3 bytes: `[0x0C, 3, status]` (`0` = accepted, `1` = rejected).

## Running under Mininet

1. `sudo python3 build_net.py` � open xterms on hosts, or use `run_test.py` for a non-interactive smoke test:
   - `sudo python3 run_test.py`
2. In host namespaces (or xterms): start `relay1.py` � `relay4.py`, then `data_aggregator.py`, then `control_center.py`.

`control_center.py` defaults to **auto** mode (poll + safe control on index `23`). Use `--interactive` for the original stepping behavior.

## Demo flags (`data_aggregator.py`)

| Flag | Meaning |
|------|---------|
| `FDIA_ON` | Apply measurement FDIA map (Project 3 style). Set `False` for baseline polls. |
| `TYPE_C_ATTACK` | Replace forwarded control setpoint with `MALICIOUS_SETPOINT` (physically unsafe ? relay rejects). |
| `PROJECT5_TYPE_C` | Environment variable: if `1` / `true` / `yes`, enables Type-C MitM without editing the file (see `run_test.py`). |

Smoke tests: `sudo python3 run_test.py` (expect control **accepted**). After `sudo mn -c`, run `sudo env PROJECT5_TYPE_C=1 python3 run_test.py` (expect control **rejected**, `status=1`).

### Experiment matrix and results

- `pip install -r requirements.txt` (NumPy + Matplotlib for tier-2 and plots).
- **Full ablation matrix** (modes x tier1 on/off x tier2 on/off x setpoint profiles x trials):  
  `sudo python3 run_experiment_matrix.py --trials 3 --rounds 2 --sudo --skip-existing`  
  Profiles: `benign_nominal`, `boundary_safe_both`, `boundary_tier2_only` (see `run_experiment_matrix.py`). Uses `sudo -E` and `mn -c` between runs.
- **Single run flags:** `--no-tier1`, `--no-tier2`, `--profile NAME`, `--log-file ...`
- Summarize: `python3 analyze_results.py` -> `results/summary.csv`, `summary_by_mode.csv`, `summary_by_combo.csv`, `ablation_delta.csv`, `confusion_table.csv`, `events.csv`.
- Figures: `python3 plot_results.py` -> `results/figures/*.png` (includes `ablation_by_combo.png`).
- Structured lines are appended to `--log-file` (`PROJECT5_LOG_FILE`); paths are resolved relative to this directory, not the shell CWD.

See `report/Project5_TypeC_Defense_Report.md` for a full write-up with measured tables and figure references.

## Primary references (PDFs in `docs/papers/`)

- Lin et al., HotSoS 2016 � type C attacks & detection principle (Figure 4).
- Liu et al., CCS 2009 � false data injection vs state estimation.
- Lin et al., Computer 2020 � survey framing.

## Limitations

- Simplified **DC/nominal-band** check instead of full adaptive AC power-flow / N-1 (HotSoS �4.2).
- Single aggregator topology; no cross-substation measurement attestation.
