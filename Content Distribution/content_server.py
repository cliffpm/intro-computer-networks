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
        self.active_peers_uuid = {}


        #node name : {node name : {neighbor name : distance}}
        self.map = {} 
        
        # uuid -> last timestamp alive
        self.uuid_to_last_alive = {} 

        # uuid -> last sequence number
        self.uuid_to_seen_seq = {}
        

        # uuid -> name . This fills when we get an LSA packet
        self.uuid_to_name = {} 

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
                    self.peer_count = int(value)
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

        self.uuid_to_name[self.uuid] = self.name



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
        time.sleep(2)
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
        # we let population of active neighbor logic to be handled
        #   in the listen() function if message == "alive"

        # maybe add a flag to alert link_state_adv to start sending out
        # LSA packets
        return
    

    # this is sending updates every 30 seconds or so, so the graph is most updated
    #increment sequence number in here. 
    # IMPORTANT: send LSA packets to only ACTIVE neighbors only
    def link_state_adv(self):
        while self.remain_threads:
            # print("sending LSA packet ...")
            # Perform Link State Advertisement to all your neighbors periodically 
            self.seq += 1

            neighbor_metrics = {}

            for uuid, stats in self.active_peers_uuid.items():
                active_neighbor_metric = stats["metric"]
                neighbor_metrics[uuid] = active_neighbor_metric
            
            lsa_packet = {
                "message": "Link State Packet",
                "source_uuid" : self.uuid,
                "source_name" : self.name,
                "neighbors": neighbor_metrics, #include a neighbor map here of their uuid and the distance
                "seq": self.seq
            }
            for uuid, active_neighbor_stats in list(self.active_peers_uuid.items()):
                ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try :
                    ul_socket.connect(('127.0.0.1', active_neighbor_stats["backend_port"]))
                    ul_socket.send((str(lsa_packet)).encode())
                    ul_socket.close()
                except socket.error:
                    #print("socket failed LSA : ", socket.error)
                    continue
            time.sleep(3) # send LSA packet every 3 seconds
        return

    # this function simply FORWARDS MESSAGES. NO LOGIC MODIFICATION !!
    def link_state_flood(self, send_time, host, msg):
        # If new information then send to all your neighbors, if old information then drop.
        sender_uuid = msg["source_uuid"]

        # drop old packet HANDLED ALREADY
        # if sender_uuid in self.uuid_to_seen_seq and msg["seq"] <= self.uuid_to_seen_seq[sender_uuid]:
        #     return

        for uuid, active_stats in list(self.active_peers_uuid.items()):
           # active_uuid = active_stats[uuid]
            if uuid == sender_uuid: # do not forward to the node we recieved from
                continue # technically natively handles but this reduces redundant socket sending
            
            active_backend_port = active_stats["backend_port"]
            ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                ul_socket.connect(('127.0.0.1',active_backend_port))
                ul_socket.send((str(msg)).encode())
                ul_socket.close()
            except socket.error:
                #print("socket failed LSA FLOOD : ", socket.error)
                continue
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
             # print("sending keep alive message")
            for neighbor in self.peers: # each neighbor is a dict of uuid, hostname, backendport, distance
                ul_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # dont make it a self. variable to avoid race condition
                try:
                    ul_socket.connect(('127.0.0.1', neighbor["backend_port"]))
                    packet_sending =    {"source_uuid" : self.uuid,
                                        "message" : "Alive message", 
                                        "backend_port" : self.backend_port,
                                        "metric":neighbor["metric"]
                                        }
                    ul_socket.send((str(packet_sending)).encode()) # should send it along with our
                    # current node UUID, so that way in timeout_old, we can distingush
                    # which node sent the keep alive so we can update status dead or alive
                    ul_socket.close()
                # except OSError as e:#socket.error:
                #     print("socket failed KEEP ALIVE : ", repr(e))
                #     continue
                except socket.error:
                    continue
            time.sleep(ALIVE_SGN_INTERVAL)
        return
    
   
   ## THIS IS THE RECEIVE FUNCTION THAT IS RECEIVING THE PACKETS
    def listen(self):
        self.dl_socket.settimeout(0.1)  # for killing the application
        msg_string = ""
        while self.remain_threads:
            try:
                connection_socket, client_address = self.dl_socket.accept()
                msg_string = connection_socket.recv(BUFSIZE).decode()
                
                if not msg_string:
                    continue
                msg_string = ast.literal_eval(msg_string)


                # guranteed in my design, all messages have at least a messsage and source uuid field
                message = msg_string["message"]
                sender_uuid = msg_string["source_uuid"]
                #print(f"message : {message}")

                # print("received", connection_socket, client_address, msg_string)
            # except(SyntaxError, ValueError):
            #     continue
            except socket.timeout:
                msg_string = ""
                continue
            if message == "": 
                continue
            
            
            # we should populate the active neighbors list in here
            # Update the timeout time if known node, otherwise add new neighbor
            # note : this gets sent to every immediate neighbor.
            elif message == "Alive message":

                current_time = time.time()
                self.uuid_to_last_alive[sender_uuid] = current_time


                # need to add logic for new nodes that are just added
                # ex : node 1 and node 2 never were neighbors.

                #
                # we ran addneighbors in node1's process to add node 2.


                # node 2 sees that it has a incoming alive message from a uuid never seen before
                #   but we know alive messages sent to neighbors only. this must mean this never before
                #   seen node (node 2's never seen it) means it should be a neighbor. Therefore we should
                #   add it to the self.peers of node 2.
                #


                known_uuid = [p["uuid"] for p in self.peers]
                if sender_uuid not in known_uuid: # this is new
                    self.peers.append({
                        "uuid": sender_uuid,
                        "host": "localhost",
                        "backend_port": msg_string["backend_port"],
                        "metric":msg_string["metric"]
                    })



            
                    
                # POPULATING ACTIVE NEIGHBORS LIST IN HERE
                # if we have the new nodes name (from LSA) AND it is not currently tracked as an active neighbor

                # Is there an issue when keepAlive message arrive BEFORE LSA ? aka we do not have the proper
                # UUID : Node Name 
                #
                #
                # print("recieved alive message, waiting to populating active peers")

                # this condition is failing because self.uuid to name is not populated yet
                #if sender_uuid in self.uuid_to_name and self.uuid_to_name[sender_uuid] not in self.active_peers:
                    # find the stats. of the new soon to be active node, and add it to the 
                    #   active neighbors list appropriately
                for p in self.peers:
                    if p["uuid"] == sender_uuid:
                        self.active_peers_uuid[sender_uuid] = {
                            "uuid": p["uuid"],
                            "host": p["host"],
                            "backend_port" : p["backend_port"],
                            "metric" : p["metric"]
                        }
                        # self.active_peers[self.uuid_to_name[sender_uuid]] = {
                        #     "uuid" : p["uuid"],
                        #     "host": p["host"],
                        #     "backend_port" : p["backend_port"],
                        #     "metric" : p["metric"]
                        # }
                        break
                #else:
                  #  print("condition to populate active peers failed")
                        
            # WE KEEP TRACK OF NODE NAMES HERE
            elif message == "Link State Packet":     # Update the map based on new information, drop if old information
                # print(f"recieved LSA packet from {sender_uuid}")
                # if uuid hasn't been tracked with a last seen seq, OR the new seq is fresher than the prev seq
                # then we update only.
                sender_seq = msg_string["seq"]



                if sender_uuid not in self.uuid_to_seen_seq or sender_seq > self.uuid_to_seen_seq[sender_uuid]:
                    self.uuid_to_seen_seq[sender_uuid] = sender_seq
                    #If new information, also flood to other neighbors
                    sender_name = msg_string["source_name"]
                    sender_seq = msg_string["seq"]
                    sender_neighbors = msg_string["neighbors"]


                    # if sender_uuid == "4166edb6-85b2-4283-ba20-95036842da17":
                    #     print("we recieved node 4's packet")
                    #     print(f"name : {sender_name}")
                    #     print(f"neighbors : {sender_neighbors}")
                      

                    # KEEPING TRACK OF NODE NAMES HERE !!!!!!!
                    self.uuid_to_name[sender_uuid] = sender_name # important for correct 'neighbors' command format
                    self.map[sender_uuid] = sender_neighbors
                    
                    # now that we updated the info we recieved for our current node, we forward it to all
                    #   other active neighbors via flooding.
                    # print("beginning flooding")
                    self.link_state_flood(time.time(), client_address, msg_string)
               # else:
                  #  print("if condition failed to update graph and flood")
            # TODO: IMPLEMENT AFTER
            # implement this after, asking prof. bc spec. says we cant do this
            # elif message == "Death message": # Delete the node if it sends the message before executing kill.
            #     pass
            # # otherwise the msg is dropped

    def timeout_old(self):
        # drop the neighbors whose information is old from the actives list 
        while self.remain_threads:
            current_time = time.time()
            # if uuid not in self.uuid_to_last_alive:
            #     continue
        
            for uuid in list(self.uuid_to_last_alive.keys()):
                last_seen_time = self.uuid_to_last_alive[uuid]
                if current_time -last_seen_time > TIMEOUT_INTERVAL:
                    # self.peers = [p for p in self.peers if p["uuid"] != uuid]

                    del self.uuid_to_last_alive[uuid]
                    del self.map[uuid]
                    del self.active_peers_uuid[uuid]

                    # if uuid in self.uuid_to_name:
                    #     if self.uuid_to_name[uuid] in self.map:
                    #         del self.map[uuid] # becauase LSA we only rely for NEW information
                    #         #                                           but it does nothing when node gets dropped
                    #         #                                           we must manually track it
                    #     if uuid in self.active_peers_uuid:
                    #         del self.active_peers_uuid[uuid]
                            


                     
                    # can trigger LSA update right here
            

            time.sleep(ALIVE_SGN_INTERVAL)



    # Dijkstras shortest path algorithm
    # lets assume that self.map will give us the proper map
    # we iterate through our DIRECT, ACTIVE neighbors, as with the current implementation, map doesn't have 
    def shortest_path(self):
        graph = self.map.copy()
        source_node_connections = {}
        for uuid, stats in self.active_peers_uuid.items():
            source_node_connections[uuid] = stats["metric"]
        graph[self.uuid] = source_node_connections
        # now this is the proper graph. Just do Dijkstra's next

        # this can serve as our distance table. in Dijktras init source = 0
        # and everything else as infinity distance
        rank = {}

        # node_name -> shortest distance from source node
        pq = [] # priority queue of unvisited nodes :  tuple (weight, name)

        rank[self.uuid] = 0 # dist = 0 for source node
        for node in graph:
            if node == self.uuid:
                continue
            rank[node] = float('inf')

        heapq.heappush(pq, (0, self.uuid)) # push our source node onto the priority queue

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
            
        del rank[self.uuid]

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
                    # this addresses threads that are being blocked w/o connection
                    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    temp_socket.connect(('127.0.0.1', self.backend_port))
                    temp_socket.close()
                except:
                    pass
                    

                try:
                    self.dl_socket.close()
                except:
                    pass
                sys.exit(0) # this allows to exit the main proccess

            elif command == "uuid":
                print(str({"uuid": self.uuid}))
            elif command == "neighbors": # complete this after completed link_state_adv()
                # Print Neighbor information
                res = {}
                for uuid, stats in self.active_peers_uuid.items():
                    res[self.uuid_to_name[uuid]] = stats
                
                #print("{\"neighbors\": " + str(res) + "}", flush=True)
                print({"neighbors":res})
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
     

                return_map = {}
                for source_uuid, neighbors in self.map.items():
                    source_name = self.uuid_to_name[source_uuid] # TODO: potential problem if LSA hasn't arrived yet
                    neighbors_res = {}
                    for destination_uuid, weight in neighbors.items():
                        destination_name = self.uuid_to_name[destination_uuid]
                        neighbors_res[destination_name] = weight

                    return_map[source_name] = neighbors_res

                source_neighbors = {}
                for uuid, stats in self.active_peers_uuid.items():
                    source_neighbors_name = self.uuid_to_name[uuid]
                    distance = stats["metric"]
                    source_neighbors[source_neighbors_name] = distance
                
                

                return_map[self.name] = source_neighbors


                # delete all the ones with distance infinity


                print("{\"map\": " + str(return_map) + "}")

            elif command == "rank": 
                # Compute and print the shortest path to each node in POV of source node
                res = {}

                uuid_rank = self.shortest_path()

                for uuid, shortest_distance in uuid_rank.items():
                    name = self.uuid_to_name[uuid]
                    res[name] = shortest_distance

                temp_res = res.copy()

                for name, distance in temp_res.items():
                    if distance == float('inf'):
                        del res[name]
                


                print("{\"rank\": " + str(res) + "}")
            elif command == "printneighbors":
                print(str(self.peers))

if __name__ == "__main__":
    content_server = Content_server(sys.argv[2])
