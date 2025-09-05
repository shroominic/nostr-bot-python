import hashlib
import json
from coincurve import PrivateKey


# --- Lightweight NIP-19 (Bech32) helpers ---
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
CHARSET_MAP = {c: i for i, c in enumerate(CHARSET)}


def init_identity(nsec: str | None) -> tuple[str, str]:
    return (
        (decode_nsec_to_hex(nsec), priv_to_pub_hex(decode_nsec_to_hex(nsec)))
        if nsec
        else generate_ephemeral_keypair()
    )


def _bech32_polymod(values: list[int]) -> int:
    gen = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i, g in enumerate(gen):
            chk ^= g if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    pm = _bech32_polymod(_bech32_hrp_expand(hrp) + data + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(pm >> 5 * (5 - i)) & 31 for i in range(6)]


def _bech32_verify_checksum(hrp: str, data: list[int]) -> bool:
    return _bech32_polymod(_bech32_hrp_expand(hrp) + data) == 1


def _bech32_encode(hrp: str, data: list[int]) -> str:
    return (
        hrp
        + "1"
        + "".join(CHARSET[d] for d in data + _bech32_create_checksum(hrp, data))
    )


def _bech32_decode(bech: str) -> tuple[str, list[int]]:
    if any(ord(x) < 33 or ord(x) > 126 for x in bech):
        raise ValueError("invalid bech32 characters")
    if bech.lower() != bech and bech.upper() != bech:
        raise ValueError("mixed-case bech32 not allowed")
    bech = bech.lower()
    pos = bech.rfind("1")
    if pos < 1 or pos + 7 > len(bech):
        raise ValueError("invalid bech32 separator position")
    hrp, data = bech[:pos], [CHARSET_MAP.get(c, -1) for c in bech[pos + 1 :]]
    if any(d == -1 for d in data) or not _bech32_verify_checksum(hrp, data):
        raise ValueError("invalid bech32 checksum or chars")
    return hrp, data[:-6]


def _convertbits(
    data: bytes | list[int], from_bits: int, to_bits: int, pad: bool
) -> list[int]:
    acc = 0
    bits = 0
    ret: list[int] = []
    maxv = (1 << to_bits) - 1
    max_acc = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        if value < 0 or (value >> from_bits):
            raise ValueError("invalid bit group")
        acc = ((acc << from_bits) | value) & max_acc
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (to_bits - bits)) & maxv)
    elif bits >= from_bits or ((acc << (to_bits - bits)) & maxv):
        raise ValueError("non-zero padding")
    return ret


def encode_npub(pubkey_hex: str) -> str:
    if len(pubkey_hex) != 64:
        raise ValueError("pubkey must be 32 bytes hex")
    return _bech32_encode("npub", _convertbits(bytes.fromhex(pubkey_hex), 8, 5, True))


def encode_nsec(privkey_hex: str) -> str:
    if len(privkey_hex) != 64:
        raise ValueError("privkey must be 32 bytes hex")
    return _bech32_encode("nsec", _convertbits(bytes.fromhex(privkey_hex), 8, 5, True))


def encode_note_id(event_id_hex: str) -> str:
    if len(event_id_hex) != 64:
        raise ValueError("event id must be 32 bytes hex")
    return _bech32_encode("note", _convertbits(bytes.fromhex(event_id_hex), 8, 5, True))


def decode_npub_to_hex(npub: str) -> str:
    hrp, data = _bech32_decode(npub)
    if hrp != "npub":
        raise ValueError("invalid hrp for npub")
    b = bytes(_convertbits(data, 5, 8, False))
    if len(b) != 32:
        raise ValueError("invalid npub payload length")
    return b.hex()


def decode_nsec_to_hex(nsec: str) -> str:
    hrp, data = _bech32_decode(nsec)
    if hrp != "nsec":
        raise ValueError("invalid hrp for nsec")
    b = bytes(_convertbits(data, 5, 8, False))
    if len(b) != 32:
        raise ValueError("invalid nsec payload length")
    return b.hex()


def decode_note_to_event_id_hex(note: str) -> str:
    hrp, data = _bech32_decode(note)
    if hrp != "note":
        raise ValueError("invalid hrp for note")
    b = bytes(_convertbits(data, 5, 8, False))
    if len(b) != 32:
        raise ValueError("invalid note payload length")
    return b.hex()


def generate_ephemeral_keypair() -> tuple[str, str]:
    pk = PrivateKey()
    return pk.secret.hex(), pk.public_key.format(compressed=False)[1:33].hex()


def priv_to_pub_hex(private_key_hex: str) -> str:
    return (
        PrivateKey(bytes.fromhex(private_key_hex))
        .public_key.format(compressed=False)[1:33]
        .hex()
    )


def create_event_id(
    pubkey: str, created_at: int, kind: int, tags: list[list[str]], content: str
) -> str:
    return hashlib.sha256(
        json.dumps(
            [0, pubkey, created_at, kind, tags, content],
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def sign_event_id(event_id: str, private_key_hex: str) -> str:
    return (
        PrivateKey(bytes.fromhex(private_key_hex))
        .sign_schnorr(bytes.fromhex(event_id))
        .hex()
    )
