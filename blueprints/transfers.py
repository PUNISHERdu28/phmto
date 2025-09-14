
# -*- coding: utf-8 -*-
from decimal import Decimal
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from config import resolve_rpc
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from rug.src.tx import send_sol, LAMPORTS_PER_SOL

bp = Blueprint("transfers", __name__, url_prefix="/api/v1")

@bp.post("/transfer/sol")
@require_api_key
def transfer_sol():
    """ Envoie des SOL depuis une clé privée vers une pubkey, avec sélection de cluster/RPC prioritaire sur `rpc_url` puis `cluster`. Renvoie la signature. """
    payload = request.get_json(force=True, silent=True) or {}
    sender_priv = payload.get("sender_private_key")
    recipient = (payload.get("recipient_pubkey_b58") or "").strip()
    amount_sol = payload.get("amount_sol")
    default_rpc = current_app.config["DEFAULT_RPC"]
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (payload.get("cluster") or env_cluster or "").strip()
    rpc_param = (payload.get("rpc_url") or "").strip()
    rpc = resolve_rpc(default_rpc, cluster_param, rpc_param)
    if not sender_priv or not recipient or amount_sol is None:
        return jsonify({"ok": False, "error": "sender_private_key, recipient_pubkey_b58, amount_sol required"}), 400
    try:
        amt = Decimal(str(amount_sol))
        if amt <= 0:
            raise ValueError("amount_sol must be > 0")
        Pubkey.from_string(recipient)
    except Exception as e:
        return jsonify({"ok": False, "error": f"invalid amount or recipient: {e}"}), 400
    try:
        kp = None
        if isinstance(sender_priv, list):
            kp = Keypair.from_bytes(bytes(sender_priv))
        elif isinstance(sender_priv, str):
            import base58 as _b58
            b = _b58.b58decode(sender_priv)
            kp = Keypair.from_bytes(b)
        else:
            return jsonify({"ok": False, "error": "sender_private_key must be base58 string or [64,int] list"}), 400
        client = Client(rpc)
        bal_lamports = client.get_balance(kp.pubkey()).value
        fee_reserved = 50_000
        amt_lamports = int(amt * LAMPORTS_PER_SOL)
        if amt_lamports + fee_reserved > bal_lamports:
            return jsonify({"ok": False, "error": "insufficient funds for amount + fee reserve"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"precheck failed: {e}", "rpc_url": rpc, "cluster": cluster_param or env_cluster}), 400
    try:
        sig = send_sol(
            debtor_private_key=sender_priv,
            recipient_pubkey_b58=recipient,
            amount_sol=float(amt),
            rpc_url=rpc
        )
        return jsonify({"ok": True, "signature": sig, "rpc_url": rpc, "cluster": cluster_param or env_cluster})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "rpc_url": rpc, "cluster": cluster_param or env_cluster}), 400



# =====================
# V3.1 — Nouveaux endpoints de gestion de transferts par wallet_id
# =====================

from pathlib import Path
from api_utils import iter_project_dirs, find_project_dir
from rug.src.project_service import load_project, save_project

def _derive_wallet_id(addr: str) -> str:
    """
    Dérive un identifiant court et stable à partir d'une adresse publique.
    Ici: 8 premiers caractères de l'adresse (suffit pour usage humain).
    """
    return (addr or "")[:8]

def _find_wallet_by_id_any(base_dir: str, wallet_id: str):
    """
    Recherche un wallet par:
      - champ 'id' si présent
      - adresse exacte
      - id dérivé (_derive_wallet_id)
    Retourne (project, wallet, project_dir) ou None.
    """
    for pdir in iter_project_dirs(base_dir):
        pr = load_project(pdir)
        pd = pr.to_dict() or {}
        for w in (pd.get("wallets") or []):
            addr = w.get("address") or w.get("pubkey")
            wid = w.get("id") or w.get("wallet_id") or _derive_wallet_id(addr or "")
            if str(wid) == str(wallet_id) or addr == wallet_id:
                return pr, w, pdir
    return None

