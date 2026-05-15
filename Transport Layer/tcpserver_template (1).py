import socket, sys
import json
import time
import threading
import base64
from queue import Queue, Empty


BUFSIZE = 10202  # size of receiving buffer
PKTSIZE = 10200  # number of bytes in a packet
WINDOW_SIZE = 16
IDX_LENGTH = 2 # 2 bytes of packet index
TIMEOUT = 0.5   # timeout time

class Server():
    def __init__(self, config_file):
        #Read the config file and initialize the port, peer_num, peer_info, content_info from the config file
        with open(config_file, 'r') as f:
            self.data = json.load(f)
        self.port = self.data["port"]
        self.peer_num = self.data["peers"]
        self.peers = self.data.get("peer_info", [])

        # establish a socket according to the information
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #NOTE THAT THE SOCK_DGRAM will ensure your socket is UDP
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("", self.port)) #This is the only port you can use to receive, IP address ?
        self.server_socket.settimeout(1)   # timeout value
        self.remain_threads = True
        self.cli()
        return
    
    def find_file(self, file_name):
        #A function to find the peer with the file you want!
        for peer_dict in self.peers:
            for curr_filename in peer_dict["content_info"]:
                if curr_filename == file_name:
                    return (peer_dict["hostname"], peer_dict["port"])
        return (None, None)

    # reciever (client) of protocol
    def load_file(self, file_name):
        hostname, port = self.find_file(file_name)

        # find which server has the file
        # establish a client socket for downloading file
        self.cl_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        
        # use a connect flag to determine if the file name is sent correctly
        connect_flag = False
      
        #Initiate three-way handshake and use a connect flag
        num_packets = 0
        while not connect_flag:
            self.cl_socket.connect((hostname, port))
            SYN_packet = {
                "filename" : file_name,
                "type" : "SYN",
            }
            self.cl_socket.send(json.dumps(SYN_packet).encode())
            try:
                data, addr = self.cl_socket.recvfrom(BUFSIZE)
                response_dict = json.loads(data.decode())

                if response_dict["type"] == "SYN-ACK":
                    num_packets = response_dict["total_packets"]
                    connect_flag = True

            except socket.timeout:
                continue
        
        # the receiver keeps a record for which part has been acked
        recieved_table = {}

        # start receiving file
        
        while len(recieved_table) < num_packets:
            try:
                data, address = self.cl_socket.recvfrom(BUFSIZE)
                recieved_packet = json.loads(data.decode())
                if recieved_packet["type"] == "DATA":
                    sequence_number = recieved_packet["sequence"]
                    recieved_table[sequence_number] = base64.b64decode(recieved_packet["data"])
                    ACK_packet = {
                        "type": "ACK",
                        "sequence" : sequence_number
                    }
                    self.cl_socket.send((json.dumps(ACK_packet)).encode())
            except socket.timeout:
                continue


        # transmission complete, close socket
        self.cl_socket.close()


        sort_sequence = sorted(recieved_table.keys())
        corrected_datastream = b"".join([recieved_table[i] for i in sort_sequence])
        try:
            with open(file_name,"wb") as f:
                f.write(corrected_datastream)
        except Exception:
            pass
        # write the file
        
    def read_file(self, file_name):
        #You can write a function that takes the file to be transmitted and converts into chunks of packet_size
        transmitted_file = []
        try:
            with open(file_name, 'rb') as f:
                while True:
                    bit_data = f.read(PKTSIZE)
                    if not bit_data:
                        break
                    transmitted_file.append(bit_data)
            return transmitted_file
        except FileNotFoundError:
            return None
        

    def transmit(self, file_name, addr, q):
        # create a udp socket for transmission
        # divide the file into several parts
        transmit_file = self.read_file(file_name) # the data we iterate over
        packet_num = len(transmit_file)
        # use socket to send packet number to the receiver
        ack = 0
        timeout_array = [0]*packet_num
        left_ptr = 0
        right_ptr = min(packet_num, WINDOW_SIZE)

        lock = threading.Lock() # because transmit and ack thread use left and right pointer
                                #   transmit reads it to iterate through transmit_file
                                #   ack thread writes (updates) to left and right pointer




        tx_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tx_socket.settimeout(TIMEOUT) # to avoid blocking
        SYN_ACK_packet = {
            "type" : "SYN-ACK",
            "total_packets" : packet_num
        }
        tx_socket.sendto(json.dumps(SYN_ACK_packet).encode(), addr)
        # while True:
        #     try:
        #         tx_socket.sendto(json.dumps(SYN_ACK_packet).encode(), addr)
        #         break
        #         #Receive ACK from the same tx_socket and increment window
        #     except socket.timeout:
        #         continue
        
        # use a transmit window to determine which file should be transmitted

        # use a time-out array to record which file is time-out and need to be transmitted again
        # -1 indicates received, 0 indicates not transmitted, positive numbers means the time of transmission
        
        def transmit_thread():
            #Takes the transmit window and transmits every packet that is allowed to be transmitted
            
            while left_ptr < packet_num:
                with lock:
                    for i in range(left_ptr, right_ptr):
                        current_time = time.time()
                        if timeout_array[i] != -1 and ((timeout_array[i] > 0 and current_time - timeout_array[i]  > TIMEOUT) or (timeout_array[i] == 0)):
                            # needs to retransmit
                            packet = {
                                "type" : "DATA",
                                "sequence" : i,
                                "data" : base64.b64encode(transmit_file[i]).decode('utf-8') # need to use b64 encode / dec. because of socket str() .encode()
                            }
                            tx_socket.sendto(json.dumps(packet).encode(), addr)
                            timeout_array[i] = current_time
                time.sleep(.001)
            return
        
        def ack_thread():
            nonlocal left_ptr, right_ptr
            #Receives acknowledgement and updates the transmit window with sendable packets
            while left_ptr < packet_num:
                try:
                    packet = q.get(timeout=TIMEOUT)
                    seq = packet["sequence"]
                    # data, addr_temp = #tx_socket.recvfrom(BUFSIZE)
                    # packet = json.loads(data.decode())
                    # if packet["type"] == "ACK":
                    #     seq = packet["sequence"]

                    with lock:
                        #if 0 <= seq < packet_num: # safety check for in bounds indexing
                        timeout_array[seq] = -1 # recieved this file
                        
                        while left_ptr < packet_num and timeout_array[left_ptr] == -1:
                            left_ptr += 1
                        
                        right_ptr = min(left_ptr + WINDOW_SIZE, packet_num)
                except Empty:
                    continue
        #Create TX and RX threads and start doing it
        tx_thread = threading.Thread(target=transmit_thread)
        ak_thread = threading.Thread(target=ack_thread)

        tx_thread.start()
        ak_thread.start()

        tx_thread.join()
        ak_thread.join()


        tx_socket.close()
        #When done transmitting, close the threads.



    # server side listening for SYN requests from client


    # important ! use only the one self.server_socket
    def listener(self): # listen to the socket to see if there's any transmission request
        #Do any initializations that you want

        self.active_trans = {} # maps tuple (ip, port) : queue for acknowedgement packets

        while self.remain_threads:
            try:
                data, address = self.server_socket.recvfrom(BUFSIZE)
                packet = json.loads(data.decode())
            
                if packet["type"] == "SYN":
                    q = Queue()
                    self.active_trans[address] = q
                    dest_file = packet["filename"]
                    tx_thread = threading.Thread(target=self.transmit, args = (dest_file, address, q))
                    tx_thread.start()
                elif packet["type"] == "ACK":
                    if address in self.active_trans:
                        self.active_trans[address].put(packet)
            except socket.timeout:
                continue

        return
        # self.active_tx_threads = []
        # while self.remain_threads:
        #     file_name = ""
        #     try:
        #         file_name, addr = self.server_socket.recvfrom(BUFSIZE)
        #         #Receive the file name and requesting address from the UDP
        #     except socket.timeout:
        #         pass
            
        #     if file_name == "":
        #         pass
        #     else:   # start transmission
        #         req = json.loads(file_name.decode())
        #         if req["type"] == "SYN":
        #             target_file = req["filename"]
        #             tx_thread = threading.Thread(target= self.transmit, args=(target_file, addr))
        #             self.active_tx_threads.append(tx_thread)
        #             tx_thread.start()
        # return
    
    def cli(self):  # cli interface for input of the file name
        listen_thread = threading.Thread(target=self.listener)
        listen_thread.start()

        while self.remain_threads:
            command_line = input()
            if command_line == "kill":  # for debugging purpose
                #Do the kill stuff
                self.remain_threads = False
                try: self.server_socket.close()
                except:
                    pass
                return
            #Otherwise it is a file name!


            # kill if file name incorrect ? later

            self.load_file(command_line)

        #Exit stuff if you have some?
        return


if __name__ == "__main__":
    server = Server(sys.argv[1])