from typing import Any
import os
from openai import AsyncOpenAI

TOKEN = os.getenv(
    "TOKEN",
    "cashuBpGFkYGF0gaJhaUgAUAVQ8ElBRmFwgaRhYRkEAGFko2FyWCDN2NAM521_1rbkQC7J22Ef6gR9iM2bTbhjrmBc-wDUR2FlWCB3d0b25tYbdWavCfsC8Zla3wBD2zfA4ZFuimlHVj0oemFzWCCyVQ6cZFDtJB2ycvfx8PpP3CYEBt4sQDXs264wdxTTpmFzeEA3Mjk1ZDk1N2UyMzVjNmUwODc1MmFlZTkyMjNjZDUzMTIxZWZhOWE2N2M1MzllZmZhMjViZjkzMjEyYzY4ODJkYWNYIQKbkzqcki9t7y0Pw3AUDKonEK81bprtGlJak_XQz9JDWmF1Y3NhdGFteCJodHRwczovL21pbnQubWluaWJpdHMuY2FzaC9CaXRjb2lu",
)
BASE_URL = os.getenv("BASE_URL", "https://api.routstr.com/v1")
MODEL = os.getenv("MODEL", "deepcogito/cogito-v2-preview-llama-109b-moe")
PROMPT = os.getenv(
    "PROMPT",
    (
        "You are a nostr meme robot! Keep responses under 512 chars. "
        "Be funny but not cringe. Shitpost."
    ),
)

client = AsyncOpenAI(api_key=TOKEN, base_url=BASE_URL)


async def generate_ai_response(message: str, **kwargs: Any) -> str:
    print(
        f"Generating AI response for: {message[:50]}{'...' if len(message) > 50 else ''}"
    )
    resp = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": message},
        ],
        **kwargs,
    )
    response_content = (resp.choices[0].message.content or "").strip()
    print(
        f"AI response: {response_content[:50]}{'...' if len(response_content) > 50 else ''}"
    )
    return response_content
