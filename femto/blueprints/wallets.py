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
from api_utils import find_project_dir, iter_project_dirs
from config import resolve_rpc
from services.backups import backup_wallet
from services.fileio import ensure_dir
from rug.src.project_service import load_project, save_project, generate_wallets
from rug.src.wallet_service import get_balance_sol, get_wallet_token_holdings
# Ajouts pour les transactions Solana (solders)

from solana.rpc.api import Client as RpcClient     # ✅ bon client RPC

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer as sp_transfer, TransferParams
from solders.message import Message
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
    """Utilise la fonction officielle iter_project_dirs."""
    return [Path(d) for d in iter_project_dirs(base_dir)]


def _find_wallet_by_id(base_dir: str, wallet_id: str, project_id: Optional[str] = None) -> Optional[Tuple[Any, Dict[str, Any], Path]]:
    """
    🔒 SÉCURISÉ - Scan de tous les projets en DATA_DIR pour trouver un wallet par ID exact ou address complète.
    ⚠️ PLUS de correspondance par 8 chars pour éviter les collisions de sécurité.
    Retour: (project_obj, wallet_dict, project_dir) | None
    """
    for pdir in _list_project_dirs(base_dir):
        try:
            pr = load_project(pdir)
            pd = pr.to_dict() or {}
            
            # Si project_id fourni, filtrer par projet
            if project_id and pd.get("project_id") != project_id:
                continue
                
            wallets = pd.get("wallets") or []
            for w in wallets:
                # Résolution SÉCURISÉE: UNIQUEMENT id exact ou address complète
                wid = str(w.get("id") or w.get("wallet_id") or "")
                addr = str(w.get("address") or w.get("pubkey") or "")
                
                # 🔒 SÉCURITÉ: Correspondances EXACTES seulement - pas de substring
                if (wid and wid == str(wallet_id)) or (addr and addr == str(wallet_id)):
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

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client as RpcClient
from rug.src.tx import send_sol

def _sign_and_send_transfer(client: RpcClient, sender_kp: Keypair, recipient_b58: str, amount_sol: float) -> str:
    """
    Transfert SOL en utilisant la fonction send_sol qui fonctionne correctement.
    """
    # Convertir le keypair au format bytes array (ce que _keypair_from_any accepte)
    sender_priv_bytes = list(bytes(sender_kp))
    
    # Appeler la fonction send_sol qui fonctionne
    sig = send_sol(
        debtor_private_key=sender_priv_bytes,
        recipient_pubkey_b58=recipient_b58,
        amount_sol=amount_sol,
        rpc_url=client._provider.endpoint_uri
    )
    
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
    """ Génère N wallets pour un projet donné, persiste la nouvelle liste et renvoie la structure complète. """
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
    
    # Import de la fonction de formatage depuis projects
    # Créer la structure de wallet avec clés privées masquées
    def _mask_private_key(private_key: str) -> str:
        """Masque une clé privée en gardant les premiers/derniers caractères."""
        if not private_key or len(private_key) < 10:
            return "***masked***"
        return f"{private_key[:6]}***...***{private_key[-4:]}"
    
    formatted_wallets = []
    for w in new_ws:
        # Récupérer les attributs du wallet
        wallet_id = getattr(w, "id", None) or getattr(w, "wallet_id", None)
        wallet_name = getattr(w, "name", None)
        wallet_address = getattr(w, "address", None)
        created_at = getattr(w, "created_at", None)
        private_key = getattr(w, "private_key", None) or getattr(w, "secret", None)
        
        # Formater le wallet avec clé masquée
        formatted_wallet = {
            "id": wallet_id,
            "name": wallet_name,
            "address": wallet_address,
            "created_at": created_at,
            "balance_sol": 0,  # Sera calculé si nécessaire
            "private_key_masked": _mask_private_key(private_key) if private_key else "***no_key***"
        }
        
        # Ajouter le solde si possible
        if wallet_address:
            try:
                client, rpc_url = _rpc_client_from_config()
                formatted_wallet["balance_sol"] = get_balance_sol(wallet_address, rpc_url=rpc_url)
            except:
                formatted_wallet["balance_sol"] = 0
        
        formatted_wallets.append(formatted_wallet)
    
    return jsonify({
        "ok": True, 
        "created": len(new_ws), 
        "wallets": formatted_wallets
    }), 201

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


