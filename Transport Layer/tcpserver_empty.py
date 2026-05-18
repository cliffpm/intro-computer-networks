import socket, sys, json, time, threading, uuid, os
import queue

BUFSIZE     = 102400
PKTSIZE     = 10200
WINDOW_SIZE = 16
TIMEOUT     = 0.5


class Server():
    def __init__(self, config_file):
        self.base_dir = os.path.dirname(os.path.abspath(config_file))

        with open(config_file, "r") as f:
            config = json.load(f)

        self.hostname     = config["hostname"]
        self.port         = config["port"]
        self.peer_count   = config["peers"]
        self.content_info = config["content_info"]
        self.peer_info    = config["peer_info"]
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", self.port))
        self.server_socket.settimeout(0.5)

        self.remain_threads = True

        # fields to support concurrent requests

        self.sessions      = {}   # tid -> queue.Queue
        self.sessions_lock = threading.Lock()
        self._active_tx     = set()  # set of (file, addr) being served
        self._active_tx_lock = threading.Lock()

        self.cli()
        return
    # helper functions

    def _send(self, packet, addr):
        try:
            self.server_socket.sendto(json.dumps(packet).encode(), addr)
        except socket.timeout:
            pass

    def _new_session(self, tid=None):
        if tid is None:
            tid = uuid.uuid4().hex[:8]
        q = queue.Queue()
        with self.sessions_lock:
            self.sessions[tid] = q
        return tid, q

    def _close_session(self, tid):
        with self.sessions_lock:
            self.sessions.pop(tid, None)


    ##

    def find_file(self, file_name):
        for peer in self.peer_info:
            if file_name in peer["content_info"]:
                return peer["hostname"], peer["port"]
        return None, None






    def load_file(self, file_name):
        hostname, port = self.find_file(file_name)

        peer_addr = (hostname, port)
        tid, q    = self._new_session()
        SYN_packet   = {"type": "SYN", "file": file_name, "tid": tid}

        packet_num = None


        # inititate three way handshake and also get the number of packets

        while packet_num is None and self.remain_threads:
            self._send(SYN_packet, peer_addr)
            try:
                pkt, _ = q.get(timeout=TIMEOUT)
                if pkt.get("type") == "COUNT":
                    packet_num = pkt["count"]
                    self._send({"type": "COUNT-ACK", "tid": tid}, peer_addr)
            except queue.Empty:
                continue

        if packet_num is None:
            self._close_session(tid)
            return

        received   = {}
        fin_seen   = False
        last_reack = time.time()

        while len(received) < packet_num and self.remain_threads:
            now = time.time()
            if now - last_reack > TIMEOUT:
                for seq in list(received.keys()):
                    self._send({"type": "ACK", "seq": seq, "tid": tid}, peer_addr)
                last_reack = now

            try:
                pkt, _ = q.get(timeout=TIMEOUT)
            except queue.Empty:
                if fin_seen:
                    break
                continue

            ptype = pkt.get("type")
            if ptype == "FIN":
                fin_seen = True
                #break
                continue
            if ptype != "DATA":
                continue

            seq = pkt.get("seq", -1)
            if seq not in received:
                received[seq] = bytes.fromhex(pkt["data"])
            self._send({"type": "ACK", "seq": seq, "tid": tid}, peer_addr)

        self._close_session(tid)


        # Write to same directory as the config file
        out_path = os.path.join(self.base_dir, file_name)
        with open(out_path, "wb") as f:
            for i in range(packet_num):
                f.write(received[i])


    def read_file(self, file_name):
        # Resolve relative to config directory
        path = os.path.join(self.base_dir, file_name)
        out  = []
        with open(path, "rb") as f:
            seq = 0
            while True:
                chunk = f.read(PKTSIZE)
                if not chunk:
                    break
                out.append({"type": "DATA", "seq": seq, "data": chunk.hex()})
                seq += 1
        return out



    def transmit(self, file_name, addr, tid):
        #print(f"[transmit] started for {file_name}")
        with self.sessions_lock:
            q = self.sessions.get(tid)
        if q is None:
            return

        try:
            pkts = self.read_file(file_name)
        except FileNotFoundError:
            self._close_session(tid)
            with self._active_tx_lock:
                self._active_tx.discard(tid)
            return

        packet_num = len(pkts)

        count_pkt = {"type": "COUNT", "tid": tid, "count": packet_num}
        while self.remain_threads:
            self._send(count_pkt, addr)
            try:
                pkt, _ = q.get(timeout=TIMEOUT)
                if pkt.get("type") == "COUNT-ACK":
                    break
            except queue.Empty:
                continue

        acked    = [False] * packet_num
        timers   = [0.0]   * packet_num
        base     = 0
        next_ptr = 0
        lock     = threading.Lock()
        done     = threading.Event()

        def tx_loop():
            nonlocal next_ptr, base
            while not done.is_set() and self.remain_threads:
                with lock:
                    while next_ptr < packet_num and next_ptr < base + WINDOW_SIZE:
                        p = dict(pkts[next_ptr]); p["tid"] = tid
                        self._send(p, addr)
                        timers[next_ptr] = time.time()
                        next_ptr += 1
                    now = time.time()
                    for i in range(base, next_ptr):
                        if not acked[i] and now - timers[i] > TIMEOUT:
                            p = dict(pkts[i]); p["tid"] = tid
                            self._send(p, addr)
                            timers[i] = now
                time.sleep(0.001)

        def ack_loop():
            nonlocal base
            while not done.is_set() and self.remain_threads:
                try:
                    pkt, _ = q.get(timeout=TIMEOUT)
                except queue.Empty:
                    continue
                if pkt.get("type") != "ACK":
                    continue
                seq = pkt.get("seq", -1)
                with lock:
                    if 0 <= seq < packet_num:
                        acked[seq] = True
                    while base < packet_num and acked[base]:
                        base += 1
                    if base >= packet_num:
                        done.set()

        t1 = threading.Thread(target=tx_loop, daemon=True)
        t2 = threading.Thread(target=ack_loop, daemon=True)
        t1.start(); t2.start()

        while base < packet_num and self.remain_threads:
            time.sleep(0.05)

        done.set()
        t1.join(timeout=1); t2.join(timeout=1)

     
        fin_pkt = {"type": "FIN", "tid": tid}
        for _ in range(5):
            self._send(fin_pkt, addr)
            time.sleep(0.05)

        self._close_session(tid)
        with self._active_tx_lock:
            self._active_tx.discard(tid)


    def listener(self):
        while self.remain_threads:
            try:
                raw, addr = self.server_socket.recvfrom(BUFSIZE)
                #print(f"[listener] received {len(raw)} bytes from {addr}")
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                pkt = json.loads(raw.decode())
            except Exception:
                continue

            ptype = pkt.get("type", "")

            #print(f"[listener] got ptype={ptype} from {addr}", flush=True)

            if ptype == "SYN":
                tid       = pkt["tid"]
                file_name = pkt["file"]
                key       = (file_name, addr, tid)

                with self._active_tx_lock:
                    already = tid in self._active_tx
                    if not already:
                        self._active_tx.add(tid)

                if already:
                    continue

                with self.sessions_lock:
                    self.sessions[tid] = queue.Queue()

                t = threading.Thread(
                    target=self.transmit,
                    args=(file_name, addr, tid),
                    daemon=True
                )
                t.start()
                continue

            tid = pkt.get("tid")
            if tid is None:
                continue
            with self.sessions_lock:
                q = self.sessions.get(tid)
            if q is not None:
                q.put((pkt, addr))





    def cli(self):
        lt = threading.Thread(target=self.listener, daemon=True)
        lt.start()

        while self.remain_threads:
            try:
                cmd = input()
            except EOFError:
                break

            cmd = cmd.strip()
            if cmd == "kill":
                self.remain_threads = False
                try:
                    self.server_socket.close()
                except OSError:
                    pass
                break
            elif cmd:
                threading.Thread(
                    target=self.load_file,
                    args=(cmd,),
                    daemon=True
                ).start()

        lt.join(timeout=2)


if __name__ == "__main__":
    server = Server(sys.argv[1])