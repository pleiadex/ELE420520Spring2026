#!/usr/bin/env python3

import socket
import relay_common

HOST = "10.0.0.11"
PORT = 20001

measurements = {
    11: 1.00,
    12: 0.00,
    13: 0.67,
    14: 0.00,
    21: 1.00,
    22: 0.17,
    23: 1.63,
    24: 0.00,
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
                        data, measurements, relay_id=1
                    )
                except (AssertionError, ValueError) as e:
                    print("Protocol error:", e)
                    break
                conn.sendall(response)


if __name__ == "__main__":
    main()