@bp.get("/wallets/<wallet_id>/details")
@require_api_key
def wallet_details(wallet_id: str):
    """
    🔓 ENDPOINT SÉCURISÉ - Récupère les détails COMPLETS d'un wallet incluant la clé privée.
    Utiliser avec précaution - expose la clé privée en clair !
    """
    base = current_app.config["DATA_DIR"]
    project_id = request.args.get("project_id")  # Optionnel pour filtrer
    
    # Trouver le wallet par son ID
    result = _find_wallet_by_id(base, wallet_id, project_id)
    if not result:
        return jsonify({"ok": False, "error": "wallet not found"}), 404
    
    project, wallet, project_dir = result
    
    # Import de la fonction de formatage depuis projects
    # Import direct de la fonction (copier localement pour éviter circular imports)
    
    # Résoudre RPC pour le solde
    client, rpc_url = _rpc_client_from_config()
    
    # Formater le wallet AVEC clé privée (show_private=True)
    wallet_details = _ensure_wallet_render(
        wallet, 
        include_balance=True, 
        rpc_url=rpc_url,
        show_private=True  # 🔓 CLÉ PRIVÉE VISIBLE
    )
    
    return jsonify({
        "ok": True,
        "wallet": wallet_details,
        "project_id": project.project_id,
        "rpc_url": rpc_url
    })

@bp.get("/wallets/<wallet_id>/tokens")
@require_api_key
def wallet_token_holdings(wallet_id: str):
    """
    💰 Récupère tous les holdings SPL tokens d'un wallet.
    Retourne la liste des tokens avec balances, métadonnées et valeurs USD.
    """
    base = current_app.config["DATA_DIR"]
    
    # Trouver le wallet par son ID ou address
    result = _find_wallet_by_id(base, wallet_id)
    if not result:
        return jsonify({"ok": False, "error": "wallet not found"}), 404
    
    project, wallet, project_dir = result
    wallet_address = _get_wallet_pubkey_str(wallet)
    
    if not wallet_address:
        return jsonify({"ok": False, "error": "wallet address not found"}), 400
    
    # Résoudre RPC
    client, rpc_url = _rpc_client_from_config()
    
    try:
        # Récupérer les holdings SPL tokens
        holdings = get_wallet_token_holdings(wallet_address, rpc_url)
        
        # Ajouter les informations SOL également
        sol_balance = _get_balance_sol_solders(client, wallet_address)
        
        # Calculer la valeur totale des holdings
        total_value_usd = 0.0
        token_count = len(holdings)
        
        for holding in holdings:
            if holding.get("value_usd"):
                total_value_usd += holding["value_usd"]
        
        return jsonify({
            "ok": True,
            "wallet_id": wallet_id,
            "wallet_address": wallet_address,
            "project_id": project.project_id,
            "sol_balance": sol_balance,
            "token_count": token_count,
            "total_value_usd": total_value_usd if total_value_usd > 0 else None,
            "tokens": holdings,
            "rpc_url": rpc_url
        })
        
    except Exception as e:
        return jsonify({
            "ok": False, 
            "error": f"Failed to fetch token holdings: {str(e)}",
            "wallet_address": wallet_address,
            "rpc_url": rpc_url
        }), 500


