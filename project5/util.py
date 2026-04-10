import socket
import struct
import binascii
import copy

# DNP3m application-layer opcodes (custom protocol)
REQ_POLL = 0x01
REQ_CONTROL = 0x02
RESP_POLL = 0x0B
RESP_CONTROL = 0x0C

STATUS_OK = 0
STATUS_REJECT = 1


def message_opcode(data):
    if not data:
        return None
    return data[0]


def get_message_kind(data):
    op = message_opcode(data)
    if op == REQ_POLL:
        return "poll"
    if op == REQ_CONTROL:
        return "control"
    return "unknown"


# Input
#   data: request received from socket
# Return
#   a list of indices whose measurements are asked
def unpack_dnp3m_request(data):
    request_format = "=" + "B" * len(data)
    data_unpacked = struct.Struct(request_format).unpack(data)
    assert data_unpacked[0] == REQ_POLL
    assert data_unpacked[1] == len(data)

    return data_unpacked[2:]


# Input
#   list_of_indices: a list containing index to include in the request
# Return
#   Byte object that will be sent by socket
def pack_dnp3m_request(list_of_indices):
    assert len(list_of_indices) > 0
    req_length = 2 + len(list_of_indices)
    req_format = "=" + "B" * req_length
    req = struct.Struct(req_format).pack(REQ_POLL, req_length, *list_of_indices)

    return req


# Control: [opcode, length, target_index (1 byte), setpoint (float LE)]
def pack_dnp3m_control(target_index, setpoint):
    req_length = 7
    return struct.Struct("=BBBf").pack(REQ_CONTROL, req_length, target_index, float(setpoint))


def unpack_dnp3m_control(data):
    assert len(data) >= 7
    assert data[0] == REQ_CONTROL
    assert data[1] == len(data) == 7
    target_index = data[2]
    setpoint = struct.Struct("=f").unpack_from(data, 3)[0]
    return target_index, setpoint


def pack_control_ack(status):
    """Minimal ack: opcode, total length, status byte."""
    assert status in (STATUS_OK, STATUS_REJECT)
    resp_length = 3
    return struct.Struct("=BBB").pack(RESP_CONTROL, resp_length, status)


def unpack_control_ack(data):
    assert len(data) >= 3
    assert data[0] == RESP_CONTROL
    assert data[1] == len(data)
    return data[2]


# Input
#   data: response received from socket
# Return
#   dictionary type including the tuples (index, measurement)
def unpack_dnp3m_response(data):
    res_length = len(data)
    assert (res_length - 2) % 5 == 0
    n_tuples = int((len(data) - 2) / 5)
    res_format = "=BB" + ("Bf" * n_tuples)
    res_unpacked = struct.Struct(res_format).unpack(data)

    assert res_unpacked[0] == RESP_POLL
    assert res_unpacked[1] == res_length
    all_measure = {}
    for j in range(0, n_tuples):
        cur_index = res_unpacked[j * 2 + 2]
        cur_measure = res_unpacked[j * 2 + 3]
        all_measure[cur_index] = cur_measure

    return all_measure


# Input
#   measurements: dictionary-type data structure containing measurements
#   indices: indices whose measurements are to be packed in the dnp3m response
# Return
#   Byte object that will be send by socket
def pack_dnp3m_response(indices, measurements):

    assert len(indices) > 0
    response_unpacked = []
    response_length = 2
    n_index = 0

    for i in indices:
        if i in measurements:
            response_unpacked.append(i)
            response_length = response_length + 1
            response_unpacked.append(measurements[i])
            response_length = response_length + 4
            n_index = n_index + 1
    response_format = "=BB" + ("Bf" * n_index)
    response = struct.Struct(response_format).pack(RESP_POLL, response_length, *response_unpacked)
    return response


def print_measure(all_measure):
    for key, value in all_measure.items():
        print(key, ": ", " {:.2f}".format(value))
    print("\n")


def index_to_relay(index):
    relay_assignment = {
        1: [11, 12, 13, 14, 21, 22, 23, 24],
        2: [31, 32, 33, 34, 41, 42, 43, 44],
        3: [51, 52, 53, 54, 61, 62, 63, 64],
        4: [71, 72, 73, 74, 81, 82, 83, 84, 91, 92, 93, 94],
    }
    relay_num = 0
    for k in relay_assignment.keys():
        if index in relay_assignment[k]:
            relay_num = k
            break

    assert relay_num != 0
    return relay_num


def change_measure(orig_measure, fdia_measure):
    result_measure = copy.deepcopy(orig_measure)
    for key, value in fdia_measure.items():
        if key in result_measure:
            result_measure[key] = value
    return result_measure
