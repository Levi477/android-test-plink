#!/usr/bin/env python3
"""
Python WebRTC CLI P2P Chat
Requirements: pip install aiortc pyperclip

WARNING: Python WebRTC is less mature than browser WebRTC
May not work as reliably as the HTML version
"""

import asyncio
import json
import sys
import logging
from typing import Optional
import signal

try:
    from aiortc import RTCPeerConnection, RTCDataChannel, RTCSessionDescription
    from aiortc.contrib.media import MediaBlackhole
    import pyperclip
except ImportError:
    print("Missing dependencies. Install with:")
    print("pip install aiortc pyperclip")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.WARNING)  # Reduce aiortc noise

class WebRTCChat:
    def __init__(self):
        self.pc = RTCPeerConnection(configuration={
            "iceServers": [
                {"urls": "stun:stun.l.google.com:19302"},
                {"urls": "stun:stun1.l.google.com:19302"},
                {"urls": "stun:stun2.l.google.com:19302"},
                {"urls": "stun:stun.stunprotocol.org:3478"}
            ]
        })
        
        self.data_channel: Optional[RTCDataChannel] = None
        self.connected = False
        self.is_offerer = False
        
        # Setup peer connection handlers
        self.setup_peer_connection()
    
    def setup_peer_connection(self):
        """Setup WebRTC peer connection event handlers"""
        
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            print(f"📡 Data channel '{channel.label}' received")
            self.setup_data_channel(channel)
        
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            state = self.pc.connectionState
            print(f"🔗 Connection state: {state}")
            
            if state == "connected":
                self.connected = True
                print("✅ Connected! You can now send messages.")
            elif state in ["failed", "closed", "disconnected"]:
                self.connected = False
                print("❌ Connection lost")
    
    def setup_data_channel(self, channel: RTCDataChannel):
        """Setup data channel event handlers"""
        self.data_channel = channel
        
        @channel.on("open")
        def on_open():
            print("📞 Data channel opened")
            self.connected = True
        
        @channel.on("message")
        def on_message(message):
            if isinstance(message, str):
                print(f"📩 Received: {message}")
            else:
                print(f"📩 Received binary message ({len(message)} bytes)")
        
        @channel.on("close")
        def on_close():
            print("📞 Data channel closed")
            self.connected = False
    
    async def create_offer(self):
        """Create WebRTC offer (Device A)"""
        try:
            print("🚀 Creating offer...")
            self.is_offerer = True
            
            # Create data channel
            self.data_channel = self.pc.createDataChannel("chat")
            self.setup_data_channel(self.data_channel)
            
            # Create offer
            offer = await self.pc.createOffer()
            await self.pc.setLocalDescription(offer)
            
            # Wait for ICE gathering
            print("🧊 Gathering ICE candidates...")
            await self.wait_for_ice_gathering()
            
            offer_data = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp
            }
            
            offer_json = json.dumps(offer_data, indent=2)
            print("\n" + "="*50)
            print("📋 YOUR OFFER CODE (send to other device):")
            print("="*50)
            print(offer_json)
            print("="*50)
            
            # Try to copy to clipboard
            try:
                pyperclip.copy(offer_json)
                print("✅ Offer copied to clipboard!")
            except:
                print("⚠️  Could not copy to clipboard")
            
            return offer_data
            
        except Exception as e:
            print(f"❌ Error creating offer: {e}")
            return None
    
    async def accept_offer(self, offer_text: str):
        """Accept offer and create answer (Device B)"""
        try:
            print("📨 Processing offer...")
            
            # Parse offer
            try:
                offer_data = json.loads(offer_text.strip())
            except json.JSONDecodeError:
                print("❌ Invalid JSON format")
                return None
            
            if "type" not in offer_data or "sdp" not in offer_data:
                print("❌ Invalid offer format - missing type or sdp")
                return None
            
            # Set remote description
            offer_desc = RTCSessionDescription(
                sdp=offer_data["sdp"], 
                type=offer_data["type"]
            )
            await self.pc.setRemoteDescription(offer_desc)
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            # Wait for ICE gathering
            print("🧊 Gathering ICE candidates...")
            await self.wait_for_ice_gathering()
            
            answer_data = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp
            }
            
            answer_json = json.dumps(answer_data, indent=2)
            print("\n" + "="*50)
            print("📋 YOUR ANSWER CODE (send back to other device):")
            print("="*50)
            print(answer_json)
            print("="*50)
            
            # Try to copy to clipboard
            try:
                pyperclip.copy(answer_json)
                print("✅ Answer copied to clipboard!")
            except:
                print("⚠️  Could not copy to clipboard")
            
            return answer_data
            
        except Exception as e:
            print(f"❌ Error accepting offer: {e}")
            return None
    
    async def accept_answer(self, answer_text: str):
        """Accept answer and complete connection (Device A)"""
        try:
            print("📨 Processing answer...")
            
            # Parse answer
            try:
                answer_data = json.loads(answer_text.strip())
            except json.JSONDecodeError:
                print("❌ Invalid JSON format")
                return False
            
            if "type" not in answer_data or "sdp" not in answer_data:
                print("❌ Invalid answer format - missing type or sdp")
                return False
            
            # Set remote description
            answer_desc = RTCSessionDescription(
                sdp=answer_data["sdp"],
                type=answer_data["type"]
            )
            await self.pc.setRemoteDescription(answer_desc)
            
            print("✅ Answer processed. Waiting for connection...")
            return True
            
        except Exception as e:
            print(f"❌ Error accepting answer: {e}")
            return False
    
    async def wait_for_ice_gathering(self):
        """Wait for ICE gathering to complete"""
        if self.pc.iceGatheringState == "complete":
            return
        
        # Wait for ICE gathering with timeout
        for _ in range(50):  # 5 second timeout
            await asyncio.sleep(0.1)
            if self.pc.iceGatheringState == "complete":
                return
        
        print("⚠️  ICE gathering timeout (continuing anyway)")
    
    def send_message(self, message: str):
        """Send message through data channel"""
        if not self.data_channel or self.data_channel.readyState != "open":
            print("❌ Not connected")
            return False
        
        try:
            self.data_channel.send(message)
            print(f"📤 Sent: {message}")
            return True
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return False
    
    async def close(self):
        """Close connection"""
        if self.data_channel:
            self.data_channel.close()
        await self.pc.close()

