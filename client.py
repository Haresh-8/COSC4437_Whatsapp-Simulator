import socket
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox
import random

# --- Configuration ---
HOST = '127.0.0.1'
PORT = 65432
SYNC_INTERVAL_MS = 15000 # Sync every 15 seconds

# --- Global Clock Variables for Client ---
LOCAL_CLOCK = time.time() 
# Simulate clock drift (e.g., 0.995 to 1.005)
TIME_DRIFT_FACTOR = 1.0 + (random.randint(-5, 5) / 1000.0) 
SYNCHRONIZED_TIME = LOCAL_CLOCK 
ALIAS = ""
CLIENT_SOCKET = None
CHAT_DISPLAY = None # Used to update the chat window from the listener thread

def adjust_local_clock():
    """Simulates a non-ideal local clock by applying a drift factor."""
    global LOCAL_CLOCK
    # Advance time based on the drift factor
    LOCAL_CLOCK += 1.0 * TIME_DRIFT_FACTOR

def get_synced_time():
    """Returns the most recently synchronized time."""
    return SYNCHRONIZED_TIME

def sync_clock(root, time_label):
    """
    Implements Cristian's Algorithm (Client Side).
    Runs non-blocking by using root.after() for scheduling.
    """
    global SYNCHRONIZED_TIME
    
    T1 = time.time()  # Client records time before sending request (T1)
    
    try:
        # 1. Send time request
        CLIENT_SOCKET.sendall("SYNC_TIME_REQUEST".encode('utf-8'))
        
        # 2. Receive server time (this is handled in the listener thread for non-blocking)
        # Note: For simple systems, the full sync logic can be implemented here *if* done in a separate thread.
        # Since we use the listener thread, the result is processed there.
        pass # The listener thread will receive the T_server response
        
    except Exception as e:
        print(f"[ERROR] during clock sync request: {e}")

    # Schedule the next sync
    root.after(SYNC_INTERVAL_MS, lambda: sync_clock(root, time_label)) 

def listen_for_messages(client_socket):
    """Dedicated thread for listening to server messages and time sync responses."""
    global SYNCHRONIZED_TIME
    
    while True:
        try:
            # Receive data. Blocking call, hence why it's in a separate thread.
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                break

            # Check if this is a server time response (Cristian's response)
            try:
                T_server = float(data.strip())
                T2 = time.time() # Client records time upon receiving response (T2)
                
                # Calculate RTT and Offset
                RTT = T2 - T1_SYNC_START.get() # Retrieve T1 from the start of the last request
                Offset = RTT / 2
                
                # New synchronized time
                SYNCHRONIZED_TIME = T_server + Offset
                
                # Update GUI label via root.after to run in the main thread
                # This ensures thread safety for Tkinter updates
                if CHAT_DISPLAY:
                    CHAT_DISPLAY.after(0, lambda: print(f"[CLIENT SYNC] T_server={time.strftime('%H:%M:%S', time.localtime(T_server))}, RTT={RTT*1000:.2f}ms. Adjusted clock."))
                
            except ValueError:
                # Not a float, so it's a regular chat message
                if CHAT_DISPLAY:
                    CHAT_DISPLAY.after(0, lambda: display_message(data))

        except Exception as e:
            # print(f"[ERROR] Listener thread failed: {e}")
            break

def display_message(message):
    """Safely updates the Tkinter chat window."""
    CHAT_DISPLAY.config(state='normal')
    CHAT_DISPLAY.insert(tk.END, message.strip() + '\n')
    CHAT_DISPLAY.config(state='disabled')
    CHAT_DISPLAY.see(tk.END) # Auto-scroll


# Helper class to store T1 (start time of sync request)
class TimeSyncState:
    def __init__(self):
        self._t1 = time.time()
    def set(self, t1):
        self._t1 = t1
    def get(self):
        return self._t1

T1_SYNC_START = TimeSyncState()


