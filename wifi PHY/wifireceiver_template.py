# -*- coding: utf-8 -*-
from random import randint
import numpy as np
import sys
import commpy as comm
import commpy.channelcoding.convcode as check
from pip import main
import matplotlib.pyplot as plt
  

def SoftViterbiDecoder(input_stream, cc1):

    bits_to_ideal_complex = {0: -1-1j,
                             1: -1 +1j,
                             2: 1-1j,
                             3: 1 + 1j} # (4 QAM mapping)
    
    # create a transition table:  (current_state, input_bit) -> [next_state, ideal_complex point]
    transition_table = {}
    for i in range(len(cc1.output_table)):
        for j in range(len(cc1.output_table[0])):
            # i represents the current state
            # j represents the input
            # arr[i][j] represents the next state
            current_state = i
            input = j
            next_state = cc1.next_state_table[i][j]
            output = cc1.output_table[i][j] #in decimal
            transition_table[(current_state, input)] = [next_state, bits_to_ideal_complex[output]]

    '''
    at each step every state has two incoming edges
    aka two candidates . compare total score of both paths
    and pick the path with lower score and store
    the index of the previous state in this grid

    score = node.val + weight

    current_node.val = min(score1, score2)
    '''
    # dimension is states x num_ofdm symbols
    #trellis_memory = is matrix graph representation. the dimensions is num_states (rows) by num_complex_numbers(columns)
    trellis_memory = np.zeros((cc1.number_states, len(input_stream) + 1))
    trellis_path = np.zeros_like(trellis_memory) # use to get shortest path tracing backwards

    trellis_input = np.zeros_like(trellis_memory)
    predecessor_table = {} 

    for state in range(cc1.number_states):
        for input in range(2):
            next_state, ideal_complex_pt = transition_table[(state, input)]
            if next_state in predecessor_table:
                predecessor_table[next_state].append((state, input))
            else:
                predecessor_table[next_state] = [(state, input)]
    
    for i in range(1, cc1.number_states):
        trellis_memory[i][0] = float('infinity')
    
    # forward pass. we fill up the trellis_memory matrix
    for t  in range(1,len(input_stream)+1):
        actual_complex = input_stream[t-1]

        for state in range(cc1.number_states):
            prev1_pack = predecessor_table[state][0]
            prev2_pack = predecessor_table[state][1]

            prev_state1, input_1 = prev1_pack[0], prev1_pack[1]
            prev_state2, input_2 = prev2_pack[0], prev2_pack[1]

            _, ideal_complex1 = transition_table[(prev_state1), input_1]
            _, ideal_complex2 = transition_table[(prev_state2), input_2]

            euclid_dist1 = abs(ideal_complex1-actual_complex)**2
            euclid_dist2 = abs(ideal_complex2 - actual_complex)**2

            distance_1, distance_2 = trellis_memory[prev_state1][t-1], trellis_memory[prev_state2][t-1]
            distance_1 += euclid_dist1
            distance_2 += euclid_dist2

            if distance_1 < distance_2: 
                trellis_memory[state][t] = distance_1
                trellis_path[state][t] = prev_state1
                trellis_input[state][t] = input_1
            else :
                trellis_memory[state][t] = distance_2
                trellis_path[state][t] = prev_state2
                trellis_input[state][t] = input_2

    # backward pass, build the shortest path. Easy way is to start at end at smallest column and move to front
    de_trellis_msg = [] # conv to int after, easier to concat

    current_state = int(np.argmin(trellis_memory[:, -1]))
    for t in range(len(trellis_memory[0])-1, 0, -1):
        de_trellis_msg.append(trellis_input[current_state][t])
        current_state = int(trellis_path[current_state][t])

    de_trellis_msg = de_trellis_msg[::-1]
    
    return de_trellis_msg

