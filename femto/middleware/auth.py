# -*- coding: utf-8 -*-
from functools import wraps
from flask import current_app, request, jsonify
import json
import os
from pathlib import Path

def _load_auth_config():
    """Charge la configuration d'authentification depuis le fichier."""
    try:
        config_path = Path(__file__).parent.parent / "auth_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    # Configuration par défaut si fichier absent ou erreur
    return {
        "auth_enabled": False,
        "simple_password": "godhand123"
    }

def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Charger la config depuis le fichier
        auth_config = _load_auth_config()
        
        # Vérifier si l'auth est activée dans le fichier de config
        if not auth_config.get("auth_enabled", False):
            return fn(*args, **kwargs)
        
        # Récupérer le mot de passe attendu
        expected = auth_config.get("simple_password", "").strip()
        
        # Vérifier les headers (x-api-key et Authorization)
        got_x_api = (request.headers.get("x-api-key") or "").strip()
        got_auth = (request.headers.get("Authorization") or "").strip()
        
        # Nettoyer le Bearer token
        if got_auth.startswith("Bearer "):
            got_auth = got_auth.split(" ", 1)[1]
        
        # Accepter soit x-api-key soit Authorization
        provided_key = got_x_api or got_auth
        
        if not expected or provided_key != expected:
            return jsonify({
                "ok": False, 
                "error": "unauthorized",
                "hint": "Utilisez la clé API dans le header x-api-key ou Authorization"
            }), 401
        
        return fn(*args, **kwargs)
    return wrapper
