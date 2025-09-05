import asyncio
import os
from crypto import encode_npub, init_identity
from nostr import stream_nostr_messages, reply_to_message
from ai import generate_ai_response

relays = [
    "wss://relay.damus.io",
    "wss://relay.primal.net",
    "wss://pyramid.fiatjaf.com/",
    "wss://relay.nostr.band/",
    "wss://nos.lol",
]

nsec = os.getenv("NSEC")
privkey, pubkey = init_identity(nsec)
activation_cmd = os.getenv("ACTIVATION_CMD", "!robot")

print(f"Bot started with identity: {encode_npub(pubkey)}")


def activation_condition(message: dict) -> bool:
    print(
        f"Message received from {encode_npub(message['pubkey'])}: {message['content'][:50]}{'...' if len(message['content']) > 50 else ''}"
    )
    return message["content"].startswith(activation_cmd) or pubkey in message["content"]


async def main():
    async for message in stream_nostr_messages(
        relays=relays, filters=[{"kinds": [1]}], since_seconds=1
    ):
        if activation_condition(message):
            response = await generate_ai_response(
                message["content"],
            )
            await reply_to_message(
                relays,
                (privkey, pubkey),
                message,
                response,
            )


if __name__ == "__main__":
    asyncio.run(main())