@bp.post("/wallets/<wallet_id>/transfer")
@require_api_key
def transfer_from_wallet_id(wallet_id: str):
    """
    Envoie des SOL depuis un wallet (sélectionné par ID dérivé ou address) vers une pubkey.
    Body JSON:
      { "recipient_pubkey": "...", "amount_sol": 0.1, "rpc": "<optionnel>" }
    """
    data = request.get_json(force=True, silent=True) or {}
    recipient = (data.get("recipient_pubkey") or "").strip()
    amt = data.get("amount_sol")
    try:
        amt = float(amt)
        if amt <= 0:
            raise ValueError
        Pubkey.from_string(recipient)
    except Exception:
        return jsonify({"ok": False, "error": "amount_sol>0 & recipient_pubkey (base58) requis"}), 400

    base = current_app.config["DATA_DIR"]
    found = _find_wallet_by_id_any(base, wallet_id)
    if not found:
        return jsonify({"ok": False, "error": f"wallet '{wallet_id}' not found"}), 404
    pr, w, pdir = found

    sender_priv = w.get("private_key_base58_64") or w.get("private_key") or w.get("secret")
    sender_addr = w.get("address") or w.get("pubkey")
    if not sender_priv or not sender_addr:
        return jsonify({"ok": False, "error": "wallet missing private key or address"}), 400
    if sender_addr == recipient:
        return jsonify({"ok": False, "error": "sender and recipient are identical"}), 400

    client = Client(resolve_rpc(
        current_app.config["DEFAULT_RPC"],
        (request.args.get("cluster") or current_app.config.get("CLUSTER") or ""),
        (request.args.get("rpc") or data.get("rpc") or ""),
    ))
    # Construire Keypair à partir du base58 (ou array)
    try:
        if isinstance(sender_priv, list):
            kp = Keypair.from_bytes(bytes(sender_priv))
        else:
            import base58 as _b58
            kp = Keypair.from_bytes(_b58.b58decode(sender_priv))
        sig = send_sol(client, kp, recipient, Decimal(str(amt)))
        return jsonify({
            "ok": True,
            "from_wallet_id": wallet_id,
            "from_address": sender_addr,
            "to_address": recipient,
            "amount_sol": float(amt),
            "signature": sig,
            "rpc_url": client._provider.endpoint_uri
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"transfer failed: {e}"}), 500

@bp.post("/wallets/mix")
@require_api_key
def mix_wallets():
    """
    Mélange des SOL entre plusieurs wallets.
    Body JSON:
      { "wallet_ids": ["w1","w2","w3"], "strategy": "random"|"roundrobin" }
    Réponse: historique détaillé des transferts.
    """
    data = request.get_json(force=True, silent=True) or {}
    wallet_ids = data.get("wallet_ids") or []
    strategy = (data.get("strategy") or "random").lower().strip()
    if not wallet_ids or not isinstance(wallet_ids, list):
        return jsonify({"ok": False, "error": "wallet_ids required"}), 400
    if strategy not in ("random","roundrobin"):
        return jsonify({"ok": False, "error": "strategy must be random|roundrobin"}), 400

    base = current_app.config["DATA_DIR"]
    # Résolution wallets
    resolved = []
    for wid in wallet_ids:
        f = _find_wallet_by_id_any(base, str(wid))
        if not f:
            return jsonify({"ok": False, "error": f"wallet '{wid}' not found"}), 404
        resolved.append(f)

    client = Client(resolve_rpc(
        current_app.config["DEFAULT_RPC"],
        (request.args.get("cluster") or current_app.config.get("CLUSTER") or ""),
        (request.args.get("rpc") or data.get("rpc") or ""),
    ))

    # Préparer balances
    entries = []
    for pr, w, pdir in resolved:
        addr = w.get("address") or w.get("pubkey")
        priv = w.get("private_key_base58_64") or w.get("private_key") or w.get("secret")
        if not addr or not priv:
            return jsonify({"ok": False, "error": "wallet missing key/address"}), 400
        bal = client.get_balance(Pubkey.from_string(addr)).value / LAMPORTS_PER_SOL
        entries.append({"pr": pr, "w": w, "addr": addr, "priv": priv, "bal": bal})

    history = []
    try:
        if strategy == "roundrobin":
            n = len(entries)
            if n < 2:
                return jsonify({"ok": False, "error": "need >=2 wallets"}), 400
            for i in range(n):
                src = entries[i]; dst = entries[(i+1)%n]
                if src["addr"] == dst["addr"]:
                    continue
                amount = max(0.0, (src["bal"] * 0.5) - 0.00001)
                if amount <= 0:
                    continue
                kp = Keypair.from_bytes(__import__("base58").b58decode(src["priv"]) if isinstance(src["priv"], str) else bytes(src["priv"]))
                sig = send_sol(client, kp, dst["addr"], Decimal(str(amount)))
                history.append({"from_wallet_id": _derive_wallet_id(src["addr"]), "from_address": src["addr"], "to_address": dst["addr"], "amount_sol": amount, "signature": sig})
        else:
            import random
            idxs = list(range(len(entries)))
            for i, src in enumerate(entries):
                choices = [j for j in idxs if j != i]
                if not choices:
                    continue
                j = random.choice(choices); dst = entries[j]
                if src["addr"] == dst["addr"]:
                    continue
                max_amount = max(0.0, src["bal"] - 0.00001)
                if max_amount <= 0:
                    continue
                amount = round(random.uniform(0, max_amount), 9)
                if amount <= 0:
                    continue
                kp = Keypair.from_bytes(__import__("base58").b58decode(src["priv"]) if isinstance(src["priv"], str) else bytes(src["priv"]))
                sig = send_sol(client, kp, dst["addr"], Decimal(str(amount)))
                history.append({"from_wallet_id": _derive_wallet_id(src["addr"]), "from_address": src["addr"], "to_address": dst["addr"], "amount_sol": amount, "signature": sig})
    except Exception as e:
        return jsonify({"ok": False, "error": f"mix failed: {e}", "history": history}), 500

    return jsonify({"ok": True, "strategy": strategy, "rpc_url": client._provider.endpoint_uri, "transfers": len(history), "history": history})