def start_client_gui():
    global ALIAS, CLIENT_SOCKET, CHAT_DISPLAY, T1_SYNC_START
    
    # 1. Alias Prompt
    root_temp = tk.Tk()
    root_temp.withdraw() 
    ALIAS = simpledialog.askstring("Alias Setup", "Enter your chat alias:", parent=root_temp)
    root_temp.destroy()

    if not ALIAS: return
    # 2. Socket Connection
    CLIENT_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        CLIENT_SOCKET.connect((HOST, PORT))
        CLIENT_SOCKET.settimeout(None) # Set back to blocking for the listener thread
    except ConnectionRefusedError:
        messagebox.showerror("Connection Error", "Could not connect to server. Ensure server is running.")
        return

    # 3. Tkinter Setup
    root = tk.Tk()
    root.title(f"Chat Client - Logged in as: {ALIAS}")
    
    # GUI Components (similar to previous version)
    clock_frame = tk.Frame(root); clock_frame.pack(fill=tk.X, padx=10, pady=5)
    local_time_label = tk.Label(clock_frame, text="Local Time: ---", font=('Arial', 10), anchor='w'); local_time_label.pack(fill=tk.X)
    synced_time_label = tk.Label(clock_frame, text="Server Time: ---", font=('Arial', 10, 'bold'), anchor='w', fg='blue'); synced_time_label.pack(fill=tk.X)
    
    CHAT_DISPLAY = scrolledtext.ScrolledText(root, width=60, height=20, state='disabled'); CHAT_DISPLAY.pack(padx=10, pady=5)
    
    input_frame = tk.Frame(root); input_frame.pack(fill=tk.X, padx=10, pady=5)
    message_entry = tk.Entry(input_frame, width=50); message_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # 4. Sending Function (Runs in Main/GUI Thread)
    def send_message(event=None):
        message = message_entry.get()
        if message:
            try:
                # Prepend alias for server/broadcast
                CLIENT_SOCKET.sendall(f"{ALIAS}: {message}".encode('utf-8')) 
                
                # Display own message immediately using synchronized time
                time_str = time.strftime('%H:%M:%S', time.localtime(get_synced_time()))
                formatted_msg = f"[{time_str}] <You ({ALIAS})>: {message}"
                display_message(formatted_msg)
                
                message_entry.delete(0, tk.END)
            except Exception as e:
                display_message(f"[ERROR] Could not send message: {e}")

    # 5. Clock Update Loop (Runs in Main/GUI Thread using root.after)
    def update_clocks():
        """Updates the time labels and schedules the next update."""
        
        # Simulate drift on local clock
        adjust_local_clock() 
        
        # Update Local Time Label
        local_time_str = time.strftime('%H:%M:%S', time.localtime(LOCAL_CLOCK))
        local_time_label.config(text=f"Local Time: {local_time_str} (Drift: {TIME_DRIFT_FACTOR:.4f})")

        # Update Synchronized Time Label (Note: SYNCHRONIZED_TIME is static until the next sync response)
        synced_time_str = time.strftime('%H:%M:%S', time.localtime(SYNCHRONIZED_TIME))
        synced_time_label.config(text=f"Server Time: {synced_time_str} (Synced)")
        
        root.after(1000, update_clocks)

    # 6. Bindings and Start
    message_entry.bind("<Return>", send_message)
    send_button = tk.Button(input_frame, text="Send", command=send_message); send_button.pack(side=tk.RIGHT, padx=5)

    # Start the listening thread
    listen_thread = threading.Thread(target=listen_for_messages, args=(CLIENT_SOCKET,), daemon=True)
    listen_thread.start()

    # Start the clock loops
    update_clocks()
    
    # Initiate the first clock sync and set up the recurring timer
    T1_SYNC_START.set(time.time()) # Record T1 before sending first request
    sync_clock(root, synced_time_label)

    # Handle graceful exit
    def on_closing():
        CLIENT_SOCKET.close()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing) 
    root.mainloop()

if __name__ == "__main__":
    start_client_gui()