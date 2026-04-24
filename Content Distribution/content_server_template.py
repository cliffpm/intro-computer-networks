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
       

       #   {neighbor name :{uuid: _ , host: _ , backend_port: _ , metric: _}}  
        self.active_peers = {} 



        #node name : {neighbor name : distance}
        self.map = {} 
        
        # the last time that node with uuid had sent a keep alive message
        self.uuid_to_last_alive = {} 
        # self.uuid_to_last_alive will keep track of last time that node w
        # uuid had sent a keep alive message, meaning its also our neighbor


        self.uuid_to_name = {} # will be helpful since right now haven't implemented LSA . uuid -> node name (from LSA)

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
                    host_name_t = vals[1]
                    backend_port_t = int(vals[2])
                    distance_t = int(vals[3])
                    self.peers.append({
                        "uuid": uuid_t,
                        "host":host_name_t,
                        "backend_port": backend_port_t,
                        "metric": distance_t
                    })


        # maybe handle case if uuid is not found ?
        # because prof. said that in lecture
        # but in spec. it says uuid guranteed in config. file





        # create the receive socket . This socket is for recieving from the server to client
        self.dl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dl_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.dl_socket.bind(('127.0.0.1', self.backend_port)) #YOU NEED TO READ THIS FROM CONFIGURATION FILE
        self.dl_socket.listen(100)

     


        # Extract neighbor information and populate the initial variables - believe I did this above



        # Update the map - I can only update it once I do link-state-advertisement
        # so I think we build the map in the link_state_adv() function




        # Initialize link state advertisement that repeats using a neighbor variable
        # self.link_state_adv() # probably not right here . deadlock since thread flag not on
        
        print("Initial setting complete")

        self.remain_threads = True
        self.alive() # parallel code
        return


    def addneighbor(self, host, backend_port, metric):
        # Add neighbor code goes here
        return
    

    # this is sending updates every 30 seconds or so, so the graph is most updated
    def link_state_adv(self):
        while self.remain_threads:
            # Perform Link State Advertisement to all your neighbors periodically 
            pass
        return

    
    def link_state_flood(self, send_time, host, msg):
        # If new information then send to all your neighbors, if old information then drop.
        return
    


    # use the template dl socket code to send information to all alive neighbors
    def dead_adv(self, peer):
        # Advertise death before kill
        return
    
    def dead_flood(self, send_time, host, peer):
        # Forward the death message information to other peers
        return




    def keep_alive(self):
        # Tell that you are alive to all your neighbors, periodically.
        while self.remain_threads:

            for neighbor in self.peers: # each neighbor is a dict of uuid, hostname, backendport, distance
                ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # dont make it a self. variable to avoid race condition
                try:
                    ul_socket.connect(('127.0.0.1', neighbor["backend_port"]))
                    packet_sending = {"uuid" : self.uuid, "message" : "Alive message"}
                    ul_socket.send((str(packet_sending)).encode()) # should send it along with our
                    # current node UUID, so that way in timeout_old, we can distingush
                    # which node sent the keep alive so we can update status dead or alive
                    ul_socket.close()
                except socket.error:
                    pass
            time.sleep(ALIVE_SGN_INTERVAL)
        return
    
   
   ## THIS IS THE RECEIVE FUNCTION THAT IS RECEIVING THE PACKETS
    def listen(self):
        self.dl_socket.settimeout(0.1)  # for killing the application
        while self.remain_threads:
            try:
                connection_socket, client_address = self.dl_socket.accept()
                msg_string = connection_socket.recv(BUFSIZE).decode()
                msg_string = ast.literal_eval(msg_string)
                if isinstance(msg_string, dict):
                    message = msg_string["message"]
                    sender_uuid = msg_string["uuid"]
                # print("received", connection_socket, client_address, msg_string)
            except socket.timeout:
                msg_string = ""
                pass

            if message == "":    # empty message
                pass # do nothing since socket probably failed




            ## might be a bit scuffed because at the time I wrote this block, LSA wasn't written yet
            elif message == "Alive message": # Update the timeout time if known node, otherwise add new neighbor
                # known_sender = None

                # for neighbor_dict in self.peers:
                #     neighbor_uuid = neighbor_dict["uuid"]
                #     if neighbor_uuid == sender_uuid:
                #         known_sender = neighbor_dict
                #         break
                        
                # if known_sender: # this means that the node that sent keep alive is one of our neighbors
                #     name = self.uuid_to_name[sender_uuid]
                #     self.active_peers[name][""]
                current_time = time.time()
                self.uuid_to_last_alive[sender_uuid] = current_time
  
                






            elif message == "Link State Packet":     # Update the map based on new information, drop if old information
                #If new information, also flood to other neighbors
                pass
            elif message == "Death message": # Delete the node if it sends the message before executing kill.
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
                print(str({"uuid": self.uuid}))
            elif command == "neighbors": # complete this after completed link_state_adv()
                # Print Neighbor information
            elif command == "addneighbor":
                # Update Neighbor List with new neighbor
            elif command == "map":
                # Print Map
            elif command == "rank": 
                # Compute and print the rank

if __name__ == "__main__":
    content_sever = Content_server(sys.argv[2])
