# -*- coding: utf-8 -*-
# src/wallet_service.py
from typing import Optional, Dict, Tuple, List, Any
import httpx
import json
import base64  # 🔥 FIX CRITIQUE: Import manquant pour base64
from solana.rpc.api import Client
from solana.rpc.types import TokenAccountOpts
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
    🛡️ ROBUST - Retourne le solde en SOL avec retry logic et timeout.
    Commitment 'confirmed' pour inclure les TX récentes.
    Soulève une exception si l'adresse est invalide ou si toutes les tentatives échouent.
    """
    from conrad.config import create_robust_rpc_client, rpc_retry_with_backoff
    from solana.rpc.commitment import Confirmed
    
    def _fetch_balance():
        c = create_robust_rpc_client(rpc_url, timeout=15)
        resp = c.get_balance(Pubkey.from_string(address), commitment=Confirmed)
        return int(resp.value) / LAMPORTS_PER_SOL
    
    return rpc_retry_with_backoff(_fetch_balance, max_retries=2, base_delay=0.5)

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
        from solders.signature import Signature
        from solana.rpc.commitment import Confirmed
        c.confirm_transaction(Signature.from_string(sig), commitment=Confirmed)
    except Exception:
        pass

    return sig


# -------- SPL Token Holdings --------

def get_spl_token_accounts(wallet_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com") -> List[Dict[str, Any]]:
    """
    🔥 FIXÉ - Récupère tous les comptes de tokens SPL d'un wallet.
    API solana-py CORRIGÉE pour parsing SPL tokens.
    Retourne une liste de token accounts avec les informations de base.
    """
    client = Client(rpc_url)
    pubkey = Pubkey.from_string(wallet_address)
    
    try:
        from solana.rpc.commitment import Confirmed
        # 🔥 FIX CRITIQUE: Client déjà importé en haut - pas besoin de re-import
        
        # 🔥 FIX CRITIQUE: API solana-py correcte avec mint filter
        spl_token_program_id = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
        
        # 🔥 FIX CRITIQUE: API solana-py correcte - encoding dans config, pas paramètre
        response = client.get_token_accounts_by_owner(
            pubkey,
            TokenAccountOpts(program_id=spl_token_program_id),
            commitment=Confirmed
        )
        
        token_accounts = []
        for account_info in response.value:
            try:
                account = account_info.account
                if not account or not account.data:
                    continue
                
                # 🔥 FIX CRITIQUE: Parser selon structure VRAIE solana-py
                raw_data = account.data
                if isinstance(raw_data, list) and len(raw_data) >= 2:
                    # Format: [data_base64_string, encoding]
                    data_str = str(raw_data[0])  # Assurer que c'est une string
                    data_bytes = base64.b64decode(data_str)
                elif isinstance(raw_data, str):
                    # Si c'est directement une string base64
                    data_bytes = base64.b64decode(raw_data)
                elif hasattr(raw_data, '__iter__'):
                    data_bytes = bytes(raw_data)
                else:
                    continue
                
                # Structure SPL Token Account: mint(32) + owner(32) + amount(8) + delegateOption(4+32) + state(1) + ...
                if len(data_bytes) < 72:  # Minimum pour SPL account
                    continue
                    
                # Parse SPL token account structure
                mint_bytes = data_bytes[0:32]
                owner_bytes = data_bytes[32:64] 
                amount_bytes = data_bytes[64:72]
                
                mint_address = str(Pubkey(mint_bytes))
                owner_address = str(Pubkey(owner_bytes))
                raw_amount = int.from_bytes(amount_bytes, 'little')
                
                # Vérifier que l'owner correspond au wallet demandé
                if owner_address != wallet_address:
                    continue
                
                # Récupérer les métadonnées pour les decimals
                try:
                    mint_info = client.get_account_info(Pubkey(mint_bytes))
                    if mint_info.value and mint_info.value.data:
                        mint_data = mint_info.value.data
                        if isinstance(mint_data, list) and len(mint_data) >= 2:
                            mint_raw = base64.b64decode(str(mint_data[0]))
                        else:
                            mint_raw = bytes(mint_data)
                        
                        # Decimals est à l'offset 44 dans SPL mint
                        decimals = mint_raw[44] if len(mint_raw) > 44 else 9
                    else:
                        decimals = 9
                except Exception:
                    decimals = 9
                
                # Calculer ui_amount avec les decimals
                ui_amount = raw_amount / (10 ** decimals) if raw_amount > 0 else 0.0
                
                # Ajouter seulement si le solde > 0
                if raw_amount > 0:
                    token_accounts.append({
                        "account_address": str(account_info.pubkey),
                        "mint": mint_address,
                        "amount": raw_amount,
                        "decimals": decimals,
                        "ui_amount": ui_amount,
                        "owner": wallet_address
                    })
                    
            except Exception as parse_error:
                print(f"Error parsing account {account_info.pubkey}: {parse_error}")
                continue
        
        return token_accounts
        
    except Exception as e:
        print(f"Error fetching token accounts for {wallet_address}: {e}")
        return []

def get_token_metadata(mint_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com") -> Dict[str, Any]:
    """
    Récupère les métadonnées d'un token depuis le registre Solana.
    Retourne name, symbol, decimals, etc.
    """
    client = Client(rpc_url)
    
    try:
        # Récupérer les informations du mint
        mint_pubkey = Pubkey.from_string(mint_address)
        mint_info = client.get_account_info(mint_pubkey)
        
        if not mint_info.value or not mint_info.value.data:
            return {"name": "Unknown Token", "symbol": "???", "decimals": 9}
        
        # Parse les données du mint (format SPL Token)
        data = mint_info.value.data
        decimals = data[44] if len(data) > 44 else 9
        
        # Essayer de récupérer les métadonnées depuis l'URI si disponible
        # Pour l'instant, retourner des infos de base
        return {
            "name": f"Token {mint_address[:8]}",
            "symbol": f"T{mint_address[:4].upper()}",
            "decimals": decimals,
            "mint": mint_address
        }
        
    except Exception as e:
        print(f"Error fetching token metadata for {mint_address}: {e}")
        return {"name": "Unknown Token", "symbol": "???", "decimals": 9, "mint": mint_address}

def get_token_price_coingecko(token_address: str, timeout: float = 5.0) -> Optional[float]:
    """
    Récupère le prix d'un token via CoinGecko (si listé).
    Retourne None si non trouvé.
    """
    try:
        # CoinGecko utilise des IDs spécifiques, pas les adresses de contrat directement
        # Pour l'instant, on ne peut pas facilement mapper les adresses Solana aux IDs CoinGecko
        # Cette fonction est préparée pour une extension future
        return None
    except Exception:
        return None

def get_wallet_token_holdings(wallet_address: str, rpc_url: str = "https://api.mainnet-beta.solana.com") -> List[Dict[str, Any]]:
    """
    Récupère tous les holdings de tokens d'un wallet avec métadonnées et valeurs.
    """
    token_accounts = get_spl_token_accounts(wallet_address, rpc_url)
    holdings = []
    
    for account in token_accounts:
        mint = account["mint"]
        raw_amount = account["amount"]
        
        # Récupérer les métadonnées du token
        metadata = get_token_metadata(mint, rpc_url)
        decimals = metadata.get("decimals", 9)
        
        # Calculer le montant réel avec les décimales
        actual_amount = raw_amount / (10 ** decimals)
        
        # Essayer de récupérer le prix
        price_usd = get_token_price_coingecko(mint)
        value_usd = (actual_amount * price_usd) if price_usd else None
        
        if actual_amount > 0:  # Ne retourner que les tokens avec un solde > 0
            holdings.append({
                "token_address": mint,
                "account_address": account["account_address"],
                "name": metadata.get("name", "Unknown Token"),
                "symbol": metadata.get("symbol", "???"),
                "decimals": decimals,
                "balance": actual_amount,
                "raw_balance": raw_amount,
                "ui_amount": account.get("ui_amount", actual_amount),  # 🔥 FIX: Utiliser ui_amount si disponible
                "price_usd": price_usd,
                "value_usd": value_usd
            })
    
    return holdings
