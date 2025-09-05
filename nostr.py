import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from httpx_ws import aconnect_ws, AsyncWebSocketSession  # type: ignore

from crypto import create_event_id, sign_event_id


def create_nostr_event(
    kind: int,
    content: str,
    identity: tuple[str, str],
    tags: list[list[str]] | None = None,
) -> dict[str, Any]:
    created_at = int(time.time())
    tg = tags or []
    event_id = create_event_id(identity[1], created_at, kind, tg, content)
    return {
        "id": event_id,
        "pubkey": identity[1],
        "created_at": created_at,
        "kind": kind,
        "tags": tg,
        "content": content,
        "sig": sign_event_id(event_id, identity[0]),
    }


async def publish_to_relay(relay_url: str, event: dict[str, Any]) -> bool:
    client = httpx.AsyncClient(http2=False, timeout=None)
    try:
        async with aconnect_ws(relay_url, client) as ws_raw:  # type: AsyncWebSocketSession
            ws = cast(AsyncWebSocketSession, ws_raw)
            await ws.send_text(json.dumps(["EVENT", event]))
            try:
                data = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=5))
                return (
                    isinstance(data, list)
                    and len(data) >= 3
                    and data[0] == "OK"
                    and bool(data[2])
                )
            except asyncio.TimeoutError:
                return False
    except Exception:
        return False
    finally:
        await client.aclose()


async def publish_event(
    relays: str | list[str], event: dict[str, Any]
) -> dict[str, Any]:
    relay_list = [relays] if isinstance(relays, str) else relays
    results = await asyncio.gather(*(publish_to_relay(r, event) for r in relay_list))
    out = dict(event)
    out["_publish_results"] = dict(zip(relay_list, results))
    return out


async def reply_to_message(
    publish_relays: str | list[str],
    identity: tuple[str, str],
    message: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    msg_tags = message.get("tags", [])
    root_id = (
        next(
            (
                t[1]
                for t in msg_tags
                if isinstance(t, list)
                and len(t) >= 4
                and t[0] == "e"
                and t[3] == "root"
            ),
            None,
        )
        or next(
            (
                t[1]
                for t in msg_tags
                if isinstance(t, list) and len(t) >= 2 and t[0] == "e"
            ),
            None,
        )
        or message["id"]
    )
    relay_hint = message.get("relay", "")
    tags: list[list[str]] = [
        ["e", root_id, relay_hint, "root"],
        ["e", message["id"], relay_hint, "reply"],
        *([["p", message["pubkey"]]] if message.get("pubkey") else []),
    ]
    published_event = await publish_event(
        relays=publish_relays,
        event=create_nostr_event(kind=1, content=content, identity=identity, tags=tags),
    )
    successful_relays = [
        relay
        for relay, success in published_event["_publish_results"].items()
        if success
    ]
    print(
        f"Replied successfully to {len(successful_relays)}/{len(published_event['_publish_results'])} relays"
    )
    return published_event


async def stream_nostr_messages(
    relays: str | list[str],
    filters: list[dict[str, Any]] | None = None,
    timeout: float | None = None,
    since_seconds: int = 1,
) -> AsyncIterator[dict[str, Any]]:
    since_cutoff = int(time.time()) - max(0, since_seconds)
    subscription_filters = [{**f, "since": since_cutoff} for f in (filters or [{}])]
    relay_urls = [relays] if isinstance(relays, str) else relays

    out_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    seen_event_ids: set[str] = set()
    seen_lock = asyncio.Lock()
    tasks: list[asyncio.Task[None]] = []

    async def _relay_worker(relay_url: str) -> None:
        client = httpx.AsyncClient(http2=False, timeout=None)
        try:
            async with aconnect_ws(relay_url, client) as ws_raw:  # type: AsyncWebSocketSession
                ws = cast(AsyncWebSocketSession, ws_raw)
                subscription_id = f"sub_{int(time.time() * 1000)}"
                req_message = ["REQ", subscription_id, *subscription_filters]
                await ws.send_text(json.dumps(req_message))

                while True:
                    message = await ws.receive_text()
                    try:
                        data = json.loads(message)
                        if (
                            isinstance(data, list)
                            and len(data) >= 3
                            and data[0] == "EVENT"
                            and isinstance(data[2], dict)
                            and "id" in data[2]
                        ):
                            event = data[2]
                            if (
                                isinstance(event.get("created_at"), int)
                                and event["created_at"] < since_cutoff
                            ):
                                continue
                            event_id = event["id"]
                            async with seen_lock:
                                if event_id in seen_event_ids:
                                    continue
                                seen_event_ids.add(event_id)
                            event["relay"] = relay_url
                            await out_queue.put(event)
                    except json.JSONDecodeError:
                        continue
        finally:
            await client.aclose()

    try:
        for relay_url in relay_urls:
            tasks.append(asyncio.create_task(_relay_worker(relay_url)))

        start_time = time.time() if timeout else None

        while True:
            if (
                timeout is not None
                and start_time is not None
                and (time.time() - start_time) > timeout
            ):
                break

            if tasks and all(t.done() for t in tasks) and out_queue.empty():
                break

            try:
                event = await asyncio.wait_for(out_queue.get(), timeout=0.05)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