def WifiReceiver(input_stream, level):

    nfft = 64
    Interleave_tr = np.reshape(np.transpose(np.reshape(np.arange(1, 2*nfft+1, 1),[4,-1])),[-1,])
    preamble = np.array([1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1,1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1])
    cc1 = check.Trellis(np.array([3]),np.array([[0o7,0o5]]))

    # set zero padding to be 0, by default
    begin_zero_padding = 0
    message=""
    length=0
    if level >= 4:
        #Input QAM modulated + Encoded Bits + OFDM Symbols in a long stream
        #Output Detected Packet set of symbols
        input_stream=input_stream

    if level >= 3:
        #Input QAM modulated + Encoded Bits + OFDM Symbols
        #Output QAM modulated + Encoded Bits
        input_stream=input_stream
    
    if level >= 2:
        #Input QAM modulated + Encoded Bits (ECC)
        #Output Interleaved bits + Encoded Length (exactly the input for level 1)

        # 4 QAM means each complex number represents 2 bits.
        # so input_stream[:len(preamble)//2] is the preamble . we should split it
        stripped_preamble = input_stream[len(preamble)//2:]
        # then at this point the encoded msg. length header is the first 128 bits
        length = stripped_preamble[:nfft] # DONT FORGET THAT EACH ITEM IN STREAM IS 2 BITS
        data_block = stripped_preamble[nfft:]
        # now since I want to implement soft viterbi decoding
        # i will use the 
        #demodulated +decoded trellis stream
        decrypt = SoftViterbiDecoder(data_block, cc1)

        # note for the encoded length, currently it is in complex number
        # we can use commpy to conv to bits but we dont need to use any viterbi decoding
        
        mod = comm.modulation.QAMModem(4)
        encoded_msg_length_bits = mod.demodulate(length, demod_type = 'hard')

        input_stream = np.concatenate((encoded_msg_length_bits, np.array(decrypt))) # now send to level 1

        # input_stream=input_stream
       
    if level >= 1: # input is bitstream 1D array of floats
    
        #Input Interleaved bits + Encoded Length
        #Output Deinterleaved bits

        # goal : deinterleave bits using given information and encoded length. known that the 
        # permutation is row-column interleaving so this is simply a matrix transpose

        # first step get the 128 bit (1 ofdm symbol) block
        # which represents the encoded length
        encoded_length_block = input_stream[0:2*nfft]
        encoded_length_block = np.trim_zeros(encoded_length_block, 'f')
        # now we are ensured theres a perfect window of 3 for each group of repeated 3 bits. get maj vote of the window
        decoded_length = []
        for i in range(0,len(encoded_length_block),3):
            decoded_length.append(str(np.bincount(encoded_length_block[i:i+3].astype(int)).argmax()))

        length = int(''.join(decoded_length), 2)
        # next step is to deinterleave the bits
        deinterleaved = np.zeros(len(input_stream[2*nfft:]),)
        data_stream = input_stream[2*nfft:]
        
        nsym = int(len(data_stream) / (2*nfft)) # num of chunks

        for i in range(nsym):
            symbol = data_stream[i*2*nfft:(i+1)*2*nfft]
            # print(f"symbol : {symbol}")
            deinterleaved[i*2*nfft:(i+1)*2*nfft] = symbol[Interleave_tr-1]
        
        for i in range(length):
            # current_char = message_string[i*8:(i+1)*8]
            current_char = deinterleaved[i*8:(i+1)*8]
            current_char = "".join(current_char.astype(int).astype(str))
            message += chr(int(current_char,2))

        #length = bin(length)[2:] # since in handout the output wants the length in binary representation
        return begin_zero_padding, message, length

    raise Exception("Error: Unsupported level")


# for testing purpose
from wifitransmitter import WifiTransmitter
if __name__ == "__main__":
    # test_case = 'The Internet has transformed our everyday lives, bringing people closer together and powering multi-billion dollar industries. The mobile revolution has brought Internet connectivity to the last-mile, connecting billions of users worldwide. But how does the Internet work? What do oft repeated acronyms like "LTE", "TCP", "WWW" or a "HTTP" actually mean and how do they work? This course introduces fundamental concepts of computer networks that form the building blocks of the Internet. We trace the journey of messages sent over the Internet from bits in a computer or phone to packets and eventually signals over the air or wires. We describe commonalities and differences between traditional wired computer networks from wireless and mobile networks. Finally, we build up to exciting new trends in computer networks such as the Internet of Things, 5-G and software defined networking. Topics include: physical layer and coding (CDMA, OFDM, etc.); data link protocol; flow control, congestion control, routing; local area networks (Ethernet, Wi-Fi, etc.); transport layer; and introduction to cellular (LTE) and 5-G networks. The course will be graded based on quizzes (on canvas), a midterm and final exam and four projects (all individual). '
    # symbols = [randint(0, 1) for i in range(32*8)]
    # print(test_case)
    # output = WifiTransmitter(test_case, 2)
    # begin_zero_padding, message, length_y = WifiReceiver(output, 2)
    # print(begin_zero_padding, message, length_y)
    # print(test_case == message)


    # test 1 : works
    # txtsignal = WifiTransmitter('hello world', 1)
    # begin_zero_padding, message, length = WifiReceiver(txtsignal, 1)

    # print(f"begin_zero_padding : {begin_zero_padding}")
    # print(f"message : {message}")
    # print(f"length : {length}")

    txsignal = WifiTransmitter('hello world', 2)
    begin_zero_padding, message, length = WifiReceiver(txsignal, 2)
    
    print(begin_zero_padding, message, length)
