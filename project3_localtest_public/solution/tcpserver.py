import socket, sys
import json
import time
import threading
import os
import uuid
import queue

BUFSIZE = 102400  # size of receiving buffer
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
        # self.active_tx = set() # set of tuple (file, address)
        # self.active_tx_lock = threading.Lock()

        self.remain_threads = True
        self.cli()
        return

    def send(self, packet, addr):
        try:
            self.server_socket.sendto(json.dumps(packet).encode(), addr)
        except socket.timeout:
            pass

    # helper function to support concurrency
    def new_session(self, transaction_id = None):
        if transaction_id is None:
            transaction_id = uuid.uuid4().hex[:8] # 7 bit unique transaction id for each client(s)
        q = queue.Queue() # use this instead of a list because queue module in python is thread safe
        with self.sessions_lock:
            self.sessions[transaction_id] = q
        return transaction_id, q

    def close_session(self, transaction_id):
        with self.sessions_lock:
            del self.sessions[transaction_id]

    
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
            except queue.Empty:
                continue
        

      
        # the receiver keeps a record for which part has been acked
        recieved = {}
        FIN_recieved = False # flag where client says that they have recieved all their data
        previous_time = time.time()

        # start receiving file
        while len(recieved) < packet_num and self.remain_threads:
            current_time = time.time()
            # if (current_time - previous_time > TIMEOUT):
            #     for sequence in list(recieved.keys()):
            #         ACK_packet = {
            #             "type": "ACK",
            #             "sequence_number" : sequence, # sequence is the index
            #             "transaction_id" : transaction_id
            #         }
            #         self.send(ACK_packet, addr)
            #     previous_time = current_time
            try:
                packet, recieved_addr2 = q.get(timeout=TIMEOUT)
            except queue.Empty:
                if FIN_recieved and len(recieved) == packet_num:
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
                    "sequence_number" : seq,
                    "data" : chunk.hex() # because JSON does not natively handle binary data
                }
                transmit_file.append(DATA_packet)
                seq += 1
        #You can write a function that takes the file to be transmitted and converts into chunks of packet_size
        return transmit_file

    def transmit(self, file_name, addr, transaction_id):
        with self.sessions_lock:
            q = self.sessions.get(transaction_id)
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
        def transmit_thread():
            nonlocal left
            while self.remain_threads:
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
                time.sleep(.001)

            #Takes the transmit window and transmits every packet that is allowed to be transmitted
            return
        
        def ack_thread():
            #Receives acknowledgement and updates the transmit window with sendable packets
            nonlocal left
            while self.remain_threads:
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

                    while left < packet_num and timeout_array[left] == -1:
                        left += 1


        tx_thread = threading.Thread(target=transmit_thread)
        ak_thread = threading.Thread(target = ack_thread)

        tx_thread.start()
        ak_thread.start()

        while left < packet_num and self.remain_threads:
            time.sleep(.01)

        # transmitting = False # that way ack and tx thread doesn't loop forever
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
        # with self.active_tx_lock:
        #     self.active_tx.discard(transaction_id)

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
            # start transmission
            #Create a transmit thread (HINT : you can have a large array of transmit threads if you want) and start it
            try:
                packet = json.loads(file_name.decode())
            except Exception:
                continue
            transaction_id = packet["transaction_id"]
            if packet["type"] == "SYN":
                file_name = packet["file"]

                with self.sessions_lock:
                    if transaction_id in self.sessions:
                        continue
                    self.sessions[transaction_id] = queue.Queue()
                # with self.active_tx_lock:
                #     if transaction_id in self.active_tx:
                #         continue
                #     self.active_tx.add(transaction_id)
                
                # with self.sessions_lock:
                #     self.sessions[transaction_id] = queue.Queue()
                
                tx_thread = threading.Thread(target = self.transmit, args = (file_name, addr, transaction_id))
                tx_thread.start()
                continue
            
            with self.sessions_lock:
                q = self.sessions.get(transaction_id)
            if q is not None:
                q.put((packet, addr))

                
        return
    
    def cli(self):  # cli interface for input of the file name
        listen_thread = threading.Thread(target=self.listener)
        listen_thread.start()

        while self.remain_threads:
            try:
                command_line = input()
            except EOFError:
                break
            command_line = command_line.strip()
            if command_line == "kill":  # for debugging purpose
                self.remain_threads = False
                try:
                    self.server_socket.close()
                except socket.timeout:
                    pass
                break
                
            else:
                start_thread = threading.Thread(target=self.load_file, args=(command_line,))
                start_thread.start()
        
        listen_thread.join()
        

if __name__ == "__main__":
    server = Server(sys.argv[1])

# import socket, sys, json, time, threading, uuid, os
# import queue

