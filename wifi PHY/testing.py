import numpy as np

msg = "hello"

res = np.unpackbits(np.array([ord(c) for c in msg], dtype = np.uint8))

# print(res)

print(f"ord of 1 :", ord("1"))
print(f"ord of 0 :", ord("0"))

res = [1,2,3,4]

# print(res[1:])

print(np.unpackbits(np.array([49,48,49],dtype=np.uint8)))

x =[0, 0, 1, 1,0, 0, 0, 1 ,0, 0, 1, 1, 0, 0, 0 ,0, 0 ,0, 1, 1, 0, 0, 0, 1]

print(len(x))