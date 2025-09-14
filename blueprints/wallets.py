# routes_wallets.py
# -*- coding: utf-8 -*-
"""
Endpoints liés aux wallets.
Ajout : GET /api/v1/wallets/<wallet_id>/private-key (exposition contrôlée de la clé privée).
"""

import os
from datetime import datetime, timezone
from flask import Blueprint, current_app, request, jsonify
from pathlib import Path
from middleware.auth import require_api_key
from api_utils import find_project_dir
from config import resolve_rpc
from services.backups import backup_wallet
from services.fileio import ensure_dir
from rug.src.project_service import load_project, save_project, generate_wallets
from rug.src.wallet_service import get_balance_sol
# Ajouts pour les transactions Solana (solders)

from solana.rpc.api import Client as RpcClient     # ✅ bon client RPC

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer as sp_transfer, TransferParams
from solders.message import Message
from solders.transaction import Transaction
from solana.rpc.api import Client as RpcClient     # ✅ bon client RPC

from solana.rpc.api import Client as RpcClient
from solana.rpc.types import TokenAccountOpts 

from solders.hash import Hash

from typing import Optional, Tuple, Dict, Any, List
import random

bp = Blueprint("wallets", __name__, url_prefix="/api/v1")
def _bool_env(var_name: str, default: bool = False) -> bool:
    """Parse bool depuis env (1/true/yes/on)."""
    v = os.getenv(var_name)
    if v is None:
        return default
    return str(v).lower() in ("1", "true", "yes", "y", "on")


def _rpc_client_from_config() -> Tuple[RpcClient, str]:
    """
    Construit un client RPC solders depuis la config Flask + query args.
    On respecte la logique existante: resolve_rpc(default_rpc, cluster_param, rpc_param).
    Retourne (client, rpc_url).
    """
    default_rpc = current_app.config["DEFAULT_RPC"]
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (request.args.get("cluster") or env_cluster or "").strip()
    rpc_param = (request.args.get("rpc") or "").strip()
    rpc = resolve_rpc(default_rpc, cluster_param, rpc_param)
    return RpcClient(rpc), rpc


def _projects_root(base_dir: str) -> Path:
    return Path(base_dir) / "projects"


def _list_project_dirs(base_dir: str) -> List[Path]:
    root = _projects_root(base_dir)
    if not root.exists():
        return []
    return [d for d in root.iterdir() if d.is_dir()]


def _find_wallet_by_id(base_dir: str, wallet_id: str) -> Optional[Tuple[Any, Dict[str, Any], Path]]:
    """
    Scan de tous les projets en DATA_DIR pour trouver un wallet par son ID.
    Retour: (project_obj, wallet_dict, project_dir) | None
    """
    for pdir in _list_project_dirs(base_dir):
        try:
            pr = load_project(pdir)
            pd = pr.to_dict() or {}
            wallets = pd.get("wallets") or []
            for w in wallets:
                wid = str(w.get("id") or w.get("wallet_id") or "")
                if wid == str(wallet_id):
                    return pr, w, pdir
        except Exception:
            continue
    return None


def _get_wallet_privkey_b58(wallet: Dict[str, Any]) -> Optional[str]:
    """Récupère la clé privée base58 depuis différents champs possibles."""
    return wallet.get("private_key_base58_64") or wallet.get("private_key") or wallet.get("secret")


def _get_wallet_pubkey_str(wallet: Dict[str, Any]) -> Optional[str]:
    """Récupère l'address/pubkey d'un wallet."""
    return wallet.get("address") or wallet.get("pubkey")

from solders.hash import Hash

def _get_latest_blockhash_hash(client: RpcClient) -> Hash:
    """
    Récupère le dernier blockhash via solana-py et le convertit en solders.Hash.
    Compatible solana-py ≥ 0.30 (objet) et fallback dict.
    """
    resp = client.get_latest_blockhash()
    if hasattr(resp, "value") and hasattr(resp.value, "blockhash"):
        bh = resp.value.blockhash
    else:
        try:
            bh = resp["result"]["value"]["blockhash"]
        except Exception:
            raise RuntimeError(f"Unexpected get_latest_blockhash response: {resp}")
    return Hash.from_string(str(bh))
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer as sp_transfer, TransferParams
from solders.message import Message
from solders.transaction import Transaction
from solana.rpc.api import Client as RpcClient

