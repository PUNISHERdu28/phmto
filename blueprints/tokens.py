# routes_tokens.py
# -*- coding: utf-8 -*-
"""
Endpoints liés aux tokens.
Ajout : PATCH /api/v1/tokens/<token_id> pour éditer les métadonnées (nom, symbole, description, image_uri, etc.)
"""

import os
from typing import Dict, Any
from pathlib import Path
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from api_utils import find_project_dir
from rug.src.project_service import load_project, save_project
from rug.src.models import TokenMetadata

# =========================
# Token management for projects (edit/reset/create via Pump.fun)
# =========================

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
