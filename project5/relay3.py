#!/usr/bin/env python3

import socket
import relay_common

HOST = "10.0.0.13"
PORT = 20003

measurements = {
    51: 1.00,
    52: -0.07,
    53: -0.90,
    54: 0.00,
    61: 1.00,
    62: 0.04,
    63: 0.00,
    64: 0.00,
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
                        data, measurements, relay_id=3
                    )
                except (AssertionError, ValueError) as e:
                    print("Protocol error:", e)
                    break
                conn.sendall(response)


if __name__ == "__main__":
    main()
