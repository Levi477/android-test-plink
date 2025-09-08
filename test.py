import socket
import sys
import threading
import time
import struct

def get_stun_mapped_address(stun_server="stun.l.google.com", stun_port=19302):
    """Get external IP and port using STUN server"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(5)

    # STUN Binding Request
    message_type = 0x0001
    message_length = 0x0000
    magic_cookie = 0x2112A442
    transaction_id = b'\x00' * 12

    stun_request = struct.pack('!HH', message_type, message_length) + \
                   struct.pack('!I', magic_cookie) + transaction_id

    try:
        sock.sendto(stun_request, (stun_server, stun_port))
        response, addr = sock.recvfrom(1024)

        # Parse STUN response for mapped address
        if len(response) >= 20:
            # Look for MAPPED-ADDRESS attribute (type 0x0001)
            offset = 20
            while offset < len(response):
                attr_type = struct.unpack('!H', response[offset:offset+2])[0]
                attr_length = struct.unpack('!H', response[offset+2:offset+4])[0]

                if attr_type == 0x0001:  # MAPPED-ADDRESS
                    family = struct.unpack('!H', response[offset+5:offset+7])[0]
                    if family == 0x01:  # IPv4
                        port = struct.unpack('!H', response[offset+6:offset+8])[0]
                        ip_bytes = response[offset+8:offset+12]
                        ip = '.'.join(str(b) for b in ip_bytes)
                        sock.close()
                        return ip, port

                offset += 4 + attr_length

        sock.close()
        return None, None

    except Exception as e:
        print(f"STUN error: {e}")
        sock.close()
        return None, None

def listen(sock):
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = data.decode()
            if message != "HOLE_PUNCH":
                print(f"[RECV from {addr}] {message}")
        except Exception as e:
            print("Recv error:", e)
            break

def aggressive_punch(sock, peer_ip, peer_port, my_external_port, stop_event):
    """More aggressive hole punching with multiple strategies"""
    print("Starting aggressive hole punching...")

    # Try multiple ports around the expected port
    port_range = range(max(1024, peer_port - 10), peer_port + 10)

    while not stop_event.is_set():
        try:
            # Standard punch to known port
            sock.sendto(b"HOLE_PUNCH", (peer_ip, peer_port))

            # Try nearby ports (for NAT port prediction)
            for port in port_range:
                if port != peer_port:
                    try:
                        sock.sendto(b"HOLE_PUNCH", (peer_ip, port))
                    except:
                        pass

            time.sleep(0.5)  # More frequent punching
        except Exception as e:
            print("Punch error:", e)
            break

    print("Hole punching stopped.")

def main(my_port, peer_ip, peer_port):
    # Get our external address using STUN
    print("Getting external address via STUN...")
    my_external_ip, my_external_port = get_stun_mapped_address()

    if my_external_ip:
        print(f"My external address: {my_external_ip}:{my_external_port}")
        print(f"Share this with your peer: {my_external_ip} {my_external_port}")
    else:
        print("Failed to get external address via STUN")

    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", my_port))

    # Start listening
    threading.Thread(target=listen, args=(sock,), daemon=True).start()

    # Wait for user to confirm peer is ready
    input("Press Enter when peer is ready and you've exchanged external addresses...")

    # Start aggressive hole punching
    stop_punch = threading.Event()
    punch_thread = threading.Thread(target=aggressive_punch,
                                  args=(sock, peer_ip, peer_port, my_external_port, stop_punch),
                                  daemon=True)
    punch_thread.start()

    print(f"Local socket: 0.0.0.0:{my_port}")
    print(f"Target peer: {peer_ip}:{peer_port}")
    print("Aggressive hole punching for 20 seconds...")

    # Longer hole punching time
    time.sleep(20)
    stop_punch.set()

    print("Starting message exchange. Type 'quit' to exit.")

    # Message exchange
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
