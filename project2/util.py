import socket
import struct
import binascii

# Input 
#   data: request received from socket
# Return
#   a list of indices whose measurements are asked
def unpack_dnp3m_request(data):
    # Parse the data to see whether it is a DNP3m request or not
    request_format = '=' + 'B' * len(data)
    data_unpacked = struct.Struct(request_format).unpack(data)
    # Using the first byte to check whether this is a DNP3m request or not
    assert(data_unpacked[0] == 0x01)
    # Checking the second byte contains appropriate value or not
    assert(data_unpacked[1] == len(data))
    
    return data_unpacked[2:]

# Input
#   list_of_indices: a list containing index to include in the request
# Return
#   Byte object that will be sent by socket
def pack_dnp3m_request(list_of_indices):
    assert(len(list_of_indices) > 0)
    req_length = 2 + len(list_of_indices)
    req_format = '=' + 'B' * req_length
    req = struct.Struct(req_format).pack(1, req_length, *list_of_indices)

    return req

# Input 
#   data: response received from socket
# Return
#   dictionary type including the tuples (index, measurement)
def unpack_dnp3m_response(data):
    res_length = len(data)
    assert( (res_length -2) % 5 == 0 )
    n_tuples = int((len(data) - 2)/5)
    # define res_format used in struct.Struct to unpack "data" into a list "res_unpacked"
    #       you can refer to unpack_dnp3m_request for some helps
    res_format = '=' + 'BB' + 'Bf' * n_tuples
    res_unpacked = struct.Struct(res_format).unpack(data)

    # using assert to check whether this is a response or not
    assert(res_unpacked[0] == 0x0B)
    # check whether the value of the length field of the response includes the appropriate values or not
    assert(res_unpacked[1] == len(data))
    all_measure = {}
    for j in range(0, n_tuples):
        # unpack the data to store all measurements
        #      all_measure should be a dictionary-type using index to indexed the corresponding measurement
        #  In each iteration 
        #      Using j to locate the starting position of an index, extract its values as i
        #      Using j to locate the starting position of an measurement, extract its values as m
        #      Store m in all_measurement indexed by i
        i = res_unpacked[2 + j * 2]
        m = res_unpacked[2 + j * 2 + 1]
        all_measure[i] = m

    return all_measure

# Input
#   measurements: dictionary-type data structure containing measurements
#   indices: indices whose measurements are to be packed in the dnp3m response
# Return
#   Byte object that will be send by socket

def pack_dnp3m_response(indices, measurements):
    
    assert(len(indices) > 0)
    response_unpacked = []
    response_length = 2
    n_index = 0

    for i in indices:
        if i in measurements:
            # packed the measurements indexed by the values in "indices"
            #       response_unpacked should be a list
            #       response_length should include the length of the response packet
            #       In each iteration
            #            adding i into response_unpacked
            #            increase the response_length by 1
            #            adding the measurements[i] into response_unpacked
            #            increase the response_length by 4
            response_unpacked.append(i)
            response_length += 1
            response_unpacked.append(measurements[i])
            response_length += 4
            n_index = n_index + 1
    # defined response_format used in struct.Struct to pack the list into a byte object
    response_format = '=' + 'BB' + 'Bf' * n_index
    # pack the list "response_format" into a byte object "response"
    response = struct.Struct(response_format).pack(0x0B, response_length, *response_unpacked)
    return response


def print_measure(all_measure):
    for key, value in all_measure.items():
        print(key, ': ' , ' {:.2f}'.format(value))
    print('\n')

def index_to_relay(index):
    relay_assignment = {1: [11, 12, 13, 14, 21, 22, 23, 24], \
                   2: [31, 32, 33, 34, 41, 42, 43, 44], \
                   3: [51, 52, 53, 54, 61, 62, 63, 64], \
                   4: [71, 72, 73, 74, 81, 82, 83, 84, 91, 92, 93, 94]}
    relay_num = 0
    for k in relay_assignment.keys():
        if index in relay_assignment[k]:
            relay_num = k
            break
    
    assert(relay_num != 0)
    return relay_num
