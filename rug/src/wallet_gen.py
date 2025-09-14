# -*- coding: utf-8 -*-
from typing import Dict, List
from nacl.signing import SigningKey
import base58

def generate_wallet() -> Dict:
    sk = SigningKey.generate()
    vk = sk.verify_key
    priv32 = sk.encode()
    pub32 = vk.encode()
    address_b58 = base58.b58encode(pub32).decode()
    secret64 = priv32 + pub32
    secret64_b58 = base58.b58encode(secret64).decode()
    secret64_json = list(secret64)
    return {
        "address": address_b58,
        "private_key_base58_64": secret64_b58,
        "private_key_json_64": secret64_json,
        "public_key_hex": pub32.hex(),
        "private_key_hex_32": priv32.hex(),
    }
