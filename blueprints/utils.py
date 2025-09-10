# -*- coding: utf-8 -*-
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from config import resolve_rpc
from solana.rpc.api import Client
from solders.pubkey import Pubkey
import time

# Exceptions selon versions de solana-py
try:
    from solana.rpc.core import RPCException  # anciennes versions
except Exception:
    RPCException = Exception

try:
    from solana.exceptions import SolanaRpcException  # versions récentes
except Exception:
    SolanaRpcException = Exception

LAMPORTS_PER_SOL = 1_000_000_000

bp = Blueprint("utils", __name__, url_prefix="/api/v1")

def _is_rate_limited(msg: str | None, code: int | None) -> bool:
    m = (msg or "").lower()
    return ("rate" in m) or ("limit" in m) or (code == -32005)

def _extract_jsonrpc_error_from_exception(e: Exception):
    """
    Tente d'extraire (message, code, data) depuis e.args avec différents formats possibles.
    """
    msg, code, data = "", None, None
    try:
        if getattr(e, "args", None):
            raw = e.args[0]
            if isinstance(raw, dict):
                err = raw.get("error") or raw
                if isinstance(err, dict):
                    msg = (err.get("message") or "").strip() or msg
                    code = err.get("code", code)
                    data = err.get("data", data)
            if not msg:
                msg = str(raw)
    except Exception:
        msg = str(e) or e.__class__.__name__
    if not msg:
        msg = str(e) or e.__class__.__name__
    return msg, code, data