@bp.post("/wallets/<wallet_id>/transfer-token")
@require_api_key
def transfer_spl_token(wallet_id: str):
    """
    🔄 Transfert de tokens SPL depuis un wallet vers un autre.
    Critical pour redistribuer les memecoins créés.
    """
    data = request.get_json(force=True, silent=True) or {}
    
    recipient = data.get("recipient")
    token_address = data.get("token_address")
    amount = data.get("amount")
    
    if not recipient:
        return jsonify({"ok": False, "error": "recipient address required"}), 400
    if not token_address:
        return jsonify({"ok": False, "error": "token_address required"}), 400
    if not amount or amount <= 0:
        return jsonify({"ok": False, "error": "amount must be > 0"}), 400
    
    base = current_app.config["DATA_DIR"]
    
    # Trouver le wallet source
    result = _find_wallet_by_id(base, wallet_id)
    if not result:
        return jsonify({"ok": False, "error": "wallet not found"}), 404
    
    project, wallet, project_dir = result
    wallet_address = _get_wallet_pubkey_str(wallet)
    private_key = _get_wallet_privkey_b58(wallet)
    
    if not wallet_address or not private_key:
        return jsonify({"ok": False, "error": "wallet keys not found"}), 400
    
    client, rpc_url = _rpc_client_from_config()
    
    try:
        # 🔥 IMPLÉMENTATION COMPLÈTE SPL TOKEN TRANSFER avec gestion ATA
        from solders.keypair import Keypair
        from solders.pubkey import Pubkey
        from solders.transaction import Transaction
        from solders.message import Message
        from solders.instruction import Instruction, AccountMeta
        from spl.token.constants import TOKEN_PROGRAM_ID, ASSOCIATED_TOKEN_PROGRAM_ID
        from solana.rpc.commitment import Confirmed
        import time
        
        # Parse addresses
        sender_pubkey = Pubkey.from_string(wallet_address)
        recipient_pubkey = Pubkey.from_string(recipient)
        token_mint = Pubkey.from_string(token_address)
        sender_keypair = Keypair.from_base58_string(private_key)
        
        # Récupérer les métadonnées du token pour les décimales
        from rug.src.wallet_service import get_token_metadata
        token_metadata = get_token_metadata(token_address, rpc_url)
        decimals = token_metadata.get("decimals", 9)
        
        # Convertir le montant en unités atomiques
        amount_atomic = int(float(amount) * (10 ** decimals))
        
        # Calculer les ATA addresses
        def get_ata_address(owner: Pubkey, mint: Pubkey) -> Pubkey:
            """Calcule l'adresse ATA pour owner + mint"""
            from spl.token.instructions import get_associated_token_address
            return get_associated_token_address(owner, mint)
        
        sender_ata = get_ata_address(sender_pubkey, token_mint)
        recipient_ata = get_ata_address(recipient_pubkey, token_mint)
        
        # Vérifier si les ATA existent
        def account_exists(address: Pubkey) -> bool:
            try:
                resp = client.get_account_info(address, commitment=Confirmed)
                return resp.value is not None
            except:
                return False
        
        instructions = []
        
        # Créer ATA destinataire si n'existe pas
        if not account_exists(recipient_ata):
            from spl.token.instructions import create_associated_token_account
            create_ata_ix = create_associated_token_account(
                payer=sender_pubkey,
                owner=recipient_pubkey,
                mint=token_mint
            )
            instructions.append(create_ata_ix)
        
        # Instruction de transfert SPL
        from spl.token.instructions import transfer_checked, TransferCheckedParams
        transfer_ix = transfer_checked(
            TransferCheckedParams(
                program_id=TOKEN_PROGRAM_ID,
                source=sender_ata,
                mint=token_mint,
                dest=recipient_ata,
                owner=sender_pubkey,
                amount=amount_atomic,
                decimals=decimals
            )
        )
        instructions.append(transfer_ix)
        
        # Construire et envoyer la transaction
        recent_blockhash = client.get_latest_blockhash(commitment=Confirmed).value.blockhash
        message = Message.new_with_blockhash(instructions, sender_pubkey, recent_blockhash)
        transaction = Transaction.new_unsigned(message)
        transaction.sign([sender_keypair], recent_blockhash)
        
        # Envoyer la transaction
        result = client.send_transaction(transaction, opts={"skip_confirmation": False, "preflight_commitment": Confirmed})
        tx_signature = str(result.value)
        
        return jsonify({
            "ok": True,
            "transfer": {
                "wallet_id": wallet_id,
                "from_address": wallet_address,
                "from_ata": str(sender_ata),
                "to_address": recipient,
                "to_ata": str(recipient_ata),
                "token_address": token_address,
                "amount": amount,
                "amount_atomic": amount_atomic,
                "decimals": decimals,
                "transaction_signature": tx_signature,
                "timestamp": time.time(),
                "status": "confirmed"
            },
            "rpc_url": rpc_url
        })
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Transfer failed: {str(e)}",
            "from_address": wallet_address,
            "to_address": recipient,
            "token_address": token_address
        }), 500