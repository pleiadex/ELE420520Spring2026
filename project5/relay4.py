#!/usr/bin/env python3

import socket
import relay_common

HOST = "10.0.0.14"
PORT = 20004

measurements = {
    71: 1.00,
    72: 0.01,
    73: -1.00,
    74: 0.00,
    81: 1.00,
    82: 0.07,
    83: 0.00,
    84: 0.00,
    91: 1.00,
    92: -0.07,
    93: -1.25,
    94: 0.00,
}


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print("Waiting for client to connect.")

        conn, addr = s.accept()

        with conn:
            print("Connected by", addr)
            while True:
                data = conn.recv(1024)
                print("Waiting for data to receive.")
                if not data:
                    print("An packet without payload is received, end the connection.")
                    break
                print("Receiving data")
                try:
                    response, _kind = relay_common.handle_message(
                        data, measurements, relay_id=4
                    )
                except (AssertionError, ValueError) as e:
                    print("Protocol error:", e)
                    break
                conn.sendall(response)


if __name__ == "__main__":
    main()
