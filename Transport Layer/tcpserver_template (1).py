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
        self.data = json.load(config_file)
        self.port = self.data["port"]
        self.peer_num = self.data["peers"]
        self.peers = self.config.get("peer_info", [])

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
                    recieved_table[sequence_number] = recieved_packet["data"]
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
        

    def transmit(self, file_name, addr):
        # create a udp socket for transmission
        # divide the file into several parts
        #transmit_file = self.read_file(file_name)
        #packet_num = len(transmit_file)
        # use socket to send packet number to the receiver
        #ack = 0
        #print("sending packet num", packet_num, "to", addr)
        tx_socket.sendto(str(packet_num).encode(), addr)
        try:
            #Receive ACK from the same tx_socket and increment window
        except socket.timeout:
            pass
        # use a transmit window to determine which file should be transmitted

        # use a time-out array to record which file is time-out and need to be transmitted again
        # -1 indicates received, 0 indicates not transmitted, positive numbers means the time of transmission
        
        def transmit_thread():
            #Takes the transmit window and transmits every packet that is allowed to be transmitted
            return
        
        def ack_thread():
            #Receives acknowledgement and updates the transmit window with sendable packets
        
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
                # tx_thread = threading.Thread(target=)
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