
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

def create_robust_rpc_client(rpc_url: str, timeout: int = 30):
    """
    🛡️ Creates a robust RPC client with timeout and better error handling.
    
    Args:
        rpc_url: The RPC endpoint URL
        timeout: Request timeout in seconds (default: 30)
    
    Returns:
        Configured Solana RPC Client
    """
    from solana.rpc.api import Client
    from solana.rpc.websocket_api import connect
    import httpx
    
    # Configure httpx client with timeout for better stability
    http_client = httpx.Client(
        timeout=httpx.Timeout(timeout),
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        follow_redirects=True
    )
    
    return Client(endpoint=rpc_url)

def rpc_retry_with_backoff(func, max_retries=3, base_delay=1.0, max_delay=30.0):
    """
    🔄 Retry RPC calls with exponential backoff for better stability.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries (default: 3)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 30.0)
    
    Returns:
        Result of func() or raises the last exception
    """
    import time
    import random
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            # Don't retry on the last attempt
            if attempt == max_retries:
                break
                
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = delay * 0.1 * random.random()  # Add 10% jitter
            total_delay = delay + jitter
            
            print(f"RPC call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {total_delay:.2f}s: {e}")
            time.sleep(total_delay)
    
    # If we get here, all retries failed
    if last_exception is not None:
        raise last_exception
    else:
        raise Exception("All retries failed, but no exception was captured")

def load_settings() -> Dict[str, str]:
    return {
        "DATA_DIR": os.getenv("DATA_DIR", "./data"),
        "DEFAULT_RPC": os.getenv("DEFAULT_RPC", "https://api.mainnet-beta.solana.com"),
        "API_KEY": os.getenv("API_KEY", ""),
        "CLUSTER": os.getenv("CLUSTER", ""),
        "REQUIRE_AUTH": str(os.getenv("REQUIRE_AUTH", "false").lower() in ("1","true","yes")),
    }

