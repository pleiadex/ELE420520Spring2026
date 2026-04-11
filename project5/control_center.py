#!/usr/bin/env python3

import argparse
import os
import socket
import time
import util

# Data aggregator (reachable from control-center host namespace in Mininet)
HOST = "10.0.0.20"
PORT = 20000

measure_index = [
    11,
    12,
    13,
    14,
    21,
    22,
    23,
    24,
    31,
    32,
    33,
    34,
    41,
    42,
    43,
    44,
    51,
    52,
    53,
    54,
    61,
    62,
    63,
    64,
    71,
    72,
    73,
    74,
    81,
    82,
    83,
    84,
    91,
    92,
    93,
    94,
]


def run_interactive():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        input("Prepare to make connection. (Press ENTER to execute s.connect() )")
        s.connect((HOST, PORT))
        input("Prepare to send data. (Press ENTER to execute poll )")
        req = util.pack_dnp3m_request(measure_index)
        s.sendall(req)

        res = s.recv(8192)
        all_measure = util.unpack_dnp3m_response(res)
        util.print_measure(all_measure)

        input("Prepare to close the connection.(Press ENTER to execute s.close() )")
        s.close()


def run_auto_demo(rounds=2, pause=1.5, control_index=23, control_setpoint=1.62):
    """Periodic poll + P-injection control command; no blocking input."""
    mode = os.environ.get("PROJECT5_MODE", "default")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        for r in range(rounds):
            print("--- Round %d: poll ---" % (r + 1))
            req = util.pack_dnp3m_request(measure_index)
            s.sendall(req)
            res = s.recv(8192)
            all_measure = util.unpack_dnp3m_response(res)
            util.print_measure(all_measure)
            time.sleep(pause)

            print(
                "--- Round %d: control (index %d -> %.4f pu) ---"
                % (r + 1, control_index, control_setpoint)
            )
            print(
                "PROJECT5,CC_CMD,mode=%s,idx=%d,sp=%.6f"
                % (mode, control_index, float(control_setpoint)),
                flush=True,
            )
            s.sendall(
                util.pack_dnp3m_control(int(control_index), float(control_setpoint))
            )
            ack = s.recv(1024)
            status = util.unpack_control_ack(ack)
            print(
                "Control ack status=%d (%s)"
                % (
                    status,
                    "accepted" if status == util.STATUS_OK else "rejected",
                )
            )
            time.sleep(pause)


def main():
    parser = argparse.ArgumentParser(
        description="Control center: poll + DNP3m control (Project 5)."
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Original stepping mode with input() prompts.",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=2,
        help="Auto-demo poll/control cycles (default 2).",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=1.5,
        help="Seconds between steps in auto mode.",
    )
    parser.add_argument(
        "--control-index",
        type=int,
        default=int(os.environ.get("PROJECT5_CONTROL_INDEX", "23")),
        help="Measurement index for DNP3m control command.",
    )
    parser.add_argument(
        "--control-setpoint",
        type=float,
        default=float(os.environ.get("PROJECT5_CONTROL_SP", "1.62")),
        help="Setpoint (pu) for control command.",
    )
    args = parser.parse_args()
    if args.interactive:
        run_interactive()
    else:
        run_auto_demo(
            rounds=args.rounds,
            pause=args.pause,
            control_index=args.control_index,
            control_setpoint=args.control_setpoint,
        )


if __name__ == "__main__":
    main()
