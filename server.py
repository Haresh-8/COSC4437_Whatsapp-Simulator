import socket
import threading
import time

# --- Configuration ---
HOST = '127.0.0.1'
PORT = 65432
# Stores (socket, address) tuples
CLIENTS = [] 
CLIENT_LOCK = threading.Lock()

def get_server_time():
    """Returns the current server clock time."""
    return time.time()

def broadcast(message, sender_socket=None):
    """Sends a message to all connected clients."""
    encoded_message = message.encode('utf-8')
    disconnected_clients = []

    with CLIENT_LOCK:
        for client_socket, address in CLIENTS:
            if client_socket != sender_socket:
                try:
                    client_socket.sendall(encoded_message)
                except Exception:
                    disconnected_clients.append((client_socket, address))
        
        # Remove disconnected clients after the loop
        for client in disconnected_clients:
            CLIENTS.remove(client)
            print(f"[SERVER] Removed disconnected client: {client[1]}")

def handle_client(client_socket, client_address):
    """Handles communication and logic for a single client."""
    print(f"[SERVER] New connection: {client_address}")
    
    with CLIENT_LOCK:
        CLIENTS.append((client_socket, client_address))
    
    try:
        while True:
            # Set a timeout so recv is not infinitely blocking
            client_socket.settimeout(0.5) 
            try:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break # Client gracefully closed the connection
            except socket.timeout:
                continue # No data received, continue loop
            except Exception:
                break # Connection likely broken

            # --- Clock Synchronization (Cristian's Algorithm Server Part) ---
            if data.strip().upper() == "SYNC_TIME_REQUEST":
                server_time_str = str(get_server_time())
                client_socket.sendall(server_time_str.encode('utf-8'))
                # print(f"[SYNC] Time request from {client_address[1]}. Sent: {time.strftime('%H:%M:%S', time.localtime(float(server_time_str)))}")
            
            # --- Chat Message Broadcast ---
            else:
                # Expecting format "Alias: Message content"
                print(f"[CHAT] Received from {client_address[1]}: {data.strip()}")
                broadcast(data + '\n', client_socket) # Broadcast the raw message and alias
                
    except Exception as e:
        print(f"[ERROR] during client handling {client_address}: {e}")
    finally:
        # Clean up client connection
        with CLIENT_LOCK:
            if (client_socket, client_address) in CLIENTS:
                CLIENTS.remove((client_socket, client_address))
        client_socket.close()
        print(f"[SERVER] Connection closed: {client_address}. Active clients: {len(CLIENTS)}")

def start_server():
    """Initializes and runs the server."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
    server.bind((HOST, PORT))
    server.listen(5)
    
    print(f"==========================================")
    print(f"| SERVER RUNNING on {HOST}:{PORT} |")
    print(f"| Press Ctrl+C to stop. |")
    print(f"==========================================")
    
    try:
        while True:
            client_socket, client_address = server.accept()
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
            client_thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Server shutting down...")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()