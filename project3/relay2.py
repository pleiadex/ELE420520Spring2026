#!/usr/bin/env python3

import socket
import util

HOST = '10.0.0.12'  # put the ip address of the relay2 (as a TCP server)
PORT = 20002

# measurements contained in this relay
# Estimated states x2, x3 from calculate_fdia.m baseline x_est
measurements = {31: 1.00, 32: 0.09, 33: 0.85, 34: 0.00, \
          41: 1.00, 42: -0.04, 43: 0.00, 44: 0.00}



def main():

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT)) 
        s.listen()
        print('Waiting for client to connect.')

        conn, addr = s.accept()

        with conn:
            print('Connected by', addr)
            while True:
                data = conn.recv(1024)
                print('Waiting for data to receive.')
                if not data:
                    print('An packet without payload is received, end the connection.')
                    break
                else:
                    print('Receiving data')
                    req_indices = util.unpack_dnp3m_request(data)
                    response = util.pack_dnp3m_response(req_indices, measurements)
                   
                conn.sendall(response)


if __name__ == "__main__":
    main()
