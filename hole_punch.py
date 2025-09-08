import socket
import sys
import threading
import time

def listen(sock):
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode()
            # Filter out hole punch packets from display
            if message != "HOLE_PUNCH":
                print(f"[RECV from {addr}] {message}")
        except Exception as e:
            print("Recv error:", e)
            break

def punch(sock, peer_ip, peer_port, stop_event):
    """Keep sending punch packets until hole is established"""
    print("Starting hole punching...")
    while not stop_event.is_set():
        try:
            sock.sendto(b"HOLE_PUNCH", (peer_ip, peer_port))
            time.sleep(1)  # send every 1 second
        except Exception as e:
            print("Punch error:", e)
            break
    print("Hole punching stopped.")

def main(my_port, peer_ip, peer_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", my_port))

    # Start listening
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    # Create stop event for hole punching
    stop_punch = threading.Event()

    # Start hole punching
    punch_thread = threading.Thread(target=punch, args=(sock, peer_ip, peer_port, stop_punch), daemon=True)
    punch_thread.start()

    print(f"My UDP socket bound to 0.0.0.0:{my_port}")
    print(f"Target peer: {peer_ip}:{peer_port}")
    print("Hole punching for 10 seconds...")

    # Give hole punching some time to establish connection
    time.sleep(10)
    stop_punch.set()

    print("Starting message exchange. Type 'quit' to exit.")

    # Send actual messages
    while True:
        msg = input("You: ")
        if msg.lower() == 'quit':
            break
        sock.sendto(msg.encode(), (peer_ip, peer_port))

    sock.close()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <my_port> <peer_ip> <peer_port>")
        sys.exit(1)

    my_port = int(sys.argv[1])
    peer_ip = sys.argv[2]
    peer_port = int(sys.argv[3])

    main(my_port, peer_ip, peer_port)
