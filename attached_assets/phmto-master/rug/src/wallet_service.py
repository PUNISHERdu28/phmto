# -*- coding: utf-8 -*-
# src/wallet_service.py
from typing import Optional, Dict, Tuple, List
import httpx
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from .models import Project

from .config import DEVNET_RPC, is_devnet_url


LAMPORTS_PER_SOL = 1_000_000_000



# -------- Prix / balances --------

def get_sol_price_usd(timeout: float = 5.0) -> float:
    """Prix spot approximatif via CoinGecko."""
    url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
    with httpx.Client(timeout=timeout) as cli:
        r = cli.get(url)
        r.raise_for_status()
        data = r.json()
        return float(data["solana"]["usd"])

def get_balance_sol(address: str, rpc_url: str = "https://api.mainnet-beta.solana.com") -> float:
    """
    Retourne le solde en SOL (commitment 'confirmed' pour inclure les TX récentes).
    Soulève une exception si l'adresse est invalide ou si la RPC renvoie une erreur.
    """
    c = Client(rpc_url)
    resp = c.get_balance(Pubkey.from_string(address), commitment="confirmed")
    lamports = int(resp.value)  # ✅ .value est un int directement
    return lamports / LAMPORTS_PER_SOL

def fetch_wallets_balances(project: Project, rpc_url: str, price_usd: float) -> Dict[str, Tuple[Optional[float], Optional[float]]]:
    """
    Retourne {address: (sol, usd)}.
    Si erreur RPC → (None, None) pour que l’UI affiche [err RPC].
    """
    out: Dict[str, Tuple[Optional[float], Optional[float]]] = {}
    for w in project.wallets:
        try:
            sol = get_balance_sol(w.address, rpc_url)
            out[w.address] = (sol, sol * price_usd if price_usd else None)
        except Exception:
            out[w.address] = (None, None)
    return out

def build_wallet_label(i: int, addr: str, balances: Dict[str, Tuple[Optional[float], Optional[float]]], price_usd: Optional[float]) -> str:
    """
    Rend une ligne lisible pour la liste de wallets :
      - données ok → "Wallet n — addr — 0.001234 SOL (~$0.22)"
      - erreur RPC  → "Wallet n — addr — [err RPC]"
      - pas encore   → "Wallet n — addr — (en attente...)"
    """
    v = balances.get(addr)
    if v is None:
        return f"Wallet {i} — {addr} — [dim](en attente...)[/dim]"
    sol, usd = v
    if sol is None:
        return f"Wallet {i} — {addr} — [red][err RPC][/red]"
    if price_usd is not None:
        return f"Wallet {i} — {addr} — {sol:.6f} SOL (~${sol*price_usd:.2f})"
    return f"Wallet {i} — {addr} — {sol:.6f} SOL"

def request_airdrop_devnet(address: str, amount_sol: float, rpc_url: str = DEVNET_RPC, commitment: str = "confirmed") -> str:
    """
    Demande un airdrop en DEVNET/TESTNET.
    Retourne la signature de la TX d'airdrop.
    """
    if not is_devnet_url(rpc_url):
        raise ValueError("L'airdrop n'est disponible que sur devnet/testnet (ou local validator).")

    if amount_sol <= 0:
        raise ValueError("Montant d'airdrop invalide (doit être > 0).")

    lamports = int(amount_sol * 1_000_000_000)
    c = Client(rpc_url)

    resp = c.request_airdrop(Pubkey.from_string(address), lamports)
    # solders: resp.value = signature (str)
    sig = str(resp.value)

    try:
        c.confirm_transaction(sig, commitment=commitment)
    except Exception:
        pass

    return sig
