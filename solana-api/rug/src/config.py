# -*- coding: utf-8 -*-
# src/config.py
from pathlib import Path


DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
# Réseaux Solana

DEVNET_RPC = "https://api.devnet.solana.com"


# Dossier de données (projets)
DATA_DIR = Path("./data")

# RPC par défaut (mainnet). Tu peux basculer vers devnet si besoin.
# Exemple alternatif public (si throttling) :
# DEFAULT_RPC = "https://rpc.ankr.com/solana"

# Rafraîchissement auto des soldes/prix dans le menu Wallets (secondes)
REFRESH_INTERVAL = 10.0


def is_devnet_url(url: str) -> bool:
    u = (url or "").lower()
    return ("devnet" in u) or ("testnet" in u) or ("localhost" in u) or ("127.0.0.1" in u)
