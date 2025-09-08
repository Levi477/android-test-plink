import socket
import sys
import threading
import time

def listen(sock):
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            print(f"[RECV from {addr}] {data.decode()}")
        except Exception as e:
            print("Recv error:", e)
            break

def punch(sock, peer_ip, peer_port):
    """Keep sending punch packets periodically"""
    while True:
        try:
            sock.sendto(b"HOLE_PUNCH", (peer_ip, peer_port))
        except Exception as e:
            print("Punch error:", e)
            break
        time.sleep(2)  # send every 2 seconds

def main(my_port, peer_ip, peer_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", my_port))

    # Start listening
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    # Start punching loop
    threading.Thread(target=punch, args=(sock, peer_ip, peer_port), daemon=True).start()

    print(f"My UDP socket bound to 0.0.0.0:{my_port}")
    print(f"Target peer: {peer_ip}:{peer_port}")

    # Send actual messages
    while True:
        msg = input("You: ")
        sock.sendto(msg.encode(), (peer_ip, peer_port))

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <my_port> <peer_ip> <peer_port>")
        sys.exit(1)

    my_port = int(sys.argv[1])
    peer_ip = sys.argv[2]
    peer_port = int(sys.argv[3])

    main(my_port, peer_ip, peer_port)

