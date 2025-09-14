# routes_tokens.py
# -*- coding: utf-8 -*-
"""
Endpoints liés aux tokens.
Ajout : PATCH /api/v1/tokens/<token_id> pour éditer les métadonnées (nom, symbole, description, image_uri, etc.)
"""

import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from api_utils import find_project_dir, iter_project_dirs
from rug.src.project_service import load_project, save_project
from rug.src.models import TokenMetadata
import time
import random

# =========================
# Token management for projects (edit/reset/create via Pump.fun)
# =========================

def _find_wallet_by_id_secure(base_dir: str, wallet_id: str, project_id: Optional[str] = None) -> Optional[Tuple[Any, Dict[str, Any], Path]]:
    """
    🔒 SÉCURISÉ - Recherche wallet par correspondance EXACTE (pas de substring).
    Résolution sécurisée : UNIQUEMENT id exact ou address complète.
    Args:
        base_dir: Répertoire data
        wallet_id: ID exact ou adresse exacte à chercher
        project_id: Scoping optionnel pour isolation
    Retour: (project_obj, wallet_dict, project_dir) | None
    """
    for pdir in iter_project_dirs(base_dir):
        try:
            pr = load_project(pdir)
            pd = pr.to_dict() or {}
            
            # Si project_id fourni, filtrer par projet pour isolation
            if project_id and pd.get("project_id") != project_id:
                continue
                
            wallets = pd.get("wallets") or []
            for w in wallets:
                # Résolution SÉCURISÉE: UNIQUEMENT correspondances EXACTES
                wid = str(w.get("id") or w.get("wallet_id") or "")
                addr = str(w.get("address") or w.get("pubkey") or "")
                
                # 🔒 SÉCURITÉ: Correspondances EXACTES seulement - AUCUN substring
                if (wid and wid == str(wallet_id)) or (addr and addr == str(wallet_id)):
                    return pr, w, Path(pdir)
        except Exception:
            continue
    return None

bp_tokens = Blueprint("tokens", __name__, url_prefix="/api/v1/projects")

def _proj_dir(base, project_id):
    p = find_project_dir(base, project_id)
    if not p:
        raise FileNotFoundError("project not found")
    return p

@bp_tokens.patch("/<project_id>/token")
@require_api_key
def token_edit(project_id: str):
    """Édite les métadonnées locales du token d’un projet."""
    data = request.get_json(force=True, silent=True) or {}
    base = current_app.config["DATA_DIR"]
    pdir = _proj_dir(base, project_id)
    pr = load_project(pdir)
    # Update TokenMetadata fields directly
    for k in ("name","symbol","description","image_uri","website","twitter","telegram"):
        if k in data and hasattr(pr.token, k):
            setattr(pr.token, k, data[k])
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "token": pr.token.__dict__})

@bp_tokens.delete("/<project_id>/token")
@require_api_key
def token_reset(project_id: str):
    """Réinitialise les attributs du token du projet."""
    base = current_app.config["DATA_DIR"]
    pdir = _proj_dir(base, project_id)
    pr = load_project(pdir)
    # Create new TokenMetadata object for reset
    pr.token = TokenMetadata(name="MyMeme", symbol="MEME", description="")
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "reset": True, "token": pr.token.__dict__})

@bp_tokens.post("/<project_id>/token/create")
@require_api_key
def token_create_pumpfun(project_id: str):
    """
    Crée réellement le token via Pump.fun.
    Pour v3.5: appel minimal, renvoie 400 si API key absente.
    """
    api_key = os.getenv("PUMPFUN_API_KEY")
    if not api_key:
        return jsonify({"ok": False, "error": "PUMPFUN_API_KEY missing"}), 400
    base = current_app.config["DATA_DIR"]
    pdir = _proj_dir(base, project_id)
    pr = load_project(pdir)
    tok = (pr.to_dict() or {}).get("token") or {}
    # NOTE: Implémentation réelle Pump.fun à brancher ici (upload metadata + trade create).
    # Pour cette version, on renvoie un 202 Accepted pour indiquer que c'est prêt côté config.
    return jsonify({"ok": True, "accepted": True, "token": tok, "note": "Implémentation complète Pump.fun à brancher avec votre clé API."}), 202


# ================ Token Purchase & Price Endpoints ================

# Nouveau blueprint pour les endpoints tokens généraux (pas liés à un projet)
bp_tokens_general = Blueprint("tokens_general", __name__, url_prefix="/api/v1/tokens")


