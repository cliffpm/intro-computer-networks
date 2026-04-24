import socket, sys
import ast
import threading, time
import random

BUFSIZE = 1024  # size of receiving buffer
ALIVE_SGN_INTERVAL = 0.5  # interval to send alive signal
TIMEOUT_INTERVAL = 10*ALIVE_SGN_INTERVAL
UPSTREAM_PORT_NUMBER = 1111 # socket number for UL transmission

##
#
# FOR TRANSMITTING PACKET USE THE FOLLOWING CODE
#
#self.ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#try:
#   self.ul_socket.connect((host, backend_port))
#   self.ul_socket.send(("STRING TO SEND").encode())
#   self.ul_socket.close()
#except socket.error:
#   pass
#
#
#
#

class Content_server():
    def __init__(self, conf_file_addr):
        # load and read configuration file
        self.uuid = None
        self.name = None # name for curr node
        self.backend_port = None
        self.peer_count = None

        # Create all the data structures to store various variables
        self.peers = [] # current neighbor of this node
        self.active_peers = {} #   {neighbor name :{uuid: , host: , backend_port: , metric: , last_seen :  (this is the timestamp of last keepalive message that is seen)}}                  will store the active nodes neighbors later
        self.map = {} #node name : {neighbor name : distance}

        with open(conf_file_addr, "r") as f:
            for line in f:
                line = line.strip()
                if not line :
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                if key == "uuid":
                    self.uuid = value
                elif key == "name":
                    self.name = value
                elif key == "backend_port":
                    self.backend_port = int(value)
                elif key == "peer_count":
                    self.peer_count = value
                elif key.startswith("peer_"):
                    vals = [val.strip() for val in value.split(',')]
                    uuid_t = vals[0]
                    name_t = vals[1]
                    backend_port_t = int(vals[2])
                    distance_t = int(vals[3])
                    self.peers.append({
                        "uuid": uuid_t,
                        "host":name_t,
                        "backend_port": backend_port_t,
                        "metric": distance_t
                    })






        # create the receive socket . This socket is for recieving from the server to client
        self.dl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.dl_socket.bind(('127.0.0.1', self.backend_port)) #YOU NEED TO READ THIS FROM CONFIGURATION FILE
        self.dl_socket.listen(100)

     


        # Extract neighbor information and populate the initial variables - believe I did this above



        # Update the map - I can only update it once I do link-state-advertisement
        # so I think we build the map in the link_state_adv() function




        # Initialize link state advertisement that repeats using a neighbor variable
        
         # self.link_state_adv() - i dont think adding this here is right
        
         # since we haven't init. self.remain_threads = True yet

        print("Initial setting complete")

        self.remain_threads = True
        self.alive() # parallel code
        return
    
    def addneighbor(self, host, backend_port, metric):
        # Add neighbor code goes here
        return
    
    def link_state_adv(self):
        while self.remain_threads:
            # Perform Link State Advertisement to all your neighbors periodically 
            pass
        return

    
    def link_state_flood(self, send_time, host, msg):
        # If new information then send to all your neighbors, if old information then drop.
        return
    
    def dead_adv(self, peer):
        # Advertise death before kill
        return
    
    def dead_flood(self, send_time, host, peer):
        # Forward the death message information to other peers
        return

    def keep_alive(self):
        # Tell that you are alive to all your neighbors, periodically.
        return
    
   
   ## THIS IS THE RECEIVE FUNCTION THAT IS RECEIVING THE PACKETS
    def listen(self):
        self.dl_socket.settimeout(0.1)  # for killing the application
        while self.remain_threads:
            try:
                connection_socket, client_address = self.dl_socket.accept()
                msg_string = connection_socket.recv(BUFSIZE).decode()
                # print("received", connection_socket, client_address, msg_string)
            except socket.timeout:
                msg_string = ""
                pass

            if msg_string == "":    # empty message
                pass
            elif msg_string == "Alive message": # Update the timeout time if known node, otherwise add new neighbor
                pass
            elif msg_string == "Link State Packet":     # Update the map based on new information, drop if old information
                #If new information, also flood to other neighbors
                pass
            elif msg_string == "Death message": # Delete the node if it sends the message before executing kill.
                pass
            # otherwise the msg is dropped

    def timeout_old(self):
        # drop the neighbors whose information is old
        print("a")

    def shortest_path(self):
        # derive the shortest path according to the current link state
        rank = {}
        return rank

    
    def alive(self):
        keep_alive = threading.Thread(target=self.keep_alive) # A thread that keeps sending keep_alive messages
        listen = threading.Thread(target=self.listen) # A thread that keeps listening to incoming packets
        timeout_old = threading.Thread(target=self.timeout_old) # A thread to eliminate old neighbors
        link_state_adv = threading.Thread(target=self.link_state_adv) # A thread that keeps doing link_state_adv
        keep_alive.start()
        listen.start()
        timeout_old.start()
        link_state_adv.start()
        while self.remain_threads:
            time.sleep(ALIVE_SGN_INTERVAL)  # wait for the network to settle
            command_line = input().split(" ")
            command = command_line[0]
            # print("Received command: ", command)
            if command == "kill":
                # Send death message
                # Kill all threads
            elif command == "uuid":
                # Print UUID
            elif command == "neighbors":
                # Print Neighbor information
            elif command == "addneighbor":
                # Update Neighbor List with new neighbor
            elif command == "map":
                # Print Map
            elif command == "rank": 
                # Compute and print the rank

if __name__ == "__main__":
    content_sever = Content_server(sys.argv[2])
