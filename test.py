import socket
import sys
import threading
import time
import struct
import random

class NATDetector:
    def __init__(self):
        self.stun_servers = [
            ("stun.1cbit.ru", 3478),
            ("stun.finsterwalder.com", 3478),
            ("stun.siplogin.de", 3478),
            ("stun.romancecompass.com", 3478)
        ]

    def create_stun_request(self):
        """Create STUN binding request"""
        message_type = 0x0001
        message_length = 0x0000
        magic_cookie = 0x2112A442
        transaction_id = bytes([random.randint(0, 255) for _ in range(12)])

        return struct.pack('!HH', message_type, message_length) + \
               struct.pack('!I', magic_cookie) + transaction_id

    def parse_stun_response(self, response):
        """Parse STUN response for mapped address"""
        if len(response) < 20:
            return None, None

        offset = 20
        while offset < len(response):
            if offset + 4 > len(response):
                break

            attr_type = struct.unpack('!H', response[offset:offset+2])[0]
            attr_length = struct.unpack('!H', response[offset+2:offset+4])[0]

            if attr_type == 0x0001 and attr_length >= 8:  # MAPPED-ADDRESS
                if offset + 12 <= len(response):
                    family = struct.unpack('!H', response[offset+5:offset+7])[0]
                    if family == 0x01:  # IPv4
                        port = struct.unpack('!H', response[offset+6:offset+8])[0]
                        ip_bytes = response[offset+8:offset+12]
                        ip = '.'.join(str(b) for b in ip_bytes)
                        return ip, port

            offset += 4 + attr_length

        return None, None

    def get_mapped_address(self, local_port, stun_server):
        """Get external address from STUN server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('', local_port))
            sock.settimeout(3)

            request = self.create_stun_request()
            sock.sendto(request, stun_server)

            response, addr = sock.recvfrom(1024)
            ip, port = self.parse_stun_response(response)

            sock.close()
            return ip, port
        except Exception as e:
            return None, None

    def detect_nat_type(self):
        """Detect NAT type using multiple STUN servers"""
        print("Detecting NAT type...")

        base_port = random.randint(10000, 50000)
        results = []

        for i, server in enumerate(self.stun_servers[:3]):
            local_port = base_port + i
            print(f"Testing with {server[0]}:{server[1]} on local port {local_port}")

            ip, port = self.get_mapped_address(local_port, server)
            if ip and port:
                results.append((ip, port, local_port))
                print(f"  Mapped to: {ip}:{port}")
            else:
                print(f"  Failed to get mapping")

        if len(results) < 2:
            return "UNKNOWN - Not enough STUN responses"

        # Analyze results
        external_ips = set(r[0] for r in results)
        external_ports = [r[1] for r in results]
        local_ports = [r[2] for r in results]

        if len(external_ips) > 1:
            return "SYMMETRIC NAT - Different external IPs (Very hard to punch)"

        # Check port allocation pattern
        port_diffs = []
        for i in range(1, len(external_ports)):
            port_diff = external_ports[i] - external_ports[i-1]
            local_diff = local_ports[i] - local_ports[i-1]
            port_diffs.append(port_diff - local_diff)

        if all(diff == 0 for diff in port_diffs):
            return "FULL CONE NAT - Easy to punch"
        elif len(set(external_ports)) == len(external_ports):
            if all(diff > 0 for diff in port_diffs):
                return "PORT RESTRICTED NAT - Moderate difficulty"
            else:
                return "SYMMETRIC NAT - Different ports (Hard to punch)"
        else:
            return "ADDRESS RESTRICTED NAT - Moderate difficulty"

def tcp_listen(port, peer_ip, peer_port, stop_event):
    """TCP listener that accepts connections"""
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('0.0.0.0', port))
        server.listen(1)
        server.settimeout(1)  # Non-blocking accept

        print(f"TCP listener started on port {port}")

        while not stop_event.is_set():
            try:
                conn, addr = server.accept()
                print(f"TCP connection established with {addr}")

                # Handle the connection
                threading.Thread(target=handle_tcp_connection, args=(conn, addr), daemon=True).start()
                break

            except socket.timeout:
                continue
            except Exception as e:
                if not stop_event.is_set():
                    print(f"TCP listen error: {e}")
                break

        server.close()

    except Exception as e:
        print(f"TCP listener setup error: {e}")

def handle_tcp_connection(conn, addr):
    """Handle established TCP connection"""
    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            message = data.decode().strip()
            if message and message != "TCP_PUNCH":
                print(f"[TCP RECV from {addr}] {message}")
    except Exception as e:
        print(f"TCP connection error: {e}")
    finally:
        conn.close()

def tcp_punch(peer_ip, peer_port, local_port, stop_event):
    """Aggressive TCP hole punching"""
    print(f"Starting TCP hole punching to {peer_ip}:{peer_port}")

    while not stop_event.is_set():
        try:
            # Create socket and bind to specific local port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', local_port))
            sock.settimeout(1)

            # Try to connect (this creates the hole)
            result = sock.connect_ex((peer_ip, peer_port))

            if result == 0:
                print(f"TCP connection established to {peer_ip}:{peer_port}!")
                # Connection successful, start chat
                threading.Thread(target=handle_tcp_connection, args=(sock, (peer_ip, peer_port)), daemon=True).start()

                # Send messages
                while not stop_event.is_set():
                    msg = input("You: ")
                    if msg.lower() == 'quit':
                        stop_event.set()
                        break
                    sock.send(msg.encode())

                sock.close()
                return

            sock.close()
            time.sleep(0.1)  # Quick retry

        except Exception as e:
            time.sleep(0.1)

    print("TCP hole punching stopped")

def main():
    if len(sys.argv) != 4:
        print(f"Usage: python {sys.argv[0]} <local_port> <peer_ip> <peer_port>")
        print("Example: python script.py 8000 203.0.113.10 8001")
        sys.exit(1)

    local_port = int(sys.argv[1])
    peer_ip = sys.argv[2]
    peer_port = int(sys.argv[3])

    # First, detect NAT type
    detector = NATDetector()
    nat_type = detector.detect_nat_type()
    print(f"\nNAT Type: {nat_type}\n")

    if "SYMMETRIC" in nat_type:
        print("WARNING: Symmetric NAT detected. TCP hole punching is very unlikely to work.")
        print("Consider using a relay server or VPN instead.")
        choice = input("Continue anyway? (y/n): ")
        if choice.lower() != 'y':
            return

    # Get external address
    print("Getting external address...")
    detector_instance = NATDetector()
    external_ip, external_port = detector_instance.get_mapped_address(local_port, detector_instance.stun_servers[0])

    if external_ip:
        print(f"Your external address: {external_ip}:{external_port}")
        print(f"Share this with your peer: {external_ip} {external_port}")
    else:
        print("Could not determine external address")

    print(f"\nLocal port: {local_port}")
    print(f"Target: {peer_ip}:{peer_port}")

    # Create stop event
    stop_event = threading.Event()

    # Start TCP listener
    listen_thread = threading.Thread(target=tcp_listen, args=(local_port, peer_ip, peer_port, stop_event), daemon=True)
    listen_thread.start()

    # Wait a moment for listener to start
    time.sleep(1)

    input("Press Enter when both peers are ready...")

    # Start TCP hole punching
    punch_thread = threading.Thread(target=tcp_punch, args=(peer_ip, peer_port, local_port, stop_event), daemon=True)
    punch_thread.start()

    try:
        # Wait for connection or user interrupt
        punch_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_event.set()

if __name__ == "__main__":
    main()
