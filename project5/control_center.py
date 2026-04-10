#!/usr/bin/env python3

import argparse
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


def run_auto_demo(rounds=2, pause=1.5):
    """Periodic poll + legitimate P-injection trim on bus 2 (index 23); no blocking input."""
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

            print("--- Round %d: safe control (index 23 -> 1.62 pu) ---" % (r + 1))
            s.sendall(util.pack_dnp3m_control(23, 1.62))
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
    args = parser.parse_args()
    if args.interactive:
        run_interactive()
    else:
        run_auto_demo(rounds=args.rounds, pause=args.pause)


if __name__ == "__main__":
    main()
