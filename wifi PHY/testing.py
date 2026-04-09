import numpy as np
import commpy as comm
import commpy.modulation as modul
import commpy.channelcoding.convcode as check


msg = np.array([0,0,0, 1,1,1,1,0])

mod = modul.QAMModem(4)
output = mod.modulate(msg.astype(bool))
# print(output)

cc1 = check.Trellis(np.array([3]),np.array([[0o7,0o5]])) # the encoder

# print(cc1.next_state_table)

# print()
# print(cc1.output_table)
bits_to_ideal_complex = {0: -1-1j,
                            1: -1 +1j,
                            2: 1-1j,
                            3: 1 + 1j}

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

        ideal_complex = bits_to_ideal_complex[output]
        actual_complex = input_stream[i] # the current Z_i actual complex value

        distance = abs(ideal_complex - actual_complex)**2


        transition_table[(current_state, input)] = [next_state, distance]



predecessor_table = {}

for state in range(cc1.number_states):
    for input in range(2):
        next_state, ideal_complex_pt = transition_table[(state, input)]
        if next_state in predecessor_table:
            predecessor_table[int(next_state)].append(state)
        else:
            predecessor_table[int(next_state)] = [state]


# print(transition_table)

# print(predecessor_table)

x = -1-1j
y = .8 +.4j

print(abs(y-x)**2)


# msg = "hello"

# res = np.unpackbits(np.array([ord(c) for c in msg], dtype = np.uint8))

# # print(res)

# print(f"ord of 1 :", ord("1"))
# print(f"ord of 0 :", ord("0"))

# res = [1,2,3,4]

# # print(res[1:])

# print(np.unpackbits(np.array([49,48,49],dtype=np.uint8)))

# x =[0, 0, 1, 1,0, 0, 0, 1 ,0, 0, 1, 1, 0, 0, 0 ,0, 0 ,0, 1, 1, 0, 0, 0, 1]

# print(len(x))