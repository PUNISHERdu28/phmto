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

bp_tokens = Blueprint("tokens", __name__, url_prefix="/api/v1")

def _tokens_dir(base: str) -> Path:
    return Path(base) / "tokens"

def _token_path(base: str, token_id: str) -> Path:
    return _tokens_dir(base) / f"{token_id}.json"

@bp_tokens.patch("/tokens/<token_id>")
@require_api_key
def edit_token(token_id: str):
    """
    Met à jour les attributs d'un token (metadata locale).
    Body JSON: { name?, symbol?, description?, image_uri?, attributes? (dict), extra? (dict) }
    """
    data: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
    if not data:
        return jsonify({"ok": False, "error": "empty body"}), 400

    base = current_app.config["DATA_DIR"]
    path = _token_path(base, token_id)
    if not path.exists():
        return jsonify({"ok": False, "error": f"token '{token_id}' not found"}), 404

    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        # champs connus
        for k in ("name", "symbol", "description", "image_uri"):
            if k in data:
                meta[k] = data[k]
        # attributs libres (optionnels)
        if "attributes" in data and isinstance(data["attributes"], dict):
            meta.setdefault("attributes", {}).update(data["attributes"])
        if "extra" in data and isinstance(data["extra"], dict):
            meta.setdefault("extra", {}).update(data["extra"])

        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        return jsonify({"ok": True, "token_id": token_id, "metadata": meta}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500



# =========================
# V3.5 — Token management for a project (edit/reset/create via Pump.fun)
# =========================
from flask import current_app
import os, requests

bp_tokens = Blueprint("tokens_v35", __name__, url_prefix="/api/v1/projects")

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
    pd = pr.to_dict() or {}
    tok = pd.get("token") or {}
    for k in ("name","symbol","description","image_uri","website","twitter","telegram"):
        if k in data:
            tok[k] = data[k]
    pd["token"] = tok
    pr.token = tok  # si attribut
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "token": tok})

@bp_tokens.delete("/<project_id>/token")
@require_api_key
def token_reset(project_id: str):
    """Réinitialise les attributs du token du projet."""
    base = current_app.config["DATA_DIR"]
    pdir = _proj_dir(base, project_id)
    pr = load_project(pdir)
    pr.token = {"name": "MyMeme", "symbol": "MEME", "description": ""}
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "reset": True, "token": pr.to_dict().get("token")})

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
