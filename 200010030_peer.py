import os
import random
import socket
import sys
import threading

# get the ip and port of the manager
ip = input("Enter the ip of the manager: ")
# ip = "localhost"
port = int(input("Enter the port of the manager: "))
# port = 1234
MY_PORT = int(input("Enter the port of this peer: "))

MANAGER_ADDR = (ip, port)
BUFF_SIZE = 1024


peers_lock = threading.Lock()
shared_files_lock = threading.Lock()

# Initialize the Peer
active_peers = []
shared_files = {}

# Define a function to connect to the Manager and get the list of active peers
def connect_to_manager():
    global active_peers
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(MANAGER_ADDR)
    sock.send(f"CONNECT 127.0.0.1 {MY_PORT}".encode())
    data = sock.recv(BUFF_SIZE)
    peer_list = data.decode().split(",")
    active_peers = [(peer.split(":")[0], int(peer.split(":")[1])) for peer in peer_list if peer != ""]
    sock.close()

# Define a function to handle incoming file transfer requests
def handle_file_request(sock, addr, request):
    global shared_files
    print(f"File request from {addr}")
    # Receive file request
    if request[0] == "REQUEST":
        file_name = request[1]
        start_byte = int(request[2])
        end_byte = int(request[3])
        # Check if file is available
        if file_name in shared_files:
            file_size = len(shared_files[file_name])
            if start_byte < file_size:
                # Send requested file fragment
                if end_byte >= file_size:
                    end_byte = file_size - 1
                sock.sendall(shared_files[file_name][start_byte:end_byte+1])
                print(f"Sent file fragment {start_byte}-{end_byte} of {file_name} to {addr}")
        else:
            print(f"File {file_name} not available.")

    # Close connection
    sock.close()

# Define a function to handle incoming connections from peers
def handle_manager(data):
    # Receive peer information
    peer_info = data.decode().split()
    if peer_info[0] == "PEERS":
        global active_peers
        peers_lock.acquire()
        active_peers.clear()
        active_peers = [(peer.split(":")[0], int(peer.split(":")[1])) for peer in peer_info[1].split(",") if peer != ""]
        peers_lock.release()
    # Close connection
    # print(f"Active peers: {active_peers}")

# Define a function to handle incoming connections
def handle_connection(sock, addr):
    data = sock.recv(BUFF_SIZE)
    request = data.decode().split()
    if request[0] == "PEERS":
        handle_manager(data)
        sock.close()
    elif request[0] == "REQUEST":
        handle_file_request(sock, addr, request)
    elif request[0] == "PING":
        sock.send("PONG".encode())
        sock.close()
    elif request[0] == "FIND":
        if request[1] in shared_files:
            sock.send(f"FOUND {len(shared_files[request[1]])}".encode())
        else:
            sock.send("NOT_FOUND".encode())
        sock.close()
    else:
        sock.close()

# Define a function to start the Peer
def start_peer():
    global MY_PORT
    # Connect to the Manager
    # Start listening for incoming connections
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", MY_PORT))
    connect_to_manager()
    sock.listen(5)
    try:
        while True:
            conn, addr = sock.accept()
            threading.Thread(target=handle_connection, args=(conn, addr)).start()
    except KeyboardInterrupt:
        sock.close()

def list_all_peers():
    peers_lock.acquire()
    print("IP\t\tPort")
    for peer in active_peers:
        print(f"{peer[0]}\t{peer[1]}")
    peers_lock.release()

def list_all_files():
    shared_files_lock.acquire()
    print("File name\t\tFile size")
    for file_name in shared_files:
        print(f"{file_name}\t{len(shared_files[file_name])}")
    shared_files_lock.release()

def add_file():
    file_name = input("Enter file path: ")
    try:
        with open(file_name, "rb") as f:
            file_name = os.path.basename(file_name)
            shared_files_lock.acquire()
            shared_files[file_name] = f.read()
            shared_files_lock.release()
    except FileNotFoundError:
        print("File not found.")

def download_chunk(file_name, start_byte, end_byte, peer, all_peers, tries=0):
    if tries == 3:
        print("Download failed.")
        return False
    global active_peers, shared_files
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(peer)
        sock.send(f"REQUEST {file_name} {start_byte} {end_byte}".encode())
        data = sock.recv(BUFF_SIZE)
        shared_files_lock.acquire()
        shared_files[file_name][start_byte:end_byte+1] = data
        shared_files_lock.release()
        sock.close()
    except:
        rand_peer = random.choice(all_peers)
        print(f"Error fetching file fragment from {peer}.")
        print(f"reasoning: {sys.exc_info()[0]}")
        # download_chunk(file_name, start_byte, end_byte, rand_peer, all_peers, tries+1)
        return False

def download_sequentially(file_name, peer, all_peers, chunks):
    for chunk in chunks:
        start_byte = chunk[0]
        end_byte = chunk[1]
        download_chunk(file_name, start_byte, end_byte, peer, all_peers)



def request_file():
    file_name = input("Enter file name: ")
    available_peers = []
    total_size = 0
    peers_lock.acquire()
    for peer in active_peers:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(peer)
        sock.send(f"FIND {file_name}".encode())
        data = sock.recv(BUFF_SIZE)
        data = data.decode().split()
        if data[0] == "FOUND":
            available_peers.append(peer)
            total_size = int(data[1])
        sock.close()
    peers_lock.release()
    if len(available_peers) == 0:
        print("File not found in peer network.")
        return
    print(f"No. of available peers: {available_peers}")
    print("Starting download...")
    # Create chunks
    chunk_size = 1000
    chunks = []
    for i in range(0, total_size, chunk_size):
        chunks.append((i, min(i+chunk_size-1, total_size-1)))
    file_buffer = bytearray(total_size)
    shared_files_lock.acquire()
    shared_files[file_name] = file_buffer
    shared_files_lock.release()
    # split chunks among peers
    split_chunks = [[] for _ in range(len(available_peers))]
    for i in range(len(chunks)):
        split_chunks[i % len(available_peers)].append(chunks[i])
    # download each split chunk parallelly
    threads = []
    i = 0
    for chunk in split_chunks:
        thread = threading.Thread(target=download_sequentially, args=(file_name, available_peers[i], active_peers, chunk))
        threads.append(thread)
        thread.start()
        i += 1
    print("Still Downloading...")
    for thread in threads:
        thread.join()
    print("Download complete.")

    # byte array to binary string
    shared_files_lock.acquire()
    shared_files[file_name] = bytes(shared_files[file_name])
    shared_files_lock.release()

    # open directory peer_<port> and save file
    if not os.path.exists(f"peer_{MY_PORT}_downloads"):
        os.makedirs(f"peer_{MY_PORT}_downloads")
    with open(f"peer_{MY_PORT}_downloads/{file_name}", "wb") as f:
        f.write(shared_files[file_name])


    


if __name__ == "__main__":
    manager_thread = threading.Thread(target=start_peer)
    manager_thread.start()
    while True:
        print("Select an option")
        print("0: list all peers")
        print("1: list all seeding files")
        print("2: Add a file for seeding")
        print("3: Request a file in peer network")
        print("4: Exit program\n")
        try:
            option = int(input("Enter option: "))
            if option == 0:
                list_all_peers()
            if option == 1:
                list_all_files()
            if option == 2:
                add_file()
            if option == 3:
                request_file()
            if option == 4:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(MANAGER_ADDR)
                sock.send(f"LEAVE 127.0.0.1 {MY_PORT}".encode())
                sock.close()
                # exit all threads
                print("Program exited press ctrl+c to exit")
                break
        except ValueError:
            print("Please try again...")
        input("press ENTER to continue\n")
