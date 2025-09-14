
# -*- coding: utf-8 -*-
import os
from typing import Dict

RPC_PRESETS = {
    "mainnet": os.getenv("SOLANA_MAINNET_RPC", "https://api.mainnet-beta.solana.com"),
    "mainnet-beta": os.getenv("SOLANA_MAINNET_RPC", "https://api.mainnet-beta.solana.com"),
    "testnet": os.getenv("SOLANA_TESTNET_RPC", "https://api.testnet.solana.com"),
    "devnet": os.getenv("SOLANA_DEVNET_RPC", "https://api.devnet.solana.com"),
}

def resolve_rpc(default_rpc: str, cluster: str | None, override_rpc: str | None) -> str:
    if override_rpc:
        return override_rpc.strip()
    if cluster:
        c = cluster.strip().lower()
        if c in RPC_PRESETS:
            return RPC_PRESETS[c]
    return default_rpc

def resolve_api_key(cluster: str | None) -> str:
    base = (os.getenv("API_KEY") or "").strip()
    c = (cluster or "").strip().lower()
    if not c:
        return base
    env_name = {
        "devnet": "API_KEY_DEVNET",
        "testnet": "API_KEY_TESTNET",
        "mainnet": "API_KEY_MAINNET",
        "mainnet-beta": "API_KEY_MAINNET",
    }.get(c)
    if env_name:
        v = (os.getenv(env_name) or "").strip()
        return v or base
    return base

# -*- coding: utf-8 -*-
import os
from typing import Dict

def load_settings() -> Dict[str, str]:
    return {
        "DATA_DIR": os.getenv("DATA_DIR", "./data"),
        "DEFAULT_RPC": os.getenv("DEFAULT_RPC", "https://api.mainnet-beta.solana.com"),
        "API_KEY": os.getenv("API_KEY", ""),
        "CLUSTER": os.getenv("CLUSTER", ""),
        "REQUIRE_AUTH": str(os.getenv("REQUIRE_AUTH", "false").lower() in ("1","true","yes")),
    }

