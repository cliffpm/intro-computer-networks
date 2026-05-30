import socket, sys
import datetime
import threading
import os

BUFSIZE = 1024
LARGEST_CONTENT_SIZE = 5242880

class Vod_Server():
    def __init__(self, port_id):
        # create an HTTP port to listen to
        self.http_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.http_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.http_socket.bind(("", port_id))
        self.http_socket.listen(10000)
        self.remain_threads = True

        # load all contents in the buffer
        self.load_contents(os.path.join(os.getcwd(),"content"))
        # listen to the http socket
        self.listen()
        

    def load_contents(self, dir):
        #Create a list of files and stuff that you have
        self.lut = {}
        for root, directory, files in os.walk(dir):
            for file in files:
                abs_path = os.path.join(root,file)

                url = "/" + os.path.relpath(abs_path, dir).replace("\\","/")
                self.lut[url] = abs_path
                    



        return

    def listen(self):
        while self.remain_threads:
            connection_socket, client_address = self.http_socket.accept()

            thread = threading.Thread(target=self.handler, args = (connection_socket,client_address))
            thread.start()

            #Do stuff here
        return

    def handler(self, connection_socket, client_addr):
        try:
            while True:
                msg_string = connection_socket.recv(BUFSIZE).decode()
                if not msg_string: break

                keep_alive = self.response(msg_string, connection_socket)
                if not keep_alive: break

        except Exception as e:
            pass
        finally:
            connection_socket.close()

    def date_header(self):
        return datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    def response(self, msg_string, connection_socket):
        #Do based on the situation if the files exist, do not exist or are unable to respond due to confidentiality
        try:
            commands = msg_string.split("\r\n")
            first = commands[0].split(" ")
            method = first[0]
            url = first[1]
            version = first[2]

            cmd_parameters = self.eval_commands(commands)

            if url.startswith("/confidential"):
                return self.generate_response_403(version, connection_socket)
            
            if url not in self.lut:
                return self.generate_response_404(version, connection_socket)
            
            path = self.lut[url]
            type = os.path.splitext(url)[1]

            if "Range" in cmd_parameters:
                return self.generate_response_206(version, path, type, cmd_parameters, connection_socket)
            
            return self.generate_response_200(version, path, type, connection_socket)
        
        except Exception as e:
            return False
        return
    
    def generate_response_404(self, http_version, connection_socket):
        #Generate Response and Send
        date = self.date_header()
        with open(self.lut["/404_not_found.html"], "rb") as f:
            body = f.read()
        
        header = (
            f"{http_version} 404 Not Found\r\n"
            f"Date: {date}\r\n" 
            f"Content-Type: text/html\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: Keep-Alive\r\n"
            f"\r\n"
        )

        connection_socket.sendall(header.encode() +body)
        response= True
        return response

    def generate_response_403(self, http_version, connection_socket):
        #Generate Response and Send
        
        date = self.date_header()
        header = (
            f"{http_version} 403 Forbidden\r\n"
            f"Date: {date}\r\n" 
            f"Content-Length: 0\r\n"
            f"Connection: Keep-Alive\r\n"
            f"\r\n"
        )
        connection_socket.sendall(header.encode())
        response= True
        return response
    
    def generate_response_200(self, http_version, file_idx, file_type, connection_socket):
        #Generate Response and Send
        date = self.date_header()
        last_modified_timestamp = os.path.getmtime(file_idx)
        last_modified = datetime.datetime.fromtimestamp(last_modified_timestamp, datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

        type = self.generate_content_type(file_type)

        with open(file_idx, "rb") as f:
            body = f.read()
        
        header = (
            f"{http_version} 200 OK\r\n"
            f"Date: {date}\r\n" 
            f"Last-Modified: {last_modified}\r\n"
            f"Content-Type: {type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Accept-Ranges: bytes\r\n"
            f"Connection: Keep-Alive\r\n"
            f"\r\n"
        )
        connection_socket.sendall(header.encode() + body)
        response = True
        return response

    def generate_response_206(self, http_version, file_idx, file_type, command_parameters, connection_socket):
        #Generate Response and Send
        date = self.date_header()
        last_modified_timestamp = os.path.getmtime(file_idx)
        last_modified = datetime.datetime.fromtimestamp(last_modified_timestamp, datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        content_type = self.generate_content_type(file_type)
        file_size = os.path.getsize(file_idx)

        range_value = command_parameters["Range"].strip()
        range_value = range_value.replace("bytes=","")
        start_end = range_value.split("-")
        start = int(start_end[0])

        if start_end[1] == "":
            end = min(start + LARGEST_CONTENT_SIZE-1, file_size-1)
        else:
            end = int(start_end[1])
        
        end = min(end, file_size-1)
        chunk = end-start + 1
        with open(file_idx, "rb") as f:
            f.seek(start)
            body = f.read(chunk)
        
        header = (
            f"{http_version} 206 Partial Content\r\n"
            f"Date: {date}\r\n" 
            f"Last-Modified: {last_modified}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {chunk}\r\n"
            f"Content-Range: bytes {start}-{end}/{file_size}\r\n"
            f"Accept-Ranges: bytes\r\n"
            f"Connection: Keep-Alive\r\n"
            f"\r\n"
        )

        connection_socket.sendall(header.encode() + body)
        response = True
        return response

    def generate_content_type(self, file_type):
        content_types = {
            ".txt":  "text/plain",
            ".css":  "text/css",
            ".htm":  "text/html",
            ".html": "text/html",
            ".gif":  "image/gif",
            ".jpg":  "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png":  "image/png",
            ".mp4":  "video/mp4",
            ".webm": "video/webm",
            ".ogg":  "video/webm",
            ".js":   "application/javascript"
        }
        return content_types.get(file_type, "application/octet-stream")

    def eval_commands(self, commands):
        command_dict = {}
        for item in commands[1:]:
            item = item.rstrip()
            splitted_item = item.split(":")
            command_dict[splitted_item[0]] = splitted_item[1].strip()
        return command_dict

if __name__ == "__main__":
    Vod_Server(int(sys.argv[1]))