# BUFSIZE     = 102400
# PKTSIZE     = 10200
# WINDOW_SIZE = 16
# TIMEOUT     = 0.5


# class Server():
#     def __init__(self, config_file):
#         print(f"CWD={os.getcwd()}, config={config_file}, abspath={os.path.abspath(config_file)}", flush=True)
#         self.base_dir = os.path.dirname(os.path.abspath(config_file))

#         with open(config_file, "r") as f:
#             config = json.load(f)

#         self.hostname     = config["hostname"]
#         self.port         = config["port"]
#         self.peer_count   = config["peers"]
#         self.content_info = config["content_info"]
#         self.peer_info    = config["peer_info"]

#         self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#         self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         self.sock.bind(("127.0.0.1", self.port))
#         self.sock.settimeout(0.2)

#         self.remain_threads = True

#         self._sessions      = {}   # tid -> queue.Queue
#         self._sessions_lock = threading.Lock()
#         self._active_tx     = set()  # set of (file, addr) being served
#         self._active_tx_lock = threading.Lock()

#         self.cli()

#     # helper functions

#     def _send(self, pkt, addr):
#         try:
#             self.sock.sendto(json.dumps(pkt).encode(), addr)
#             print(f"[send] sent {pkt.get('type')} to {addr}", flush=True)
#         except OSError as e:
#             print(f"[send] ERROR: {e}", flush=True)

#     def _new_session(self, tid=None):
#         if tid is None:
#             tid = uuid.uuid4().hex[:8]
#         q = queue.Queue()
#         with self._sessions_lock:
#             self._sessions[tid] = q
#         return tid, q

#     def _close_session(self, tid):
#         with self._sessions_lock:
#             self._sessions.pop(tid, None)


#     ##

#     def find_file(self, file_name):
#         for peer in self.peer_info:
#             if file_name in peer["content_info"]:
#                 return peer["hostname"], peer["port"]
#         return None, None


#     def listener(self):
#         print(f"[listener] started on port {self.port}", flush=True)
#         while self.remain_threads:
#             try:
#                 raw, addr = self.sock.recvfrom(BUFSIZE)
#                 print(f"[listener] received {len(raw)} bytes from {addr}", flush=True)
#             except socket.timeout:
#                 continue
#             except OSError:
#                 break

#             try:
#                 pkt = json.loads(raw.decode())
#             except Exception:
#                 continue

#             ptype = pkt.get("type", "")

#             print(f"[listener] got ptype={ptype} from {addr}", flush=True)

#             if ptype == "REQUEST":
#                 tid       = pkt["tid"]
#                 file_name = pkt["file"]
#                 key       = (file_name, addr, tid)

#                 with self._active_tx_lock:
#                     already = tid in self._active_tx
#                     if not already:
#                         self._active_tx.add(tid)

#                 if already:
#                     continue

#                 with self._sessions_lock:
#                     self._sessions[tid] = queue.Queue()

#                 t = threading.Thread(
#                     target=self.transmit,
#                     args=(file_name, addr, tid),
#                     daemon=True
#                 )
#                 t.start()
#                 continue

#             tid = pkt.get("tid")
#             if tid is None:
#                 continue
#             with self._sessions_lock:
#                 q = self._sessions.get(tid)
#             if q is not None:
#                 q.put((pkt, addr))


#     def read_file(self, file_name):
#         # Resolve relative to config directory
#         path = os.path.join(self.base_dir, file_name)
#         out  = []
#         with open(path, "rb") as f:
#             seq = 0
#             while True:
#                 chunk = f.read(PKTSIZE)
#                 if not chunk:
#                     break
#                 out.append({"type": "DATA", "seq": seq, "data": chunk.hex()})
#                 seq += 1
#         return out

#     def transmit(self, file_name, addr, tid):
#         print(f"[transmit] started for {file_name}", flush=True)
#         with self._sessions_lock:
#             q = self._sessions.get(tid)
#         if q is None:
#             return

#         try:
#             pkts = self.read_file(file_name)
#         except FileNotFoundError:
#             self._close_session(tid)
#             with self._active_tx_lock:
#                 self._active_tx.discard(tid)
#             return

#         packet_num = len(pkts)

#         count_pkt = {"type": "COUNT", "tid": tid, "count": packet_num}
#         while self.remain_threads:
#             self._send(count_pkt, addr)
#             try:
#                 pkt, _ = q.get(timeout=TIMEOUT)
#                 if pkt.get("type") == "COUNT-ACK":
#                     break
#             except queue.Empty:
#                 continue

#         acked    = [False] * packet_num
#         timers   = [0.0]   * packet_num
#         base     = 0
#         next_ptr = 0
#         lock     = threading.Lock()
#         done     = threading.Event()

