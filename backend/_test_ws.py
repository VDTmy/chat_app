"""
Interactive WebSocket test script.

Usage:
    python _test_ws.py

Steps:
    1. Registers 2 users (Alice & Bob)
    2. Logs in to get tokens
    3. Creates a private conversation between them
    4. Connects both users to WebSocket
    5. Alice sends a message → Bob receives it in real-time
    6. Tests typing indicators and mark_seen
"""

import asyncio
import json
import sys
import httpx
import websockets

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://127.0.0.1:8000"
WS_BASE = "ws://127.0.0.1:8000"


async def register_and_login(client: httpx.AsyncClient, email: str, username: str, password: str) -> dict:
    """Register a user (ignore 409 if exists), then login and return tokens + user info."""
    # Register (ignore conflict)
    await client.post(f"{BASE}/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "password": password,
    })

    # Login
    resp = await client.post(f"{BASE}/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    tokens = resp.json()

    # Get user info
    resp = await client.get(f"{BASE}/api/v1/auth/me", headers={
        "Authorization": f"Bearer {tokens['access_token']}"
    })
    user = resp.json()

    return {"tokens": tokens, "user": user}


async def main():
    print("=" * 60)
    print("  WebSocket Test Script")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        # ── Step 1: Register & Login ──────────────────────────────
        print("\n[1] Registering & logging in users...")
        alice = await register_and_login(client, "alice@test.com", "alice", "password123")
        bob = await register_and_login(client, "bob@test.com", "bob", "password123")

        alice_token = alice["tokens"]["access_token"]
        bob_token = bob["tokens"]["access_token"]
        alice_id = alice["user"]["id"]
        bob_id = bob["user"]["id"]

        print(f"    ✓ Alice: {alice_id}")
        print(f"    ✓ Bob:   {bob_id}")

        # ── Step 2: Create private conversation ──────────────────
        print("\n[2] Creating private conversation...")
        resp = await client.post(
            f"{BASE}/api/v1/conversations/private",
            json={"user_id": bob_id},
            headers={"Authorization": f"Bearer {alice_token}"},
        )
        conv = resp.json()
        conv_id = conv["id"]
        print(f"    ✓ Conversation: {conv_id}")

        # ── Step 3: Connect both to WebSocket ────────────────────
        print("\n[3] Connecting to WebSocket...")

        bob_messages = []

        async def bob_listener(ws_bob):
            """Bob listens for incoming messages."""
            try:
                async for msg in ws_bob:
                    data = json.loads(msg)
                    bob_messages.append(data)
                    event_type = data.get("type", "?")
                    print(f"    📨 Bob received: {event_type} → {json.dumps(data['payload'], indent=2, default=str)}")
            except websockets.exceptions.ConnectionClosed:
                pass

        async with websockets.connect(f"{WS_BASE}/ws?token={alice_token}") as ws_alice, \
                   websockets.connect(f"{WS_BASE}/ws?token={bob_token}") as ws_bob:

            # Start Bob's listener in background
            bob_task = asyncio.create_task(bob_listener(ws_bob))

            # Wait for connection confirmations
            alice_welcome = json.loads(await ws_alice.recv())
            print(f"    ✓ Alice connected: {alice_welcome['type']}")

            # Give Bob time to receive his welcome + user_online events
            await asyncio.sleep(0.5)

            # ── Step 4: Alice sends typing_start ─────────────────
            print("\n[4] Alice starts typing...")
            await ws_alice.send(json.dumps({
                "type": "typing_start",
                "payload": {"conversation_id": conv_id}
            }))
            await asyncio.sleep(0.3)

            # ── Step 5: Alice stops typing ───────────────────────
            print("\n[5] Alice stops typing...")
            await ws_alice.send(json.dumps({
                "type": "typing_stop",
                "payload": {"conversation_id": conv_id}
            }))
            await asyncio.sleep(0.3)

            # ── Step 6: Alice sends a message ────────────────────
            print("\n[6] Alice sends a message...")
            await ws_alice.send(json.dumps({
                "type": "send_message",
                "payload": {
                    "conversation_id": conv_id,
                    "content": "Hello Bob! 👋 This is a real-time WebSocket message!",
                }
            }))

            # Alice also receives the broadcast
            alice_echo = json.loads(await ws_alice.recv())
            print(f"    ✓ Alice echo: {alice_echo['type']}")

            await asyncio.sleep(0.5)

            # ── Step 7: Bob marks conversation as seen ───────────
            print("\n[7] Bob marks conversation as seen...")
            await ws_bob.send(json.dumps({
                "type": "mark_seen",
                "payload": {"conversation_id": conv_id}
            }))
            await asyncio.sleep(0.5)

            # ── Step 8: Test error handling ───────────────────────
            print("\n[8] Testing error handling (unknown event)...")
            await ws_alice.send(json.dumps({
                "type": "unknown_event",
                "payload": {}
            }))
            # Drain until we find the error response (may have pending events)
            for _ in range(5):
                resp = json.loads(await ws_alice.recv())
                if resp.get("type") == "error":
                    print(f"    OK Error response: {resp['payload']['message']}")
                    break
                else:
                    print(f"    (drained pending event: {resp['type']})")

            # ── Cleanup ──────────────────────────────────────────
            bob_task.cancel()
            try:
                await bob_task
            except asyncio.CancelledError:
                pass

        # After disconnect, wait a moment for offline broadcast
        await asyncio.sleep(0.5)

    # ── Summary ──────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    print(f"  Bob received {len(bob_messages)} events:")
    for msg in bob_messages:
        print(f"    • {msg['type']}")
    print("\n  ✅ WebSocket test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