def _sign_and_send_transfer(client: RpcClient, sender_kp: Keypair, recipient_b58: str, amount_sol: float) -> str:
    lamports = int(amount_sol * 1_000_000_000)
    ix = sp_transfer(
        TransferParams(
            from_pubkey=sender_kp.pubkey(),
            to_pubkey=Pubkey.from_string(recipient_b58),
            lamports=lamports,
        )
    )
    recent_blockhash = _get_latest_blockhash(client)
    msg = Message.new_with_blockhash(
        [ix],
        payer=sender_kp.pubkey(),
        blockhash=recent_blockhash
    )
    tx = Transaction([sender_kp], msg)        # signature via solders
    sig = client.send_transaction(tx).value   # renvoie la signature base58 (solana>=0.30)
    return str(sig)


def _get_balance_sol_solders(client: RpcClient, pubkey_b58: str) -> float:
    """Balance en SOL via solders (lamports → SOL)."""
    lamports = client.get_balance(Pubkey.from_string(pubkey_b58)).value
    return float(lamports) / 1_000_000_000.0

@bp.post("/wallets/mix")
@require_api_key
def mix_wallets():
    """
    Mélange des SOL entre une liste de wallets.
    JSON attendu:
      {
        "wallet_ids": ["w1","w2","w3"],
        "strategy": "random" | "roundrobin"
      }
    Stratégie:
      - random    : chaque source envoie un montant pseudo-aléatoire <= solde disponible vers une cible différente
      - roundrobin: chaque source envoie ~solde/2 vers la suivante (anneau)
    Réponse: historique détaillé des transferts (qui → qui, combien, signature).
    """
    data = request.get_json(force=True, silent=True) or {}
    wallet_ids = data.get("wallet_ids") or []
    strategy = (data.get("strategy") or "random").lower().strip()
    if not wallet_ids or not isinstance(wallet_ids, list):
        return jsonify({"ok": False, "error": "wallet_ids must be a non-empty list"}), 400
    if strategy not in ("random", "roundrobin"):
        return jsonify({"ok": False, "error": "strategy must be 'random' or 'roundrobin'"}), 400

    base = current_app.config["DATA_DIR"]
    # Résoudre tous les wallets
    resolved: List[Tuple[Any, Dict[str, Any], Path]] = []
    for wid in wallet_ids:
        f = _find_wallet_by_id(base, str(wid))
        if not f:
            return jsonify({"ok": False, "error": f"wallet '{wid}' not found"}), 404
        resolved.append(f)

    client, rpc_url = _rpc_client_from_config()

    # Préparer balances et clés
    wallets_info = []
    for pr, w, pdir in resolved:
        addr = _get_wallet_pubkey_str(w)
        priv = _get_wallet_privkey_b58(w)
        if not addr or not priv:
            return jsonify({"ok": False, "error": f"wallet missing key/address (id={w.get('id') or w.get('wallet_id')})"}), 400
        bal = _get_balance_sol_solders(client, addr)
        wallets_info.append({
            "project": pr,
            "wallet": w,
            "address": addr,
            "priv": priv,
            "balance": bal
        })

    history = []  # journal détaillé de chaque envoi
    try:
        if strategy == "roundrobin":
            # Anneau: i -> (i+1) % n, montant = balance / 2 (simple heuristique)
            n = len(wallets_info)
            if n < 2:
                return jsonify({"ok": False, "error": "need at least 2 wallets for mixing"}), 400
            for i in range(n):
                src = wallets_info[i]
                dst = wallets_info[(i + 1) % n]
                if src["address"] == dst["address"]:
                    continue
                amount = max(0.0, src["balance"] * 0.5)  # heuristique
                # laisser un petit coussin pour frais (~0.00001 SOL)
                amount = max(0.0, amount - 0.00001)
                if amount <= 0:
                    continue
                kp = Keypair.from_base58_string(src["priv"])
                sig = _sign_and_send_transfer(client, kp, dst["address"], amount)
                history.append({
                    "from_wallet_id": src["wallet"].get("id") or src["wallet"].get("wallet_id"),
                    "from_address": src["address"],
                    "to_address": dst["address"],
                    "amount_sol": amount,
                    "signature": sig
                })
        else:
            # random: chaque source choisit une cible différente et envoie un montant aléatoire
            indices = list(range(len(wallets_info)))
            for i, src in enumerate(wallets_info):
                # choisir une cible != i
                choices = [j for j in indices if j != i]
                if not choices:
                    continue
                j = random.choice(choices)
                dst = wallets_info[j]
                if src["address"] == dst["address"]:
                    continue
                # montant aléatoire entre [0, balance - fee]
                max_amount = max(0.0, src["balance"] - 0.00001)
                if max_amount <= 0:
                    continue
                amount = round(random.uniform(0, max_amount), 9)
                if amount <= 0:
                    continue
                kp = Keypair.from_base58_string(src["priv"])
                sig = _sign_and_send_transfer(client, kp, dst["address"], amount)
                history.append({
                    "from_wallet_id": src["wallet"].get("id") or src["wallet"].get("wallet_id"),
                    "from_address": src["address"],
                    "to_address": dst["address"],
                    "amount_sol": amount,
                    "signature": sig
                })
    except Exception as e:
        return jsonify({"ok": False, "error": f"mix failed: {e}", "history": history}), 500

    return jsonify({
        "ok": True,
        "strategy": strategy,
        "rpc_url": rpc_url,
        "transfers": len(history),
        "history": history
    }), 200
