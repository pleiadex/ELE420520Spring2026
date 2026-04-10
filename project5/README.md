# Project 5 — Type-C command defense (pre-execution physical check)

Branch: **`project5`**. Code lives only in this directory; [`project3/`](../project3/) remains the reference for the original FDIA lab.

## Threat model (short)

- **Type A / false data injection (Liu et al., CCS 2009):** attacker alters **telemetry** on the read path — demonstrated in Project 3 (`FDIA_ON` in `data_aggregator.py`).
- **Type C (Lin et al., HotSoS 2016):** attacker alters **control fields** on the write path so packets stay **syntactically valid** but become **physically unsafe** — we inject this at the data aggregator with `TYPE_C_ATTACK` (MitM).

**Defense (HotSoS Figure 4, P2):** relays **estimate consequence ahead of time** using a **tier-1** envelope: real-power injection setpoints must stay within **nominal ± `MARGIN_PU`** (see `relay_common.py`). Violations are rejected before updating local state.

## Protocol

- **Poll:** opcode `0x01` (unchanged).
- **Control:** opcode `0x02`, 7 bytes: `[0x02, 7, target_index, float setpoint]`.
- **Ack:** opcode `0x0C`, 3 bytes: `[0x0C, 3, status]` (`0` = accepted, `1` = rejected).

## Running under Mininet

1. `sudo python3 build_net.py` — open xterms on hosts, or use `run_test.py` for a non-interactive smoke test:
   - `sudo python3 run_test.py`
2. In host namespaces (or xterms): start `relay1.py` … `relay4.py`, then `data_aggregator.py`, then `control_center.py`.

`control_center.py` defaults to **auto** mode (poll + safe control on index `23`). Use `--interactive` for the original stepping behavior.

## Demo flags (`data_aggregator.py`)

| Flag | Meaning |
|------|---------|
| `FDIA_ON` | Apply measurement FDIA map (Project 3 style). Set `False` for baseline polls. |
| `TYPE_C_ATTACK` | Replace forwarded control setpoint with `MALICIOUS_SETPOINT` (physically unsafe ? relay rejects). |

## Primary references (PDFs in `docs/papers/`)

- Lin et al., HotSoS 2016 — type C attacks & detection principle (Figure 4).
- Liu et al., CCS 2009 — false data injection vs state estimation.
- Lin et al., Computer 2020 — survey framing.

## Limitations

- Simplified **DC/nominal-band** check instead of full adaptive AC power-flow / N-1 (HotSoS §4.2).
- Single aggregator topology; no cross-substation measurement attestation.
