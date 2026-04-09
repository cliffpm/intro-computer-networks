# -*- coding: utf-8 -*-
from random import randint
import numpy as np
import sys
import commpy as comm
import commpy.channelcoding.convcode as check
from pip import main
import matplotlib.pyplot as plt
  

def SoftViterbiDecoder(input_stream, cc1):
    



    # use euclidean distance (squared dist.)
    # ideal points : 
    # 00 : -1 - 1j
    # 01 : -1 + 1j
    # 11 : 1  + 1j
    # 10 : 1 -  1j
    #
    #
    bits_to_ideal_complex = {0: -1-1j,
                             1: -1 +1j,
                             2: 1-1j,
                             3: 1 + 1j}
    


    
    # create a transition table 
    # where (current_state, input_bit) -> [next_state, ideal_complex point]
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


    # calulcating the weights for each edge beforehand might be useful

    # we can store it as the third item in the trans table values list
    

 
    
    

    
    # row represents time
    # column represents the 8 states

    '''
    at each step every state has two incoming edges
    aka two candidates . compare total score of both paths
    and pick the path with lower score and store
    the index of the previous state in this grid

    ex : best way to get to state 2 at time step 5 was coming
    from state 4, then trellis_memory[5][2] = 4

    '''
    # dimension is states x num_ofdm symbols
    trellis_memory = [[0 for _ in range(len(input_stream)+1)] for _ in range(len(cc1.number_states))] # 2d array of size num_symbols, 8
    
    trellis_path = np.zeros_like(trellis_memory) # use to walk backward and get
    # the shortest path

    trellis_input = np.zeros_like(trellis_memory)
    # CURRENT TO DO: MAKE A TABLE current_state : [states that it couldve came from]
    predecessor_table = {} # tells us at the current state which 2 previous state came from to get
    # to current state

    for state in range(cc1.number_states):
        for input in range(2):
            next_state, ideal_complex_pt = transition_table[(state, input)]
            if next_state in predecessor_table:
                predecessor_table[next_state].append((state, input))
            else:
                predecessor_table[next_state] = [(state, input)]
    



    # it would be cleaner if we computed the distances but I guess we can do that in one go
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

            if distance_1 < distance_2: # then we USE prev state 1, so make note of that in our decision matrix
                trellis_memory[state][t] = distance_1
                trellis_path[state][t] = prev_state1
                trellis_input[state][t] = input_1
            else :
                trellis_memory[state][t] = distance_2
                trellis_path[state][t] = prev_state2
                trellis_input[state][t] = input_2




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
        stripped_preamble = input_stream[:len(preamble)//2]
        # then at this point the encoded msg. length header is the first 128 bits
        length = stripped_preamble[:nfft] # DONT FORGET THAT EACH ITEM IN STREAM IS 2 BITS
        data_block = stripped_preamble[nfft:]
        # now since I want to implement soft viterbi decoding
        # i will use the 
        #demodulated +decoded trellis stream
        decrypt = SoftViterbiDecoder(data_block)

        input_stream=input_stream
       
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
            print(f"symbol : {symbol}")
            deinterleaved[i*2*nfft:(i+1)*2*nfft] = symbol[Interleave_tr-1]
        
        for i in range(length):
            # current_char = message_string[i*8:(i+1)*8]
            current_char = deinterleaved[i*8:(i+1)*8]
            current_char = "".join(current_char.astype(int).astype(str))
            message += chr(int(current_char,2))

        length = bin(length)[2:] # since in handout the output wants the length in binary representation
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

    test_2 = WifiTransmitter('101', 2)
    print(test_2)