@bp.post("/wallets/consolidate/<target_wallet_id>")
@require_api_key
def consolidate_to_target(target_wallet_id: str):
    """
    Envoie le solde de tous les wallets d'un même projet vers un wallet cible (par ID).
    JSON optionnel:
      {
        "project_id": "prj_xxx",  // recommandé pour borner le scope
        "min_reserve_sol": 0.00001 // laisser un coussin sur les sources pour frais
      }
    Règles:
      - On IGNORE tout wallet dont la pubkey == pubkey de la cible (self-send interdit).
      - On saute les wallets sans balance disponible (> reserve).
    """
    data = request.get_json(force=True, silent=True) or {}
    project_id_param = (data.get("project_id") or "").strip()
    min_reserve_sol = float(data.get("min_reserve_sol") or 0.00001)

    base = current_app.config["DATA_DIR"]
    found_target = _find_wallet_by_id(base, target_wallet_id)
    if not found_target:
        return jsonify({"ok": False, "error": f"target wallet '{target_wallet_id}' not found"}), 404
    target_pr, target_wallet, target_pdir = found_target
    target_addr = _get_wallet_pubkey_str(target_wallet)
    if not target_addr:
        return jsonify({"ok": False, "error": "target wallet missing address"}), 400

    # Si project_id fourni, on borne au projet demandé;
    # sinon on prend le projet du wallet cible (c'est le "projet courant" logique).
    if project_id_param:
        pdir = find_project_dir(base, project_id_param)
        if not pdir:
            return jsonify({"ok": False, "error": f"project '{project_id_param}' not found"}), 404
        pr = load_project(pdir)
    else:
        pr = target_pr
        pdir = target_pdir

    pd = pr.to_dict() or {}
    wallets = pd.get("wallets") or []

    client, rpc_url = _rpc_client_from_config()
    history = []
    skipped = []

    for w in wallets:
        wid = str(w.get("id") or w.get("wallet_id") or "")
        addr = _get_wallet_pubkey_str(w)
        priv = _get_wallet_privkey_b58(w)
        if not wid or not addr or not priv:
            skipped.append({"wallet_id": wid, "reason": "missing id/address/private_key"})
            continue
        # Règle: ne pas s'auto-envoyer si l'address correspond à la cible
        if addr == target_addr:
            skipped.append({"wallet_id": wid, "reason": "same pubkey as target (self-send skipped)"})
            continue

        bal = _get_balance_sol_solders(client, addr)
        amount = max(0.0, bal - min_reserve_sol)
        # aussi éviter en dessous d'un plancher pour esquiver les tx minuscules
        if amount <= 0:
            skipped.append({"wallet_id": wid, "reason": f"no available balance (balance={bal})"})
            continue

        try:
            kp = Keypair.from_base58_string(priv)
            sig = _sign_and_send_transfer(client, kp, target_addr, amount)
            history.append({
                "from_wallet_id": wid,
                "from_address": addr,
                "to_wallet_id": target_wallet_id,
                "to_address": target_addr,
                "amount_sol": amount,
                "signature": sig
            })
        except Exception as e:
            skipped.append({"wallet_id": wid, "reason": f"transfer failed: {e}"})

    return jsonify({
        "ok": True,
        "project_id": pr.project_id,
        "target_wallet_id": target_wallet_id,
        "target_address": target_addr,
        "rpc_url": rpc_url,
        "transfers": len(history),
        "history": history,
        "skipped": skipped
    }), 200

