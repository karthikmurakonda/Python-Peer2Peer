import socket
import threading
import time

# Define constants
PORT = 1234
BUFF_SIZE = 1024
CHECK_INTERVAL = 5

# Initialize the Manager
active_peers = []

# Define a function to broadcast the list of active peers
def broadcast_peers():
    global active_peers
    peer_list = ",".join([f"{peer[0]}:{peer[1]}" for peer in active_peers])
    for peer in active_peers:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(peer)
            sock.send(f"PEERS {peer_list}".encode())
            sock.close()
        except Exception as e:
            print(e)
            active_peers.remove(peer)
            print(f"Peer {peer} removed from active peers list.")

# Define a function to handle incoming connections from peers
def handle_peer(sock, addr):
    global active_peers
    # Receive peer information
    data = sock.recv(BUFF_SIZE)
    peer_info = data.decode().split()
    if peer_info[0] == "CONNECT":
        print(f"New peer {(peer_info[1], int(peer_info[2]))} connected.")
        active_peers.append((peer_info[1], int(peer_info[2])))
        peer_list = ",".join([f"{peer[0]}:{peer[1]}" for peer in active_peers])
        sock.send(f"{peer_list}".encode())
    elif peer_info[0] == "LEAVE":
        print(f"Peer {(peer_info[1], int(peer_info[2]))} disconnected.")
        active_peers.remove((peer_info[1], int(peer_info[2])))
    sock.close()
    # Close connection
    time.sleep(1)
    broadcast_peers()

# Define a function to periodically check the availability of active peers
def check_peers():
    global active_peers
    while True:
        for peer in active_peers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                # print(f"Checking peer {peer}")
                sock.connect((peer[0], peer[1]))
                sock.send(b"PING")
                sock.close()
            except:
                active_peers.remove(peer)
                print(f"Peer {peer} removed from active peers list.")
        broadcast_peers()
        time.sleep(CHECK_INTERVAL)

# Set up the socket to listen for incoming connections
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.bind(('localhost', PORT))
server_sock.listen()

# Start the thread to periodically check the availability of active peers
check_thread = threading.Thread(target=check_peers)
check_thread.start()

# Handle incoming connections from peers
while True:
    sock, addr = server_sock.accept()
    peer_thread = threading.Thread(target=handle_peer, args=(sock, addr))
    peer_thread.start()
