import socket, sys
import ast
import threading, time
import random
import heapq


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
        self.seq = 0 # use this for LSA to determine 'recent'ness



        # Create all the data structures to store various variables
        self.peers = [] # current neighbor of this node
       

       #   {neighbor name :{uuid: _ , host: _ , backend_port: _ , metric: _}}  
        self.active_peers = {} 

        #node name : {node name : {neighbor name : distance}}
        self.map = {} 
        
        # the last time that node with uuid had sent a keep alive message
        self.uuid_to_last_alive = {} 
        # self.uuid_to_last_alive will keep track of last time that node w
        # uuid had sent a keep alive message, meaning its also our neighbor
       
       
       
        self.uuid_to_seen_seq = {}


        # i believe we can fill this in the flooding stage
        # state_adv function is only used to send the packet to each neighbors only 
        # from the current node


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


    # note code came originally without uuid as a parameter,
    # but it should be included to follow expected neighbor format
    def addneighbor(self, uuid, host, backend_port, metric):
        # Add neighbor code goes here
        self.peers.append({                        
                        "uuid": uuid,
                        "host":host,
                        "backend_port": backend_port,
                        "metric": metric
                        })


        # maybe add a flag to alert link_state_adv to start sending out
        # LSA packets

        return
    

    # this is sending updates every 30 seconds or so, so the graph is most updated
    def link_state_adv(self):
        while self.remain_threads:
            # Perform Link State Advertisement to all your neighbors periodically 
            self.seq += 1



            # uuid to distance of all neighbors of the current node
            #neighbor_metrics = {p['uuid'] : p['metric'] for p in self.peers}
            neighbor_metrics = {}

            for p in self.peers:
                name = self.uuid_to_name.get(p["uuid"])
                if name:
                    neighbor_metrics[name] = p["metric"]
                # else LSA hasnt sent name yet


            lsa_packet = {
                "message": "Link State Packet",
                "source_uuid" : self.uuid,
                "source_name" : self.name,
                "neighbors": neighbor_metrics, #include a neighbor map here of their uuid and the distance
                "seq": self.seq
            }
            for neighbor in self.peers:
                ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)



                try :
                    ul_socket.connect(('127.0.0.1', neighbor['backend_port']))
                    ul_socket.send((str(lsa_packet)).encode())
                    ul_socket.close()
                except socket.error:
                    pass
            time.sleep(3) # send LSA packet every 3 seconds

        return

    
    def link_state_flood(self, send_time, host, msg):
        # If new information then send to all your neighbors, if old information then drop.
        sender_uuid = msg["source_uuid"]

        # drop old packet
        if sender_uuid in self.uuid_to_seen_seq and msg["seq"] <= self.uuid_to_seen_seq[sender_uuid]:
            return

        self.uuid_to_seen_seq[sender_uuid] = msg["seq"]
        
        

        sender_node = host[1]
        # host is a tuple of (ip, port) from the node that just sent LSA to us

        # self.uuid_to_seen_seq[sender_uuid] = msg["seq"]
        # self.uuid_to_name[sender_uuid] = msg["source_name"]
        # self.map[msg["source_name"]] = msg["neighbors"]

        for neighbor in self.peers:
            if neighbor["uuid"] == sender_uuid:
                continue 
            
            ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                ul_socket.connect(('127.0.0.1', neighbor["backend_port"]))
                ul_socket.send((str(msg)).encode())
                ul_socket.close()
            except socket.error:
                pass
        
        return
    


    # TODO IMPLEMENT THESE LATER (OPTIONAL BUT STILL DO IT)

    # use the template dl socket code to send information to all alive neighbors
    # def dead_adv(self, peer):
    #     dead_message = {
    #         "message": "Death message",
    #         "source_uuid": self.uuid,
    #         "source_name": self.name
    #     }

    #     for neighbor in self.peers:
    #         ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #         try:
    #             ul_socket.connect(('127.0.0.1', neighbor['backend_port']))
    #             ul_socket.send(str(dead_message).encode())
    #             ul_socket.close()
    #         except socket.error:
    #             pass

    #     return
    
    # def dead_flood(self, send_time, host, peer):
    #     # Forward the death message information to other peers
    #     return




    def keep_alive(self):
        # Tell that you are alive to all your neighbors, periodically.
        while self.remain_threads:

            for neighbor in self.peers: # each neighbor is a dict of uuid, hostname, backendport, distance
                ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # dont make it a self. variable to avoid race condition
                try:
                    ul_socket.connect(('127.0.0.1', neighbor["backend_port"]))
                    packet_sending = {"source_uuid" : self.uuid, "message" : "Alive message", 
                                      "backend_port" : self.backend_port}
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
                    sender_uuid = msg_string["source_uuid"]
                # print("received", connection_socket, client_address, msg_string)
            except socket.timeout:
                msg_string = ""
                pass
            if message == "":    # empty message
                pass # do nothing

            ## might be a bit scuffed because at the time I wrote this block, LSA wasn't written yet
            elif message == "Alive message": # Update the timeout time if known node, otherwise add new neighbor
                


                current_time = time.time()
                self.uuid_to_last_alive[sender_uuid] = current_time
                
                # neighbors_uuid = set(p["uuid"] for p in self.peers)
                # if sender_uuid not in neighbors_uuid:
                # # ....
                #     pass
                    


                # POPULATING ACTIVE NEIGHBORS LIST IN HERE

                if sender_uuid in self.uuid_to_name and self.uuid_to_name[sender_uuid] not in self.active_peers:
                    # we add to active peers if this node is not in the active neighbors list yet
                    for p in self.peers:
                        if p["uuid"] == sender_uuid:
                            self.active_peers[self.uuid_to_name[sender_uuid]] = {
                                "uuid" : p["uuid"],
                                "host": p["host"],
                                "backend_port" : p["backend_port"],
                                "metric" : p["metric"]
                            }
                            break
                        
                
            
            # WE KEEP TRACK OF NODE NAMES HERE

            elif message == "Link State Packet":     # Update the map based on new information, drop if old information

                if sender_uuid not in self.uuid_to_seen_seq or sender_seq > self.uuid_to_seen_seq[sender_uuid]:
                    self.uuid_to_seen_seq[sender_uuid] = sender_seq
                    #If new information, also flood to other neighbors
                    sender_name = msg_string["source_name"]
                    sender_seq = msg_string["seq"]
                    sender_neighbors = msg_string["neighbors"]
                    self.uuid_to_name[sender_uuid] = sender_name # important for correct 'neighbors' command format
                    self.map[sender_name] = sender_neighbors
                    
                    # for p in self.peers:
                    #     if p["uuid"] == sender_uuid:
                    #         if self.uuid in sender_neighbors:
                    #             p["metric"] = sender_neighbors[self.uuid]

                    
                    self.link_state_flood(time.time(), client_address, msg_string)

            # TODO: IMPLEMENT AFTER

            # implement this after, asking prof. bc spec. says we cant do this
            # elif message == "Death message": # Delete the node if it sends the message before executing kill.
                
            #     pass
            # # otherwise the msg is dropped

    def timeout_old(self):
        # drop the neighbors whose information is old
        while self.remain_threads:
            current_time = time.time()

            for uuid in list(self.uuid_to_last_alive):
                last_seen_time = self.uuid_to_last_alive[uuid]
                if current_time -last_seen_time > TIMEOUT_INTERVAL:
                    self.peers = [p for p in self.peers if p["uuid"] != uuid]

                    del self.uuid_to_last_alive[uuid]

                    if uuid in self.uuid_to_name:
                        if self.uuid_to_name[uuid] in self.map:
                            del self.map[self.uuid_to_name[uuid]]
                        if self.uuid_to_name[uuid] in self.active_peers:
                            del self.active_peers[self.uuid_to_name[uuid]]


                     
                    # can trigger LSA update right here
            

            time.sleep(ALIVE_SGN_INTERVAL)



    # Dijkstras shortest path algorithm
    def shortest_path(self):
        # derive the shortest path according to the current link state
        graph = self.map.copy()
        source_node_connections = {}
        for name, stats in self.active_peers.items():
            source_node_connections[name] = stats["metric"]
        # for p in self.peers:
        #     neighbor = self.uuid_to_name.get(p["uuid"])
        #     source_node_connections[neighbor] = p["metric"]
        graph[self.name] = source_node_connections

        # now this graph includes the source node and its connections




        # this can serve as our distance table. in Dijktras init source = 0
        # and everything else as infinity distance
        rank = {}
        # node_name -> shortest distance from source node

        pq = [] # priority queue of unvisited nodes (including source)
        # contains tuple (weight, name)

        rank[self.name] = 0 # dist = 0 for source node
        for node in graph:
            if node == self.name:
                continue
            rank[node] = float('inf')

        heapq.heappush(pq, (0, self.name)) # push our source node onto the priority queue

        
        while pq:
            curr_weight, curr_name = heapq.heappop(pq)

            if curr_weight > rank[curr_name]:
                continue # alr found a good path

            if rank[curr_name] == float('inf'):
                break # if smallest dist is infinity, remaining are also inf

            for neighbor, weight in graph[curr_name].items():
                if neighbor not in rank:
                    rank[neighbor] = float('inf') # added this line in case threads unpredict.
                new_dist = curr_weight + weight
                if new_dist < rank[neighbor]:
                    rank[neighbor] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor))
                
        del rank[self.name]

        

        

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
                self.remain_threads = False
                try:
                    self.dl_socket.close()
                except:
                    pass
                sys.exit(0) # this allows to exit the main proccess

            elif command == "uuid":
                print(str({"uuid": self.uuid}))
            elif command == "neighbors": # complete this after completed link_state_adv()
                # Print Neighbor information
                print("{\"neighbors\": " + str(self.active_peers) + "}")
            elif command == "addneighbor":
                # Update Neighbor List with new neighbor
                cmd_uuid = command_line[1]
                cmd_uuid = cmd_uuid[cmd_uuid.index('=')+1:len(cmd_uuid)]

                cmd_host = command_line[2]
                cmd_host = cmd_host[cmd_host.index('=')+1:len(cmd_host)]

                cmd_backend_port = command_line[3]
                cmd_backend_port = cmd_backend_port[cmd_backend_port.index('=')+1:len(cmd_backend_port)]


                cmd_metric = command_line[4]
                cmd_metric = cmd_metric[cmd_metric.index('=')+1:len(cmd_metric)]

                self.addneighbor(cmd_uuid, cmd_host, int(cmd_backend_port), int(cmd_metric))
            elif command == "map":
                # Print Map
                res_map = self.map.copy()
                res_map[self.name] = {self.uuid_to_name.get(p['uuid'], p['uuid']) : p['metric'] for p in self.peers}
                print("{\"map\": " + str(res_map) + "}")
            elif command == "rank": 
                # Compute and print the shortest path to each node in POV of source node
                print("{\"rank\": " + str(self.shortest_path()) + "}")

if __name__ == "__main__":
    content_server = Content_server(sys.argv[2])