@bp.post("/airdrop")
@require_api_key
def airdrop():
    """
    Airdrop DEVNET avec retries + polling <= 60s max.

    Body JSON:
    {
      "address": "<pubkey>",                 # requis
      "sol": 0.2,                            # optionnel (défaut 1.0)
      "cluster": "devnet",                   # optionnel (priorité: rpc_url > cluster > DEFAULT_RPC)
      "rpc_url": "https://api.devnet.solana.com",  # optionnel

      "confirm_seconds": 60,                 # optionnel (0..60)
      "confirm_interval": 1,                 # optionnel (0.2..5)
      "retries": 3,                          # optionnel (0..10)
      "backoff_seconds": 1.5                 # optionnel (0.2..10) backoff exponentiel par tentative
    }

    Réponse OK (exemples):
    - a) Signature + delta observé dans la fenêtre:
      { ok:true, confirmation:"balance_delta", signature:"...", pre_balance:..., post_balance:..., delta_sol:..., attempts_poll:..., attempts_airdrop:..., waited_seconds:..., rpc_url:"...", cluster:"devnet" }

    - b) Signature obtenue mais pas de delta observé avant timeout:
      { ok:true, confirmation:"signature", signature:"...", ... }   (HTTP 201)

    - c) Pas de signature, pas de delta avant timeout:
      { ok:false, confirmation:"none", error:"pending confirmation...", ... }   (HTTP 202)
    """
    payload = request.get_json(force=True, silent=True) or {}

    # ---- Lecture paramètres ----
    addr = (payload.get("address") or "").strip()
    sol_amount = float(payload.get("sol") or 1.0)

    default_rpc = current_app.config["DEFAULT_RPC"]
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (payload.get("cluster") or env_cluster or "").strip().lower()
    rpc_param = (payload.get("rpc_url") or "").strip()
    rpc = resolve_rpc(default_rpc, cluster_param, rpc_param)

    # Fenêtre & retries (bornage)
    try:
        confirm_seconds = float(payload.get("confirm_seconds", 60))
    except Exception:
        confirm_seconds = 60.0
    confirm_seconds = max(0.0, min(confirm_seconds, 60.0))

    try:
        confirm_interval = float(payload.get("confirm_interval", 1))
    except Exception:
        confirm_interval = 1.0
    confirm_interval = max(0.2, min(confirm_interval, 5.0))

    try:
        retries = int(payload.get("retries", 3))
    except Exception:
        retries = 3
    retries = max(0, min(retries, 10))

    try:
        backoff = float(payload.get("backoff_seconds", 1.5))
    except Exception:
        backoff = 1.5
    backoff = max(0.2, min(backoff, 10.0))

    # ---- Devnet guard ----
    is_dev = (cluster_param == "devnet") or ("devnet" in rpc.lower())
    if not is_dev:
        return jsonify({"ok": False, "error": "airdrop allowed only on devnet", "rpc_url": rpc}), 400

    # ---- Adresse valide ? ----
    try:
        pk = Pubkey.from_string(addr)
    except Exception:
        return jsonify({"ok": False, "error": "invalid address", "rpc_url": rpc}), 400

    lamports = int(sol_amount * LAMPORTS_PER_SOL)
    client = Client(rpc)

    # Lire solde avant
    try:
        pre_balance_lamports = client.get_balance(pk).value
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"failed to read pre-balance: {str(e) or e.__class__.__name__}",
            "rpc_url": rpc
        }), 400

    signature_b58 = None
    attempts_airdrop = 0
    errors = []

    # ---- Planification du temps max ----
    start = time.monotonic()
    deadline = start + confirm_seconds

    # ---- Boucle de tentatives d'airdrop + polling ----
    # On effectue (retries + 1) tentatives maximum
    for attempt in range(retries + 1):
        attempts_airdrop += 1

        # Si pas de temps restant, on sort
        now = time.monotonic()
        if now >= deadline:
            break

        # 1) Tenter un airdrop
        try:
            res = client.request_airdrop(pk, lamports)

            # Succès immédiat ? (signature)
            sig = getattr(res, "value", None)
            if sig:
                signature_b58 = str(sig)

            else:
                # Échec sans exception -> extraire message/ code
                d = None
                try:
                    d = res.to_dict()
                except Exception:
                    pass

                msg = ""
                code = 400
                if isinstance(d, dict) and "error" in d and isinstance(d["error"], dict):
                    err = d["error"]
                    msg = (err.get("message") or "").strip()
                    code = int(err.get("code", 400))
                if not msg:
                    msg = "airdrop failed (no signature returned)"

                errors.append({"type": "JsonRpcError", "message": msg, "code": code, "rpc_response": d})

        except (RPCException, SolanaRpcException) as e:
            msg, code, data = _extract_jsonrpc_error_from_exception(e)
            errors.append({"type": e.__class__.__name__, "message": msg, "code": code, "data": data})

        except Exception as e:
            msg = str(e) or e.__class__.__name__
            errors.append({"type": e.__class__.__name__, "message": msg, "code": None, "data": None})

        # 2) Polling du solde jusqu’à expiration de la fenêtre
        attempts_poll = 0
        post_balance_lamports = pre_balance_lamports
        while time.monotonic() < deadline:
            attempts_poll += 1
            try:
                post_balance_lamports = client.get_balance(pk).value
            except Exception:
                # On ignore l'erreur ponctuelle de lecture
                pass

            delta = post_balance_lamports - pre_balance_lamports
            if delta >= lamports:
                waited = max(0.0, time.monotonic() - start)
                return jsonify({
                    "ok": True,
                    "signature": signature_b58,  # peut être None si jamais renvoyée
                    "confirmation": "balance_delta",
                    "pre_balance": pre_balance_lamports / LAMPORTS_PER_SOL,
                    "post_balance": post_balance_lamports / LAMPORTS_PER_SOL,
                    "delta_sol": delta / LAMPORTS_PER_SOL,
                    "attempts_poll": attempts_poll,
                    "attempts_airdrop": attempts_airdrop,
                    "waited_seconds": round(waited, 3),
                    "rpc_url": rpc,
                    "cluster": (cluster_param or env_cluster) or "devnet"
                }), 201

            # Si on a déjà une signature, on peut décider d'arrêter ici (retour "signature")
            # mais on préfère continuer jusqu'au timeout pour tenter d'observer le delta.
            time.sleep(min(confirm_interval, max(0.0, deadline - time.monotonic())))

        # 3) Si on arrive ici, la fenêtre est écoulée -> pas de delta observé.
        #    On décide si on retente un airdrop (si du temps reste) avec backoff.
        #    Note: deadline atteint, donc plus de temps: on sort.
        if time.monotonic() >= deadline:
            break

        # Sinon, appliquer un backoff avant la prochaine tentative d'airdrop
        last_err = errors[-1] if errors else {}
        msg = last_err.get("message")
        code = last_err.get("code")
        # Si rate-limit détecté, on backoff (déjà prévu), sinon on backoff quand même légèrement.
        sleep_s = min(backoff * (1.6 ** attempt), max(0.0, deadline - time.monotonic()))
        if sleep_s > 0:
            time.sleep(sleep_s)

    # ---- Fin : pas de delta observé dans la fenêtre ----
    post_balance_lamports = client.get_balance(pk).value
    waited = max(0.0, time.monotonic() - start)
    delta = post_balance_lamports - pre_balance_lamports

    if signature_b58:
        # On a une signature, mais pas (encore) de delta observé dans la fenêtre
        return jsonify({
            "ok": True,
            "signature": signature_b58,
            "confirmation": "signature",
            "pre_balance": pre_balance_lamports / LAMPORTS_PER_SOL,
            "post_balance": post_balance_lamports / LAMPORTS_PER_SOL,
            "delta_sol": delta / LAMPORTS_PER_SOL,
            "attempts_airdrop": attempts_airdrop,
            "waited_seconds": round(waited, 3),
            "rpc_url": rpc,
            "cluster": (cluster_param or env_cluster) or "devnet",
            "notes": "Signature reçue mais crédit non observé dans la fenêtre allouée."
        }), 201

    # Pas de signature et pas de delta -> pending
    # S'il y a des erreurs collectées, on remonte la dernière (ou on agrège).
    status = 202
    error_payload = {
        "ok": False,
        "error": "pending confirmation (no signature, no balance delta within window)",
        "confirmation": "none",
        "pre_balance": pre_balance_lamports / LAMPORTS_PER_SOL,
        "post_balance": post_balance_lamports / LAMPORTS_PER_SOL,
        "delta_sol": delta / LAMPORTS_PER_SOL,
        "attempts_airdrop": attempts_airdrop,
        "waited_seconds": round(waited, 3),
        "rpc_url": rpc,
        "cluster": (cluster_param or env_cluster) or "devnet"
    }
    if errors:
        error_payload["errors"] = errors
        # Si clairement rate-limit dans le dernier message -> 429
        last = errors[-1]
        if _is_rate_limited(last.get("message"), last.get("code")):
            status = 429
            error_payload["hint"] = "Faucet rate-limited. Réduis le montant, attends un peu, ou change d'adresse."

    return jsonify(error_payload), status