#         def tx_loop():
#             nonlocal next_ptr, base
#             while not done.is_set() and self.remain_threads:
#                 with lock:
#                     while next_ptr < packet_num and next_ptr < base + WINDOW_SIZE:
#                         p = dict(pkts[next_ptr]); p["tid"] = tid
#                         self._send(p, addr)
#                         timers[next_ptr] = time.time()
#                         next_ptr += 1
#                     now = time.time()
#                     for i in range(base, next_ptr):
#                         if not acked[i] and now - timers[i] > TIMEOUT:
#                             p = dict(pkts[i]); p["tid"] = tid
#                             self._send(p, addr)
#                             timers[i] = now
#                 time.sleep(0.001)

#         def ack_loop():
#             nonlocal base
#             while not done.is_set() and self.remain_threads:
#                 try:
#                     pkt, _ = q.get(timeout=TIMEOUT)
#                 except queue.Empty:
#                     continue
#                 if pkt.get("type") != "ACK":
#                     continue
#                 seq = pkt.get("seq", -1)
#                 with lock:
#                     if 0 <= seq < packet_num:
#                         acked[seq] = True
#                     while base < packet_num and acked[base]:
#                         base += 1
#                     if base >= packet_num:
#                         done.set()

#         t1 = threading.Thread(target=tx_loop, daemon=True)
#         t2 = threading.Thread(target=ack_loop, daemon=True)
#         t1.start(); t2.start()

#         while base < packet_num and self.remain_threads:
#             time.sleep(0.05)

#         done.set()
#         t1.join(timeout=1); t2.join(timeout=1)

     
#         fin_pkt = {"type": "FIN", "tid": tid}
#         for _ in range(5):
#             self._send(fin_pkt, addr)
#             time.sleep(0.05)

#         self._close_session(tid)
#         with self._active_tx_lock:
#             self._active_tx.discard(tid)


#     def load_file(self, file_name):
#         hostname, port = self.find_file(file_name)
#         print(f"[load_file] {file_name} -> {hostname}:{port}", flush=True)
#         if hostname is None:
#             print(f"File {file_name} not found in any peer.")
#             return

#         peer_addr = (hostname, port)
#         tid, q    = self._new_session()
#         req_pkt   = {"type": "REQUEST", "file": file_name, "tid": tid}

#         packet_num = None
#         while packet_num is None and self.remain_threads:
#             self._send(req_pkt, peer_addr)
#             try:
#                 pkt, _ = q.get(timeout=TIMEOUT)
#                 if pkt.get("type") == "COUNT":
#                     packet_num = pkt["count"]
#                     self._send({"type": "COUNT-ACK", "tid": tid}, peer_addr)
#             except queue.Empty:
#                 continue

#         if packet_num is None:
#             self._close_session(tid)
#             return

#         received   = {}
#         fin_seen   = False
#         last_reack = time.time()

#         while len(received) < packet_num and self.remain_threads:
#             now = time.time()
#             if now - last_reack > TIMEOUT:
#                 for seq in list(received.keys()):
#                     self._send({"type": "ACK", "seq": seq, "tid": tid}, peer_addr)
#                 last_reack = now

#             try:
#                 pkt, _ = q.get(timeout=TIMEOUT)
#             except queue.Empty:
#                 if fin_seen:
#                     break
#                 continue

#             ptype = pkt.get("type")
#             if ptype == "FIN":
#                 fin_seen = True
#                 #break
#                 continue
#             if ptype != "DATA":
#                 continue

#             seq = pkt.get("seq", -1)
#             if seq not in received:
#                 received[seq] = bytes.fromhex(pkt["data"])
#             self._send({"type": "ACK", "seq": seq, "tid": tid}, peer_addr)

#         self._close_session(tid)

#         if len(received) < packet_num:
#             print(f"Incomplete: {len(received)}/{packet_num} for {file_name}")
#             return

#         # Write to same directory as the config file
#         out_path = os.path.join(self.base_dir, file_name)
#         with open(out_path, "wb") as f:
#             for i in range(packet_num):
#                 f.write(received[i])


#     def cli(self):
#         lt = threading.Thread(target=self.listener, daemon=True)
#         lt.start()

#         while self.remain_threads:
#             try:
#                 cmd = input()
#             except EOFError:
#                 break

#             cmd = cmd.strip()
#             if cmd == "kill":
#                 self.remain_threads = False
#                 try:
#                     self.sock.close()
#                 except OSError:
#                     pass
#                 break
#             elif cmd:
#                 threading.Thread(
#                     target=self.load_file,
#                     args=(cmd,),
#                     daemon=True
#                 ).start()

#         lt.join(timeout=2)


# if __name__ == "__main__":
#     server = Server(sys.argv[1])