async def main():
    print("🚀 WebRTC P2P Chat (Python CLI)")
    print("=" * 40)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Usage:")
        print("  python webrtc_chat.py          # Interactive mode")
        print("  python webrtc_chat.py --help   # Show this help")
        return
    
    chat = WebRTCChat()
    
    try:
        # Connection setup phase
        print("\n📋 CONNECTION SETUP")
        print("1. Create offer (Device A)")
        print("2. Accept offer (Device B)")
        
        while True:
            choice = input("\nChoose (1/2): ").strip()
            
            if choice == "1":
                # Device A - Create offer
                await chat.create_offer()
                
                print("\n📥 Waiting for answer...")
                print("Paste the answer you received:")
                answer_text = ""
                print("(Type 'END' on a new line when done)")
                
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    answer_text += line + "\n"
                
                if await chat.accept_answer(answer_text):
                    print("✅ Connection setup complete!")
                    break
                else:
                    print("❌ Failed to process answer")
                    continue
                    
            elif choice == "2":
                # Device B - Accept offer
                print("\n📥 Paste the offer you received:")
                print("(Type 'END' on a new line when done)")
                
                offer_text = ""
                while True:
                    line = input()
                    if line.strip() == "END":
                        break
                    offer_text += line + "\n"
                
                if await chat.accept_offer(offer_text):
                    print("✅ Answer created and displayed above!")
                    print("⏳ Waiting for connection...")
                    break
                else:
                    print("❌ Failed to process offer")
                    continue
            else:
                print("Invalid choice. Enter 1 or 2.")
        
        # Wait for connection
        print("\n⏳ Waiting for WebRTC connection...")
        for i in range(100):  # 10 second timeout
            await asyncio.sleep(0.1)
            if chat.connected:
                break
        
        if not chat.connected:
            print("❌ Connection timeout. Check network connectivity.")
            return
        
        # Chat phase
        print("\n💬 CHAT MODE")
        print("Type messages (or 'quit' to exit):")
        
        while True:
            try:
                message = input("You: ")
                
                if message.lower() in ['quit', 'exit', 'q']:
                    break
                
                if message.strip():
                    chat.send_message(message)
                    
            except (KeyboardInterrupt, EOFError):
                break
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    finally:
        print("\n🔚 Closing connection...")
        await chat.close()

def handle_signal(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🔚 Shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, handle_signal)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🔚 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