@bp.post("/wallets/<wallet_id>/transfer")
@require_api_key
def transfer_from_wallet_id(wallet_id: str):
    """
    Envoie des SOL depuis le wallet <wallet_id> (clé privée en base58 dans le projet)
    vers une adresse publique (Base58) passée en JSON.
    Body JSON attendu:
      {
        "recipient_pubkey": "DestPubKeyBase58",
        "amount_sol": 1.23
      }
    """
    payload = request.get_json(force=True, silent=True) or {}
    recipient = (payload.get("recipient_pubkey") or "").strip()
    try:
        amount_sol = float(payload.get("amount_sol"))
    except Exception:
        return jsonify({"ok": False, "error": "amount_sol must be a number"}), 400

    if not recipient:
        return jsonify({"ok": False, "error": "recipient_pubkey is required"}), 400
    if amount_sol <= 0:
        return jsonify({"ok": False, "error": "amount_sol must be > 0"}), 400

    base = current_app.config["DATA_DIR"]
    found = _find_wallet_by_id(base, wallet_id)
    if not found:
        return jsonify({"ok": False, "error": f"wallet '{wallet_id}' not found"}), 404
    pr, wallet, pdir = found

    sender_priv_b58 = _get_wallet_privkey_b58(wallet)
    sender_pub_b58 = _get_wallet_pubkey_str(wallet)
    if not sender_priv_b58 or not sender_pub_b58:
        return jsonify({"ok": False, "error": "wallet missing private key or address"}), 400

    # Client RPC
    client, rpc_url = _rpc_client_from_config()

    # Option de sécurité: interdire self-transfer (même pubkey)
    if sender_pub_b58 == recipient:
        return jsonify({"ok": False, "error": "sender and recipient are identical"}), 400

    try:
        sender_kp = Keypair.from_base58_string(sender_priv_b58)
        signature = _sign_and_send_transfer(client, sender_kp, recipient, amount_sol)
        return jsonify({
            "ok": True,
            "from_wallet_id": wallet_id,
            "from_address": sender_pub_b58,
            "to_address": recipient,
            "amount_sol": amount_sol,
            "signature": signature,
            "rpc_url": rpc_url
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@bp.post("/projects/<project_id>/wallets")
@require_api_key
def create_wallets(project_id: str):
    """ Génère N wallets pour un projet donné, persiste la nouvelle liste et renvoie les adresses créées. """
    data = request.get_json(force=True, silent=True) or {}
    try:
        n = int(data.get("n") or 1)
    except ValueError:
        return jsonify({"ok": False, "error": "n must be integer"}), 400
    if n <= 0 or n > 1000:
        return jsonify({"ok": False, "error": "n must be in 1..1000"}), 400
    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404
    pr = load_project(pdir)
    new_ws = generate_wallets(pr, n)
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "created": len(new_ws), "wallets": [w.address for w in new_ws]}), 201

@bp.get("/wallets/<address>/balance")
@require_api_key
def balance(address: str):
    """ Retourne le solde SOL d'une adresse donnée. Le cluster/RPC est résolu via `cluster` (query) ou `rpc` prioritaire. """
    default_rpc = current_app.config["DEFAULT_RPC"]
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (request.args.get("cluster") or env_cluster or "").strip()
    rpc_param = (request.args.get("rpc") or "").strip()
    rpc = resolve_rpc(default_rpc, cluster_param, rpc_param)
    try:
        sol = get_balance_sol(address, rpc_url=rpc)
        return jsonify({"ok": True, "address": address, "balance_sol": sol, "rpc_url": rpc, "cluster": cluster_param or env_cluster})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "rpc_url": rpc, "cluster": cluster_param or env_cluster}), 400


@bp.delete("/projects/<project_id>/wallets/<address>")
@require_api_key
def delete_wallet(project_id: str, address: str):
    """ Sauvegarde JSON (backup) du wallet (private/public) puis le retire de la liste du projet et persiste. """
    base = current_app.config["DATA_DIR"]
    backups_dir = Path(base) / "backups"
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)
    wallets = pr.to_dict().get("wallets") or []

    # Chercher le wallet
    idx = None
    for i, w in enumerate(wallets):
        if (w.get("address") or w.get("pubkey")) == address:
            idx = i
            break
    if idx is None:
        return jsonify({"ok": False, "error": "wallet not found"}), 404

    # Sauvegarde AVANT suppression
    try:
        ensure_dir(backups_dir / "wallets")
        backup_path = backup_wallet(pr.to_dict(), wallets[idx], Path(pdir), backups_dir)
    except Exception as e:
        return jsonify({"ok": False, "error": f"backup failed: {e}"}), 500

    # Suppression logique: retirer de la liste puis sauvegarder le projet
    try:
        wallets.pop(idx)
        # Réinjecter la liste modifiée dans l'objet pr (selon ton modèle)
        pr.wallets = wallets  # si attribut; sinon adapte à ton modèle
        save_project(pr, dossier_base=base)
    except Exception as e:
        return jsonify({"ok": False, "error": f"delete failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "deleted_wallet": address,
        "project_id": pr.project_id,
        "backup": str(backup_path),
    }), 200