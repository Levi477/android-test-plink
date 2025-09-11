import asyncio
import json
import sys
import signal
from typing import Optional

import pyperclip
from aiortc import (
    RTCPeerConnection,
    RTCDataChannel,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer
)


def get_clipboard_content() -> str:
    try:
        return pyperclip.paste()
    except Exception as e:
        print(f"Failed to read clipboard: {e}")
        return ""


class SimpleWebRTCChat:
    def __init__(self):
        self.pc = RTCPeerConnection(configuration=RTCConfiguration(
            iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
        ))
        self.data_channel: Optional[RTCDataChannel] = None
        self.connected = False
        self.is_offerer = False
        self.setup_handlers()

    def setup_handlers(self):
        @self.pc.on("datachannel")
        def on_datachannel(channel):
            self.data_channel = channel

            @channel.on("open")
            def on_open():
                self.connected = True
                print("Data channel opened.")

            @channel.on("message")
            def on_message(message):
                print(f"Peer: {message}")

            @channel.on("close")
            def on_close():
                self.connected = False
                print("Data channel closed.")

        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            if self.pc.connectionState == "connected":
                self.connected = True
            elif self.pc.connectionState in ["failed", "closed", "disconnected"]:
                self.connected = False

    async def create_offer(self):
        self.is_offerer = True
        self.data_channel = self.pc.createDataChannel("chat")

        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        await self.wait_ice_complete()

        offer_data = {
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp
        }
        return json.dumps(offer_data, indent=2)

    async def accept_offer(self, offer_text: str):
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

    async def accept_answer(self, answer_text: str):
        answer_data = json.loads(answer_text)
        answer_desc = RTCSessionDescription(answer_data["sdp"], answer_data["type"])
        await self.pc.setRemoteDescription(answer_desc)

    async def wait_ice_complete(self):
        while self.pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)

    def send_message(self, message: str):
        if self.data_channel and self.data_channel.readyState == "open":
            self.data_channel.send(message)
        else:
            print("Not connected.")

    async def close(self):
        if self.data_channel:
            self.data_channel.close()
        await self.pc.close()


async def main():
    print("Simple WebRTC P2P Chat")

    chat = SimpleWebRTCChat()

    choice = input("Choose mode:\n1. Create Offer\n2. Accept Offer (from clipboard)\n> ").strip()

    if choice == "1":
        offer = await chat.create_offer()
        print("\nOffer generated (copy this to clipboard and send to peer):\n")
        print(offer)
        pyperclip.copy(offer)
        print("\nOffer has been copied to clipboard.")

    elif choice == "2":
        print("\nReading offer from clipboard...")

        clipboard_content = get_clipboard_content()
        if not clipboard_content:
            print("Clipboard is empty or unreadable.")
            return

        try:
            offer_data = json.loads(clipboard_content)
            if not isinstance(offer_data, dict) or "sdp" not in offer_data:
                print("Clipboard does not contain a valid offer JSON object.")
                return
        except json.JSONDecodeError:
            print("Clipboard does not contain valid JSON.")
            return

        answer = await chat.accept_offer(clipboard_content)
        print("\nAnswer generated (copied to clipboard, send this back to peer):\n")
        print(answer)
        pyperclip.copy(answer)

    else:
        print("Invalid choice.")
        return

    print("\nWaiting for connection...")
    for _ in range(50):
        await asyncio.sleep(0.1)
        if chat.connected:
            break

    if not chat.connected:
        print("Failed to connect.")
        return

    print("\nConnected! Type messages below (type 'exit' to quit).")

    while True:
        msg = input("You: ")
        if msg.lower() in ["exit", "quit"]:
            break
        chat.send_message(msg)

    await chat.close()
    print("Connection closed.")


def handle_signal(signum, frame):
    print("\nExiting...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")
