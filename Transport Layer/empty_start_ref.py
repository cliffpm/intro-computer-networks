import socket, sys
import json
import time
import threading
import os
import uuid
import queue

BUFSIZE = 10202  # size of receiving buffer
PKTSIZE = 10200  # number of bytes in a packet
WINDOW_SIZE = 16
IDX_LENGTH = 2 # 2 bytes of packet index
TIMEOUT = 0.5   # timeout time

class Server():
    def __init__(self, config_file):
        self.base_directory = os.path.dirname(os.path.abspath(config_file))

        with open(config_file, "r") as f:
            config = json.load(f)


        self.hostname     = config["hostname"]
        self.port         = config["port"]
        self.peer_count   = config["peers"]
        self.content_info = config["content_info"]
        self.peer_info    = config["peer_info"]

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #NOTE THAT THE SOCK_DGRAM will ensure your socket is UDP
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("", self.port)) #This is the only port you can use to receive
        
        self.server_socket.settimeout(TIMEOUT)   # timeout value

        # for concurrent requests to handle thread synchronization
        self.sessions = {}
        self.sessions_lock = threading.Lock()
        self.active_tx = set() # set of tuple (file, address)
        self.active_tx_lock = threading.Lock()

        self.remain_threads = True
        self.cli()
        return

    def send(self, packet, addr):
        try:
            self.server_socket.sendto(json.dumps(packet).encode(), addr)
        except socket.timeout:
            pass

    # helper function to support concurrency
    def new_session(self, transaction_id):
        if transaction_id is None:
            transaction_id = uuid.uuid4().hex[:8] # 7 bit unique transaction id for each client(s)
        q = queue.Queue() # use this instead of a list because queue module in python is thread safe
        with self.sessions_lock:
            self.sessions[transaction_id] = q
        return transaction_id, q

    def close_session(self, transaction_id):
        with self.sessions_lock:
            del self.sessions["transaction_id"]

    
    def find_file(self, file_name):
        for peer in self.peer_info:
            if file_name in peer["content_info"]:
                return peer["hostname"], peer["port"]
    

    
    def load_file(self, file_name):
        hostname, port = self.find_file(file_name)
        addr = (hostname, port)
        transaction_id, q = self.new_session()
        SYN_packet = {
            "type" : "SYN",
            "file" : file_name,
            "transaction_id" : transaction_id
        }
        
        packet_num = None

        while packet_num is None and self.remain_threads:
            try:
                self.send(SYN_packet, addr)
                packet, recieved_addr = q.get(timeout=TIMEOUT)
                if packet["type"] == "COUNT":
                    packet_num = packet["count"]
                    COUNT_ACK_packet = {
                        "type" : "COUNT-ACK",
                        "transaction_id" : transaction_id
                    }
                    self.send(COUNT_ACK_packet, addr)
            except socket.timeout:
                continue
        

      
        # the receiver keeps a record for which part has been acked
        recieved = {}
        FIN_recieved = False # flag where client says that they have recieved all their data
        previous_time = time.time()

        # start receiving file
        while len(recieved) < packet_num and self.remain_threads:
            current_time = time.time()
            if (current_time - previous_time > TIMEOUT):
                for sequence in list(recieved.keys()):
                    ACK_packet = {
                        "type": "ACK",
                        "sequence_number" : sequence, # sequence is the index
                        "transaction_id" : transaction_id
                    }
                    self.send(ACK_packet, addr)
                previous_time = current_time
            try:
                packet, recieved_addr2 = q.get(timeout=TIMEOUT)
            except queue.Empty:
                if FIN_recieved:
                    break
                else:
                    continue
            
            packet_type = packet["type"]
            if packet_type == "FIN":
                FIN_recieved = True
                continue
            elif packet_type != "DATA":
                continue
                
            sequence = packet["sequence_number"]
            if sequence not in recieved:
                recieved[sequence] = bytes.fromhex(packet["data"])
            ACK_packet = {
                "type" : "ACK",
                "sequence_number" : sequence,
                "transaction_id" : transaction_id
            }
            self.send(ACK_packet, addr)

        self.close_session(transaction_id)

        destination_address = os.path.join(self.base_directory, file_name)
        with open(destination_address, "wb") as f:
            for i in range(packet_num):
                f.write(recieved[i])
        



        # write the file
        
    def read_file(self, file_name):
        transmit_file = []
        destination_address = os.path.join(self.base_directory, file_name)
        with open(destination_address, "rb") as f:
            seq = 0 # start of packet used in TCP
            while True:
                chunk = f.read(PKTSIZE)
                if not chunk:
                    break
                DATA_packet = {
                    "type": "DATA",
                    "seq" : seq,
                    "data" : chunk.hex() # because JSON does not natively handle binary data
                }
                transmit_file.append(DATA_packet)
                seq += 1
        #You can write a function that takes the file to be transmitted and converts into chunks of packet_size
        return transmit_file

    def transmit(self, file_name, addr, transaction_id):
        with self.sessions_lock:
            q = self.sessions_lock.get(transaction_id)
        if q is None: 
            return

        transmit_file = self.read_file(file_name)

        packet_num = len(transmit_file)

        COUNT_packet = {
            "type" : "COUNT",
            "transaction_id" : transaction_id,
            "count" : packet_num
        }

        while True:
            
            try:
                self.send(COUNT_packet, addr)
                packet, _ = q.get(timeout = TIMEOUT)
                if packet["type"] == "COUNT-ACK":
                    break
            except queue.Empty:
                continue
        
        timeout_array = [0] * packet_num # 0 = not transmitted, -1 = recieved, anything postive = time of trans.
        left = 0
        lock = threading.Lock()
        finished = threading.Event() # for synchronization


        # create a udp socket for transmission
        # divide the file into several parts
        #transmit_file = self.read_file(file_name)
        #packet_num = len(transmit_file)
        # use socket to send packet number to the receiver
        #ack = 0
        #print("sending packet num", packet_num, "to", addr)
        # tx_socket.sendto(str(packet_num).encode(), addr)
        # try:
        #     #Receive ACK from the same tx_socket and increment window
        # except socket.timeout:
        #     pass
        # # use a transmit window to determine which file should be transmitted

        # # use a time-out array to record which file is time-out and need to be transmitted again
        # # -1 indicates received, 0 indicates not transmitted, positive numbers means the time of transmission
        
        def transmit_thread():
            nonlocal left
            while not finished.is_set() and self.remain_threads:
                current_time = time.time()
                with lock:
                    for i in range(left, min(left + WINDOW_SIZE, packet_num)):
                        if timeout_array[i] == 0:
                            packet = dict(transmit_file[i])
                            packet["transaction_id"] = transaction_id
                            self.send(packet, addr)
                            timeout_array[i] = current_time
                        
                        elif timeout_array[i] > 0 and (current_time-timeout_array[i] > TIMEOUT):
                            packet = dict(transmit_file[i])
                            packet["transaction_id"] = transaction_id
                            self.send(packet, addr)
                            timeout_array[i] = current_time
                time.sleep(.01)

            #Takes the transmit window and transmits every packet that is allowed to be transmitted
            return
        
        def ack_thread():
            #Receives acknowledgement and updates the transmit window with sendable packets
            nonlocal left
            while not finished.is_set() and self.remain_threads:
                try:
                    packet, _ = q.get(timeout=TIMEOUT)
                except queue.Empty:
                    continue
                    
                if packet["type"] != "ACK":
                    continue
                    
                sequence_number = packet["sequence_number"]
                with lock:
                    if 0 <= sequence_number < packet_num:
                        timeout_array[sequence_number] = -1

                    while left < packet_num and timeout_array[left] != 0:
                        left += 1
                    if left >= packet_num:
                        finished.set() # alert all threads finished state

        tx_thread = threading.Thread(target=transmit_thread)
        ak_thread = threading.Thread(target = ack_thread)

        tx_thread.start()
        ak_thread.start()

        finished.set()
        tx_thread.join()
        ak_thread.join()

        FIN_packet = {
            "type" : "FIN",
            "transaction_id" :transaction_id
        }


        # prof. rec. to send FIN packet multiple types for redundancy
        for _ in range(3):
            self.send(FIN_packet, addr)
            time.sleep(.001)

        # clean up proc.
        self.close_session(transaction_id)
        with self.active_tx_lock:
            self.active_tx.disacrd(transaction_id)

        #Create TX and RX threads and start doing it

        #When done transmitting, close the threads.

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
                #Create a transmit thread (HINT : you can have a large array of transmit threads if you want) and start it
                packet = json.loads(file_name.decode())
                if packet["type"] == "SYN":
                    transaction_id = packet["transaction_id"]
                    file_name = packet["file"]

                    with self.active_tx_lock:
                        if transaction_id in self.active_tx:
                            continue
                        self.active_tx.add(transaction_id)
                    
                    with self.sessions_lock:
                        self.sessions[transaction_id] = queue.Queue()
                    
                    tx_thread = threading.Thread(tarrget = self.transmit, args = (file_name, addr, transaction_id))
                    tx_thread.start()
                    continue
            
                with self.sessions_lock:
                    q = self.sessions["transaction_id"]
                if q is not None:
                    q.put((packet, addr))

                
        return
    
    def cli(self):  # cli interface for input of the file name
        listen_thread = threading.Thread(target=self.listener)
        listen_thread.start()

        while self.remain_threads:
            command_line = input()
            if command_line == "kill":  # for debugging purpose
                self.remain_threads = False
                try:
                    self.server_socket.close()
                except socket.timeout:
                    pass
                break
            else:
                start_thread = threading.Thread(target=self.load_file, args=(command_line))
                start_thread.start()
        
        listen_thread.join()
        return

if __name__ == "__main__":
    server = Server(sys.argv[1])