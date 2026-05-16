import socket, sys
import json
import time
import threading

BUFSIZE = 10202  # size of receiving buffer
PKTSIZE = 10200  # number of bytes in a packet
WINDOW_SIZE = 16
IDX_LENGTH = 2 # 2 bytes of packet index
TIMEOUT = 0.5   # timeout time

class Server():
    def __init__(self, config_file):
        #Read the config file and initialize the port, peer_num, peer_info, content_info from the config file
        with open(config_file, "r") as f:
            config = json.load(f)
        
        self.hostname = config["hostname"]
        self.port = config["port"]
        self.peer_count = config["peers"]
        self.content_info = config["content_info"]
        self.peer_info = config["peer_info"]


        # establish a socket according to the information
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #NOTE THAT THE SOCK_DGRAM will ensure your socket is UDP
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("", self.port)) #This is the only port you can use to receive
        
        self.server_socket.settimeout(1)   # timeout value

        self.remain_threads = True
        self.cli()
        return
    
    def find_file(self, file_name):
        for peer in self.peer_info:
            if file_name in peer["content_info"]:
                return(peer["hostname"], peer["port"]) # we return hostname alongside with back port number
    
    def load_file(self, file_name):
        # find which server has the file
        # establish a client socket for downloading file
        hostname, port = self.find_file(file_name)

        self.cl_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        
        # use a connect flag to determine if the file name is sent correctly
        
        #Initiate three-way handshake and use a connect flag
        
        # while not connect_flag:
        #     try:
        #         # handshake
        #     except socket.timeout:
        #         # handshake failed


        # professor said handshake is optional. will implement this later

        
        # need to get the packet count
        packet_num = None

        while packet_num is None:
            try:
                message, address = self.cl_socket.recvfrom(BUFSIZE)
                packet = json.loads(message.decode())
                if packet["type"] == "COUNT":
                    packet_num = packet["count"]

                    COUNT_packet = {
                        "type": "COUNT"
                    }

                    self.cl_socket.sendto(json.dumps(COUNT_packet).encode(), (hostname, port))
            except socket.timeout:
                continue
      
        # the receiver keeps a record for which part has been acked
        recieved = {} # dict of sequence number -> data
        
        # start receiving file

        while (len(recieved) < packet_num):
            try:
                message, address = self.cl_socket.recvfrom(BUFSIZE)

                packet = json.loads(message.decode())
                if packet["type"] != "DATA":
                    continue
                    
                seq = packet["sequence"]

                if seq not in recieved:
                    data = bytes.fromhex(packet["data"]) # because we stored as hex in JSON 
                    recieved[seq] = data
                
                ACK_packet = {
                    "type" : "ACK",
                    "seq" : seq
                }

                self.cl_socket.sendto(json.dumps(ACK_packet).encode(),(hostname, port))

            except socket.timeout:
                continue

        # transmission complete, close socket
        self.cl_socket.close()
        # write the file

        with open(file_name, "wb") as f:
            for i in range(packet_num):
                f.write(recieved[i])
        
        
        
    def read_file(self, file_name):
        #You can write a function that takes the file to be transmitted and converts into chunks of packet_size
        transmit_file = []
        with open(file_name, "rb") as f:
            seq = 0
            while True:
                chunks = f.read(PKTSIZE)
                if not chunks:
                    break
                transmit_file.append({
                    "seq" : seq,
                    "data" : chunks.hex() # since JSON does not natively support raw binary data
                })
                seq += 1
        return transmit_file




    def transmit(self, file_name, addr):
        # create a udp socket for transmission
        # divide the file into several parts
        transmit_file = self.read_file(file_name)
        packet_num = len(transmit_file)
        # use socket to send packet number to the receiver
        ack = 0
        count_acknowledged = False
        timeout_array = [False] * packet_num
        timers = [0] * packet_num
        tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #print("sending packet num", packet_num, "to", addr)
        
        while not count_acknowledged:
            tx_socket.sendto(str(packet_num).encode(), addr) # sends the packet number
            try:
                message, address = tx_socket.recvfrom(BUFSIZE)
                packet = json.loads(message.decode())

                if packet["type"] == "COUNT-ACK":
                    count_acknowledged = True
                #Receive ACK from the same tx_socket and increment window
            except socket.timeout:
                pass

        # use a transmit window to determine which file should be transmitted
        base = 0
        next_ptr = 0
        lock = threading.Lock()

        # use a time-out array to record which file is time-out and need to be transmitted again
        # -1 indicates received, 0 indicates not transmitted, positive numbers means the time of transmission
        
        def transmit_thread():
            nonlocal next_ptr
            nonlocal base
            while base < packet_num:
                lock.aquire()

                while (next_ptr < packet_num and next_ptr < base + WINDOW_SIZE):
                    tx_socket.sendto(json.dumps(transmit_file[next_ptr]).encode(), addr)

                    timers[next_ptr] = time.time()
                    next_ptr += 1
                

                for i in range(base, next_ptr):
                    if timeout_array[i]:
                        continue
                    if time.time() - timers[i] > TIMEOUT:
                        tx_socket.sendto(json.dumps(transmit_file[i]).encode(), addr)
                        timers[i]= time.time()

                lock.release()
                time.sleep(.001)

            #Takes the transmit window and transmits every packet that is allowed to be transmitted
            return
        
        def ack_thread():
            #Receives acknowledgement and updates the transmit window with sendable packets
            nonlocal base
            while base < packet_num:
                try:
                    message, address = tx_socket.recvfrom(BUFSIZE)
                    packet = json.loads(message.decode())
                    if packet["type"] != "ACK":
                        continue
                        
                    seq = packet["seq"]
                    lock.acquire()

                    if 0 <= seq < packet_num:
                        timeout_array[seq] = True
                    
                    while (base < packet_num and timeout_array[base]):
                        base += 1
                    
                    lock.release()
                
                except socket.timeout:
                    pass
        
        #Create TX and RX threads and start doing it
        tx_thread =threading.Thread(target=transmit_thread)
        rx_thread =threading.Thread(target=ack_thread)

        tx_thread.join()
        rx_thread.join()

        #When done transmitting, close the threads.
        tx_socket.sendto(json.dumps({"type": "FIN"}).encode(), addr)
        tx_socket.close()

    def listener(self): # listen to the socket to see if there's any transmission request
        #Do any initializations that you want
        while self.remain_threads:
            file_name = ""
            try:
                file_name, addr = self.server_socket.recvfrom(BUFSIZE)
                #Receive the file name and requesting address from the UDP
            except socket.timeout:
                pass
            
            if file_name == "":
                pass
            else:   # start transmission
                pass#Create a transmit thread (HINT : you can have a large array of transmit threads if you want) and start it
                
        return
    
    def cli(self):  # cli interface for input of the file name
        listen_thread = threading.Thread(target=self.listener)
        listen_thread.start()

        while self.remain_threads:
            command_line = input()
            if command_line == "kill":  # for debugging purpose
                #Do the kill stuff
                return
            #Otherwise it is a file name!
        #Exit stuff if you have some?
        return


if __name__ == "__main__":
    server = Server(sys.argv[1])