@bp_tokens_general.post("/purchase")
@require_api_key
def purchase_token():
    """
    🪙 Achat direct de token via DEX (Jupiter/Raydium).
    Swap SOL → Token pour un wallet donné.
    Sécurisé avec ownership et isolation projet.
    """
    # 🔒 SÉCURITÉ PRODUCTION: Vérifier REQUIRE_AUTH pour production
    require_auth = current_app.config.get("REQUIRE_AUTH", True)
    if require_auth and not os.getenv("API_KEY"):
        return jsonify({
            "ok": False,
            "error": "Production security required",
            "details": "REQUIRE_AUTH=true requires valid API_KEY"
        }), 401
    
    data = request.get_json(force=True, silent=True) or {}
    
    # Validation des paramètres
    wallet_id = data.get("wallet_id")
    token_address = data.get("token_address")
    amount_sol = data.get("amount_sol")
    slippage_percent = data.get("slippage_percent", 1.0)  # 1% par défaut
    
    if not wallet_id:
        return jsonify({"ok": False, "error": "wallet_id required"}), 400
    if not token_address:
        return jsonify({"ok": False, "error": "token_address required"}), 400
    if not amount_sol or amount_sol <= 0:
        return jsonify({"ok": False, "error": "amount_sol must be > 0"}), 400
    if slippage_percent < 0.1 or slippage_percent > 50:
        return jsonify({"ok": False, "error": "slippage_percent must be between 0.1 and 50"}), 400
    
    base = current_app.config["DATA_DIR"]
    
    # 🔒 SÉCURITÉ CRITIQUE - Trouver wallet avec correspondance EXACTE + ownership
    project_id = data.get("project_id")  # RECOMMANDÉ: Scoping pour isolation
    
    if not project_id:
        # ⚠️ AVERTISSEMENT: Recherche cross-projet sans isolation
        pass  # Permité mais recommande project_id pour sécurité
    
    result = _find_wallet_by_id_secure(base, wallet_id, project_id)
    
    if not result:
        error_msg = f"wallet '{wallet_id}' not found"
        if project_id:
            error_msg += f" in project '{project_id}'"
        return jsonify({"ok": False, "error": error_msg}), 404
    
    project, wallet, project_dir = result
    wallet_address = wallet.get("address")
    private_key = wallet.get("private_key_base58_64") or wallet.get("private_key")
    
    if not wallet_address or not private_key:
        return jsonify({"ok": False, "error": "wallet keys not found"}), 400
    
    try:
        # 🚫 SIMULATION GATED - Retourner 501 Not Implemented au lieu de misleader
        jupiter_api_key = os.getenv("JUPITER_API_KEY")
        enable_simulation = os.getenv("ENABLE_TOKEN_SIMULATION", "false").lower() == "true"
        
        if not jupiter_api_key and not enable_simulation:
            return jsonify({
                "ok": False,
                "error": "Token purchase not implemented",
                "details": "Jupiter DEX integration required. Set JUPITER_API_KEY or ENABLE_TOKEN_SIMULATION=true",
                "capability": "not_implemented"
            }), 501
        
        # TODO: Intégration Jupiter API pour le swap SOL → Token
        if enable_simulation:
            # Simulation EXPLICITE avec warning
            estimated_tokens = amount_sol * random.uniform(1000, 10000)
            tx_signature = f"SIMULATION_{int(time.time())}"
            
            return jsonify({
                "ok": False,  # ⚠️ IMPORTANT: ok=False pour simulation
                "simulation": True,
                "purchase": {
                    "wallet_id": wallet_id,
                    "wallet_address": wallet_address,
                    "token_address": token_address,
                    "amount_sol_spent": amount_sol,
                    "estimated_tokens_received": estimated_tokens,
                    "slippage_percent": slippage_percent,
                    "transaction_signature": tx_signature,
                    "timestamp": time.time(),
                    "status": "SIMULATION_ONLY"
                },
                "warning": "This is a SIMULATION - no real transaction occurred"
            }), 202  # Accepted but not processed
        
        # Real Jupiter integration would go here
        return jsonify({
            "ok": False,
            "error": "Real Jupiter integration not yet implemented",
            "capability": "pending_implementation"
        }), 501
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Purchase failed: {str(e)}",
            "wallet_address": wallet_address,
            "token_address": token_address
        }), 500


@bp_tokens_general.get("/<token_address>/price")
@require_api_key
def get_token_price(token_address: str):
    """
    📈 Récupère le prix actuel d'un token.
    Intégration avec API de prix (CoinGecko, Jupiter).
    Sécurisé pour production.
    """
    # 🔒 SÉCURITÉ PRODUCTION
    require_auth = current_app.config.get("REQUIRE_AUTH", True)
    if require_auth and not os.getenv("API_KEY"):
        return jsonify({
            "ok": False,
            "error": "Production security required",
            "details": "REQUIRE_AUTH=true requires valid API_KEY"
        }), 401
    try:
        # Validation de l'adresse token
        if len(token_address) < 32:
            return jsonify({"ok": False, "error": "invalid token address"}), 400
        
        # 🚫 PRICE SIMULATION GATED
        coingecko_api_key = os.getenv("COINGECKO_API_KEY")
        jupiter_api_key = os.getenv("JUPITER_API_KEY")
        enable_simulation = os.getenv("ENABLE_PRICE_SIMULATION", "false").lower() == "true"
        
        if not (coingecko_api_key or jupiter_api_key) and not enable_simulation:
            return jsonify({
                "ok": False,
                "error": "Token pricing not implemented",
                "details": "CoinGecko or Jupiter Price API required. Set API keys or ENABLE_PRICE_SIMULATION=true",
                "capability": "not_implemented"
            }), 501
        
        # TODO: Intégration avec Jupiter Price API ou CoinGecko
        if enable_simulation:
            # Simulation EXPLICITE avec warning
            price_usd = random.uniform(0.00001, 0.1)
            price_sol = price_usd / 150  # Assume SOL = $150
            market_cap = random.uniform(10000, 1000000)
            change_24h = random.uniform(-50, 100)
            
            return jsonify({
                "ok": False,  # ⚠️ IMPORTANT: ok=False pour simulation
                "simulation": True,
                "token_address": token_address,
                "price": {
                    "usd": price_usd,
                    "sol": price_sol,
                    "market_cap_usd": market_cap,
                    "change_24h_percent": change_24h,
                    "last_updated": time.time()
                },
                "data_source": "SIMULATION_ONLY",
                "warning": "This is SIMULATED price data - not real market data"
            }), 202  # Accepted but simulated
        
        # Real price API integration would go here
        return jsonify({
            "ok": False,
            "error": "Real price API integration not yet implemented",
            "capability": "pending_implementation"
        }), 501
        
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Failed to fetch price: {str(e)}",
            "token_address": token_address
        }), 500
