# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Union, List
import json, os
import base58

# solana-py 0.31.x
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.rpc.types import TxOpts

# solders 0.19.x
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams

# Constantes
LAMPORTS_PER_SOL = 1_000_000_000
FALLBACK_FEE_LAMPORTS = 5_000         # ~5k lamports si l’estimation n’est pas dispo
MIN_LEFTOVER_LAMPORTS = 5_000         # petite marge (éviter de tout raser)

# ------------------------------
# Helpers bas niveau
# ------------------------------
def _get_balance_lamports(client: Client, pub: Pubkey) -> int:
    """Solde en lamports (commitment 'confirmed')."""
    resp = client.get_balance(pub, commitment="confirmed")
    return int(resp.value)  # solders renvoie directement un int dans .value

def _estimate_fee_lamports(client: Client, tx: Transaction) -> int:
    """Estime les frais en lamports via get_fee_for_message, fallback si indispo."""
    try:
        # Si mise à jour rb : tx.recent_blockhash = str(bh.value.blockhash)
        if not hasattr(tx, 'recent_blockhash') or not tx.recent_blockhash:
            bh = client.get_latest_blockhash()
            tx.recent_blockhash = bh.value.blockhash
        msg = tx.compile_message()
        fee_resp = client.get_fee_for_message(msg)
        return int(fee_resp.value) if fee_resp.value is not None else FALLBACK_FEE_LAMPORTS
    except Exception:
        return FALLBACK_FEE_LAMPORTS

def _get_min_rent_exempt_lamports(client: Client, data_len: int = 0) -> int:
    """
    Min rent-exempt pour un compte sans données (transfert SOL pur) ≈ 0.
    On garde la fonction pour extension futures (création de comptes, etc.).
    """
    try:
        # Pour un simple transfert SOL, l’ATA ou la création d’account n’est pas concernée ici.
        # Si tu crées des comptes plus tard: utilise get_minimum_balance_for_rent_exemption(data_len)
        return 0
    except Exception:
        return 0

def _keypair_from_any(secret: Union[str, List[int], bytes]) -> Keypair:
    """
    Accepte :
      - chemin de fichier JSON (array 64/32),
      - liste d’octets 64/32,
      - bytes 64/32,
      - base58 64/32.
    """
    # bytes / list(int)
    if isinstance(secret, list):
        b = bytes(secret)
        if len(b) == 64: return Keypair.from_bytes(b)
        if len(b) == 32: return Keypair.from_seed(b)
        raise ValueError("Liste d’octets invalide (attendu 32 ou 64).")

    if isinstance(secret, (bytes, bytearray)):
        b = bytes(secret)
        if len(b) == 64: return Keypair.from_bytes(b)
        if len(b) == 32: return Keypair.from_seed(b)
        raise ValueError("Secret bytes invalide (32 ou 64).")

    s = str(secret).strip()

    # fichier JSON ?
    if os.path.isfile(s):
        with open(s, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _keypair_from_any(data)

    # liste JSON encodée en str ?
    if s.startswith("[") and s.endswith("]"):
        return _keypair_from_any(json.loads(s))

    # base58 32/64
    raw = base58.b58decode(s)
    if len(raw) == 64: return Keypair.from_bytes(raw)
    if len(raw) == 32: return Keypair.from_seed(raw)

    raise ValueError("Clé privée invalide (attendu: fichier JSON, liste, base58 32/64 ou bytes).")

# ------------------------------
# API haut niveau
# ------------------------------
def send_sol(
    debtor_private_key: Union[str, List[int], bytes],
    recipient_pubkey_b58: str,
    amount_sol: Union[float, Decimal, str],
    rpc_url: str = "https://api.mainnet-beta.solana.com",
) -> str:
    """
    Envoie `amount_sol` SOL depuis la clé privée `debtor_private_key` vers `recipient_pubkey_b58`.
    Retourne la signature (str). Lève ValueError/RuntimeError sur erreur utilisateur ou RPC.
    """
    # 1) SOL -> lamports (arrondi vers le bas à 1e-9 SOL)
    lamports = int(
        (Decimal(str(amount_sol)).quantize(Decimal("0.000000001"), rounding=ROUND_DOWN))
        * LAMPORTS_PER_SOL
    )
    if lamports <= 0:
        raise ValueError("Montant doit être > 0.")

    # 2) Matos de base
    sender = _keypair_from_any(debtor_private_key)
    from_pub = sender.pubkey()
    to_pub = Pubkey.from_string(recipient_pubkey_b58)
    if from_pub == to_pub:
        raise ValueError("Destination identique à la source.")

    client = Client(rpc_url)

    # 3) Vérification solde et frais estimés
    balance = _get_balance_lamports(client, from_pub)

    # Obtenir le blockhash d'abord
    bh = client.get_latest_blockhash()
    rb = bh.value.blockhash  # Utiliser l'objet Hash directement
    
    # Construire une tx squelette pour estimer les frais
    dummy_tx = Transaction(recent_blockhash=rb, fee_payer=from_pub)
    dummy_tx.add(
        transfer(TransferParams(from_pubkey=from_pub, to_pubkey=to_pub, lamports=max(1, min(lamports, 1000))))
    )
    fee = _estimate_fee_lamports(client, dummy_tx)

    # Petite marge + rent-min (ici 0 pour transfert simple) + laisser un reste symbolique
    rent_min = _get_min_rent_exempt_lamports(client)
    needed = lamports + fee + rent_min
    if needed + MIN_LEFTOVER_LAMPORTS > balance:
        have_sol = balance / LAMPORTS_PER_SOL
        need_sol = needed / LAMPORTS_PER_SOL
        fee_sol = fee / LAMPORTS_PER_SOL
        raise ValueError(
            f"Fonds insuffisants: solde={have_sol:.9f} SOL, "
            f"requis(montant+frais)={need_sol:.9f} SOL (frais~{fee_sol:.9f} SOL)."
        )

    # 4) Construction + envoi
    # Obtenir un blockhash frais pour la transaction finale
    bh_final = client.get_latest_blockhash()
    rb2 = bh_final.value.blockhash  # Utiliser l'objet Hash directement
    tx = Transaction(recent_blockhash=rb2, fee_payer=from_pub)
    tx.add(
        transfer(TransferParams(from_pubkey=from_pub, to_pubkey=to_pub, lamports=lamports))
    )

    # Garde finale : s'assurer que recent_blockhash est bien défini
    if not tx.recent_blockhash:
        tx.recent_blockhash = client.get_latest_blockhash().value.blockhash

    sig = client.send_transaction(
        tx,
        sender,
        opts=TxOpts(skip_preflight=False, preflight_commitment="confirmed", max_retries=3),
    ).value

    # 5) Confirmation best-effort (facultatif)
    try:
        client.confirm_transaction(sig, commitment="confirmed")
    except Exception:
        pass

    return sig
