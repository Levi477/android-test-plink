import asyncio
import json
import sys
import signal
from typing import Optional

import clipman
from aiortc import (
    RTCPeerConnection,
    RTCDataChannel,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer
)


def get_clipboard_content() -> str:
    try:
        return clipman.get().strip()
    except Exception as e:
        print(f"Failed to read clipboard: {e}")
        return ""


def set_clipboard_content(content: str) -> bool:
    try:
        clipman.set(content)
        return True
    except Exception as e:
        print(f"Failed to copy to clipboard: {e}")
        return False


class SimpleWebRTCChat:
    def __init__(self):
        self.pc = RTCPeerConnection(configuration=RTCConfiguration(
            iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
        ))
        self.data_channel: Optional[RTCDataChannel] = None
        self.connected = False
        self.setup_handlers()

    def setup_handlers(self):
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            print("Data channel received")
            self.data_channel = channel
            self.setup_channel_handlers(channel)

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            print(f"Connection state changed to: {self.pc.connectionState}")
            if self.pc.connectionState == "connected":
                self.connected = True
            elif self.pc.connectionState in ["failed", "closed", "disconnected"]:
                self.connected = False

    def setup_channel_handlers(self, channel):
        @channel.on("open")
        def on_open():
            print("Data channel opened - ready to chat!")
            self.connected = True

        @channel.on("message")
        def on_message(message):
            print(f"Peer: {message}")

        @channel.on("close")
        def on_close():
            print("Data channel closed")
            self.connected = False

    async def create_offer(self):
        print("Creating offer...")
        self.data_channel = self.pc.createDataChannel("chat")
        self.setup_channel_handlers(self.data_channel)

        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.wait_ice_complete()

        offer_data = {
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp
        }
        return json.dumps(offer_data, indent=2)

    async def handle_offer(self, offer_text: str):
        print("Processing offer...")
        try:
            offer_data = json.loads(offer_text)
            offer_desc = RTCSessionDescription(offer_data["sdp"], offer_data["type"])
            await self.pc.setRemoteDescription(offer_desc)

            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            await self.wait_ice_complete()

            answer_data = {
                "type": self.pc.localDescription.type,
                "sdp": self.pc.localDescription.sdp
            }
            return json.dumps(answer_data, indent=2)
        except Exception as e:
            print(f"Error handling offer: {e}")
            return None

    async def handle_answer(self, answer_text: str):
        print("Processing answer...")
        try:
            answer_data = json.loads(answer_text)
            answer_desc = RTCSessionDescription(answer_data["sdp"], answer_data["type"])
            await self.pc.setRemoteDescription(answer_desc)
            print("Answer processed successfully")
            return True
        except Exception as e:
            print(f"Error handling answer: {e}")
            return False

    async def wait_ice_complete(self):
        print("Waiting for ICE gathering to complete...")
        while self.pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)
        print("ICE gathering complete")

    def send_message(self, message: str):
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(message)
        else:
            print("Not connected - message not sent")

    async def wait_for_connection(self, timeout_seconds=60):
        print(f"Waiting for connection (timeout: {timeout_seconds}s)...")
        for i in range(timeout_seconds * 10):
            if self.connected:
                return True
            await asyncio.sleep(0.1)
            if i % 50 == 0:  # Print every 5 seconds
                print(f"Still waiting... ({i//10}s)")
        return False

    async def close(self):
        if self.data_channel:
            self.data_channel.close()
        await self.pc.close()


async def main():
    print("Simple WebRTC P2P Chat")
    print("=" * 40)

    # Initialize clipman
    try:
        clipman.init()
        print("Clipboard initialized successfully")
    except Exception as e:
        print(f"Failed to initialize clipboard: {e}")
        return

    chat = SimpleWebRTCChat()

    choice = input("\nChoose mode:\n1. Create Offer (initiator)\n2. Accept Offer (responder)\n> ").strip()

    if choice == "1":
        # INITIATOR FLOW
        print("\n" + "=" * 40)
        print("INITIATOR MODE")
        print("=" * 40)

        # Step 1: Create and copy offer
        offer = await chat.create_offer()
        print("\nOffer created successfully!")
        print("\nOffer (copying to clipboard):")
        print("-" * 40)
        print(offer)
        print("-" * 40)

        if set_clipboard_content(offer):
            print("✓ Offer copied to clipboard")
        else:
            print("✗ Failed to copy offer to clipboard")
            return

        # Step 2: Wait for user to share offer and get answer
        print("\nNext steps:")
        print("1. Share this offer with the other person")
        print("2. Wait for them to send you back an answer")
        print("3. Copy their answer to clipboard")
        print("4. Press Enter here to continue")

        input("\nPress Enter when you have the answer in clipboard...")

        # Step 3: Get and process answer
        print("\nReading answer from clipboard...")
        answer_content = get_clipboard_content()
        if not answer_content:
            print("✗ Clipboard is empty")
            return

        # Validate it looks like JSON
        try:
            answer_data = json.loads(answer_content)
            if answer_data.get("type") != "answer":
                print("✗ Clipboard doesn't contain a valid answer")
                return
        except json.JSONDecodeError:
            print("✗ Clipboard doesn't contain valid JSON")
            return

        # Process the answer
        success = await chat.handle_answer(answer_content)
        if not success:
            print("✗ Failed to process answer")
            return

        print("✓ Answer processed successfully")

    elif choice == "2":
        # RESPONDER FLOW
        print("\n" + "=" * 40)
        print("RESPONDER MODE")
        print("=" * 40)

        # Step 1: Get offer from clipboard
        print("Reading offer from clipboard...")
        offer_content = get_clipboard_content()
        if not offer_content:
            print("✗ Clipboard is empty")
            return

        # Validate it looks like an offer
        try:
            offer_data = json.loads(offer_content)
            if offer_data.get("type") != "offer":
                print("✗ Clipboard doesn't contain a valid offer")
                return
        except json.JSONDecodeError:
            print("✗ Clipboard doesn't contain valid JSON")
            return

        # Step 2: Process offer and create answer
        answer = await chat.handle_offer(offer_content)
        if not answer:
            print("✗ Failed to create answer")
            return

        # Step 3: Copy answer to clipboard
        print("\nAnswer created successfully!")
        print("\nAnswer (copying to clipboard):")
        print("-" * 40)
        print(answer)
        print("-" * 40)

        if set_clipboard_content(answer):
            print("✓ Answer copied to clipboard")
            print("\nSend this answer back to the initiator")
        else:
            print("✗ Failed to copy answer to clipboard")
            return

    else:
        print("Invalid choice")
        return

    # Wait for connection
    print("\n" + "=" * 40)
    print("CONNECTING...")
    print("=" * 40)

    connected = await chat.wait_for_connection(60)
    if not connected:
        print("✗ Connection failed or timed out")
        return

    print("✓ Connected successfully!")

    # Chat loop
    print("\n" + "=" * 40)
    print("CHAT READY")
    print("=" * 40)
    print("Type your messages below (type 'exit' or 'quit' to leave)")
    print()

    try:
        while True:
            msg = input("You: ")
            if msg.lower() in ["exit", "quit"]:
                break
            if msg.strip():
                chat.send_message(msg)
    except KeyboardInterrupt:
        print("\nExiting...")

    await chat.close()
    print("Connection closed")


def handle_signal(signum, frame):
    print("\nExiting...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