@bp.post("/wallets/consolidate/<target_wallet_id>")
@require_api_key
def consolidate(target_wallet_id: str):
    """
    Consolide les SOL de tous les wallets du même projet que la cible vers celle-ci.
    Body JSON optionnel:
      { "project_id": "...", "min_reserve_sol": 0.00001 }
    Règle: ne JAMAIS s'auto-envoyer si addr == addr cible (skip).
    """
    data = request.get_json(force=True, silent=True) or {}
    project_id = (data.get("project_id") or "").strip()
    min_reserve_sol = float(data.get("min_reserve_sol") or 0.00001)

    base = current_app.config["DATA_DIR"]
    ftarget = _find_wallet_by_id_any(base, target_wallet_id)
    if not ftarget:
        return jsonify({"ok": False, "error": f"target wallet '{target_wallet_id}' not found"}), 404
    target_pr, target_w, target_pdir = ftarget
    target_addr = target_w.get("address") or target_w.get("pubkey")
    if not target_addr:
        return jsonify({"ok": False, "error": "target missing address"}), 400

    # Déterminer le projet à considérer
    if project_id:
        pdir = find_project_dir(base, project_id)
        if not pdir:
            return jsonify({"ok": False, "error": f"project '{project_id}' not found"}), 404
        pr = load_project(pdir)
    else:
        pr = target_pr
        pdir = target_pdir

    pd = pr.to_dict() or {}
    wallets = pd.get("wallets") or []

    client = Client(resolve_rpc(
        current_app.config["DEFAULT_RPC"],
        (request.args.get("cluster") or current_app.config.get("CLUSTER") or ""),
        (request.args.get("rpc") or data.get("rpc") or ""),
    ))

    history, skipped = [], []
    for w in wallets:
        addr = w.get("address") or w.get("pubkey")
        priv = w.get("private_key_base58_64") or w.get("private_key") or w.get("secret")
        wid = w.get("id") or w.get("wallet_id") or _derive_wallet_id(addr or "")
        if not addr or not priv:
            skipped.append({"wallet_id": wid, "reason": "missing key/address"}); continue
        if addr == target_addr:
            skipped.append({"wallet_id": wid, "reason": "same pubkey as target (self-send skipped)"}); continue
        bal = client.get_balance(Pubkey.from_string(addr)).value / LAMPORTS_PER_SOL
        amount = max(0.0, bal - min_reserve_sol)
        if amount <= 0:
            skipped.append({"wallet_id": wid, "reason": f"no available balance (balance={bal})"}); continue
        try:
            kp = Keypair.from_bytes(__import__("base58").b58decode(priv) if isinstance(priv, str) else bytes(priv))
            sig = send_sol(client, kp, target_addr, Decimal(str(amount)))
            history.append({"from_wallet_id": wid, "from_address": addr, "to_wallet_id": target_wallet_id, "to_address": target_addr, "amount_sol": amount, "signature": sig})
        except Exception as e:
            skipped.append({"wallet_id": wid, "reason": f"transfer failed: {e}"})

    return jsonify({"ok": True, "project_id": pr.project_id, "target_wallet_id": target_wallet_id, "target_address": target_addr, "rpc_url": client._provider.endpoint_uri, "transfers": len(history), "history": history, "skipped": skipped})
