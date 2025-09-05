import asyncio
import os
from crypto import (
    generate_ephemeral_keypair,
    encode_npub,
    decode_nsec_to_hex,
    priv_to_pub_hex,
)
from nostr import stream_nostr_messages, reply_to_message
from ai import generate_ai_response

relays = [
    "wss://relay.damus.io",
    "wss://relay.primal.net",
    "wss://nos.lol",
    "wss://offchain.pub",
    "wss://nostr21.com",
    "wss://pyramid.fiatjaf.com/",
    "wss://relay.sig.fun",
]

nsec = os.getenv("NSEC")
bot_identity = (
    (decode_nsec_to_hex(nsec), priv_to_pub_hex(decode_nsec_to_hex(nsec)))
    if nsec
    else generate_ephemeral_keypair()
)
activation_cmd = os.getenv("ACTIVATION_CMD", "!robot")
print(f"Bot started with identity: {encode_npub(bot_identity[1])}")


async def main():
    async for message in stream_nostr_messages(
        relays=relays,
        filters=[{"kinds": [1]}],
        since_seconds=60 * 10,
    ):
        if activation_cmd in message["content"]:
            print(
                f"Processing message from {encode_npub(message['pubkey'])}: {message['content'][:50]}{'...' if len(message['content']) > 50 else ''}"
            )

            response = await generate_ai_response(
                message["content"],
            )
            await reply_to_message(
                relays,
                bot_identity,
                message,
                response,
            )


if __name__ == "__main__":
    asyncio.run(main())
