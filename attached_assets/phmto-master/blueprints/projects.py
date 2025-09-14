# -*- coding: utf-8 -*-
import os
import json
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from api_utils import iter_project_dirs, find_project_dir

# services "vendorisés"
from rug.src.project_service import nouveau_projet, save_project, load_project, generate_wallets
from rug.src.wallet_service import get_balance_sol
from config import resolve_rpc

from pathlib import Path
from services.backups import backup_project, move_project_to_trash
from services.fileio import ensure_dir

from pathlib import Path
from flask import Blueprint, current_app, request, jsonify
from api_utils import iter_project_dirs, find_project_dir
from rug.src.project_service import nouveau_projet, save_project, load_project


bp = Blueprint("projects", __name__, url_prefix="/api/v1/projects")

# --- Helpers ---
def _project_to_dict(pr) -> dict:
    """Convertit un objet Project en dict sans placeholders 'string'."""
    # 1) Essaye d'abord 'to_dict' si présent
    d = None
    if hasattr(pr, "to_dict"):
        try:
            d = pr.to_dict()
        except Exception:
            d = None

    # 2) Fallback manuel si to_dict() renvoie des placeholders
    if not d or not isinstance(d, dict) or d.get("project_id") in (None, "", "string"):
        d = {
            "project_id": getattr(pr, "project_id", None),
            "name": getattr(pr, "name", None),
            "slug": getattr(pr, "slug", None),
            "created_at": getattr(pr, "created_at", None),
            "wallets": getattr(pr, "wallets", []),
        }

    # 3) Nettoie les champs 'string'
    for k, v in list(d.items()):
        if isinstance(v, str) and v.strip().lower() == "string":
            d[k] = None
    return d


@bp.get("/<project_id>")
@require_api_key
def get_project(project_id: str):
    """ Charge le projet par `project_id` et renvoie sa structure complète (to_dict). """
    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404
    pr = load_project(pdir)
    return jsonify({"ok": True, "project": pr.to_dict()})

@bp.post("/<project_id>/wallets")
@require_api_key
def create_wallets(project_id: str):
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

@bp.get("/<project_id>/wallets")
@require_api_key
def list_wallets(project_id: str):
    """
    Liste les wallets d'un projet.
    - ?with_balance=true pour inclure le solde (live, via RPC)
    - ?cluster=devnet|testnet|mainnet ou ?rpc=<url> pour forcer l'endpoint RPC
    """
    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)
    with_balance = (request.args.get("with_balance") or "").lower() in ("1", "true", "yes")
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (request.args.get("cluster") or env_cluster or "").strip()
    rpc_param = (request.args.get("rpc") or "").strip()
    rpc = resolve_rpc(current_app.config["DEFAULT_RPC"], cluster_param, rpc_param)

    result = []
    for w in pr.wallets:
        item = {"address": w.address}
        if with_balance:
            try:
                item["balance_sol"] = get_balance_sol(w.address, rpc_url=rpc)
            except Exception as e:
                item["balance_error"] = str(e)
        result.append(item)

    return jsonify({
        "ok": True,
        "project_id": pr.project_id,
        "name": pr.name,
        "wallets": result,
        "rpc_used": rpc,
        "cluster": cluster_param or env_cluster
    })

@bp.delete("/<project_id>")
@require_api_key
def delete_project(project_id: str):
    """ Sauvegarde JSON de tous les wallets du projet (private/public), puis déplace le dossier du projet vers `data/.trash` pour sécurité. """
    base = current_app.config["DATA_DIR"]
    backups_dir = Path(base) / "backups"
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)

    # 1) Sauvegarde globale (toutes clés/pub)
    try:
        ensure_dir(backups_dir / "projects")
        backup_path = backup_project(pr.to_dict(), Path(pdir), backups_dir)
    except Exception as e:
        return jsonify({"ok": False, "error": f"backup failed: {e}"}), 500

    # 2) Déplacement en corbeille
    try:
        trashed_path = move_project_to_trash(Path(pdir), Path(base))
    except Exception as e:
        return jsonify({"ok": False, "error": f"trash failed: {e}"}), 500

    return jsonify({
        "ok": True,
        "project_id": pr.project_id,
        "backup": str(backup_path),
        "trashed_path": str(trashed_path),
        "note": "Le projet a été déplacé dans data/.trash pour sécurité.",
    }), 200


# =========================
# V3.5 — Endpoints projets & wallets (création, liste, renommage, import/export)
# =========================

from datetime import datetime, timezone
from slugify import slugify
from werkzeug.utils import secure_filename
from io import BytesIO

def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _project_dir(base: str, project_id: str) -> Path:
    p = find_project_dir(base, project_id)
    if not p:
        raise FileNotFoundError("project not found")
    return p

def _ensure_wallet_render(w: dict, include_balance=False, rpc_url=None) -> dict:
    """
    Normalise le rendu JSON d'un wallet pour v3.5 : id, name, address, balance_sol?, created_at, private_key.
    """
    out = {
        "id": str(w.get("id") or w.get("wallet_id") or (w.get("address") or "")[:8]),
        "name": w.get("name"),
        "address": w.get("address") or w.get("pubkey"),
        "created_at": w.get("created_at") or w.get("created") or None,
        "private_key": w.get("private_key_base58_64") or w.get("private_key") or w.get("secret"),
    }
    if include_balance and out["address"]:
        try:
            sol = get_balance_sol(out["address"], rpc_url=rpc_url)
            out["balance_sol"] = sol
        except Exception as e:
            out["balance_error"] = str(e)
    return out

@bp.post("")
@require_api_key
def create_project():
    """Crée un nouveau projet avec un ID stable (8 hex) et slug dérivé du nom."""
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    base = current_app.config["DATA_DIR"]
    pr = nouveau_projet(name, base_dir=base)  # utilise service existant
    # enrichir
    obj = pr.to_dict()
    obj["created_at"] = obj.get("created_at") or _now_iso()
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "project": obj}), 201

@bp.get("")
@require_api_key
def list_projects():
    """Liste tous les projets (synthèse)."""
    base = current_app.config["DATA_DIR"]
    projs = []
    for pdir in iter_project_dirs(base):
        try:
            pr = load_project(pdir)
            pd = pr.to_dict() or {}
            projs.append({
                "project_id": pd.get("project_id"),
                "name": pd.get("name"),
                "slug": pd.get("slug"),
                "created_at": pd.get("created_at"),
                "wallets": len(pd.get("wallets") or []),
            })
        except Exception:
            continue
    return jsonify({"ok": True, "projects": projs})

@bp.patch("/<project_id>")
@require_api_key
def rename_project(project_id: str):
    """Renomme un projet (met à jour le slug et sauvegarde)."""
    data = request.get_json(force=True, silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"ok": False, "error": "name is required"}), 400
    base = current_app.config["DATA_DIR"]
    pdir = _project_dir(base, project_id)
    pr = load_project(pdir)
    pd = pr.to_dict() or {}
    old_name = pd.get("name")
    pd["name"] = new_name
    pd["slug"] = slugify(new_name or "project")
    # persist via model
    pr.name = pd["name"]
    pr.slug = pd["slug"]
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "project_id": pr.project_id, "old_name": old_name, "new_name": new_name})

@bp.get("/<project_id>/export")
@require_api_key
def export_project(project_id: str):
    """Exporte un projet en JSON (brut lisible)."""
    base = current_app.config["DATA_DIR"]
    pdir = _project_dir(base, project_id)
    pr = load_project(pdir)
    obj = pr.to_dict() or {}
    obj["exported_at"] = _now_iso()
    # Inclure wallets.json si présent
    wpath = Path(pdir) / "wallets.json"
    if wpath.exists():
        try:
            wallets = json.loads(wpath.read_text(encoding="utf-8"))
            obj["wallets_file"] = wallets
        except Exception:
            pass
    return jsonify({"ok": True, "project_backup": obj})

@bp.post("/import")
@require_api_key
def import_project():
    """Importe un projet via JSON brut (body)."""
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "JSON object required"}), 400
    base = current_app.config["DATA_DIR"]
    # Recréer projet
    name = (data.get("name") or data.get("project", {}).get("name") or "Imported Project").strip()
    pr = nouveau_projet(name, base_dir=base)
    # Injecter wallets si fournis
    wallets = data.get("wallets") or data.get("wallets_file", {}).get("wallets") or []
    if wallets:
        # Convertir en format attendu par model
        pd = pr.to_dict()
        pd["wallets"] = wallets
        pr.wallets = wallets  # si attribut supporté
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "project_id": pr.project_id, "name": pr.name, "wallets": len(pr.to_dict().get("wallets") or [])})

@bp.patch("/wallets/<wallet_id>")
@require_api_key
def rename_wallet(wallet_id: str):
    """Renomme un wallet par son ID (recherche globale)."""
    data = request.get_json(force=True, silent=True) or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"ok": False, "error": "name required"}), 400
    base = current_app.config["DATA_DIR"]
    # Recherche dans tous les projets
    for pdir in iter_project_dirs(base):
        pr = load_project(pdir)
        pd = pr.to_dict() or {}
        changed = False
        for w in (pd.get("wallets") or []):
            wid = str(w.get("id") or w.get("wallet_id") or (w.get("address") or "")[:8])
            if wid == str(wallet_id):
                w["name"] = new_name
                changed = True
        if changed:
            pr.wallets = pd.get("wallets")
            save_project(pr, dossier_base=base)
            return jsonify({"ok": True, "wallet_id": wallet_id, "new_name": new_name})
    return jsonify({"ok": False, "error": "wallet not found"}), 404

@bp.get("/wallets/<wallet_id>")
@require_api_key
def wallet_detail(wallet_id: str):
    """Retourne le détail complet d'un wallet (id, name, address, created_at, private_key, balance optionnelle)."""
    base = current_app.config["DATA_DIR"]
    include_balance = (request.args.get("with_balance") == "true")
    rpc = resolve_rpc(current_app.config["DEFAULT_RPC"], current_app.config.get("CLUSTER",""), request.args.get("rpc",""))
    for pdir in iter_project_dirs(base):
        pr = load_project(pdir)
        pd = pr.to_dict() or {}
        for w in (pd.get("wallets") or []):
            wid = str(w.get("id") or w.get("wallet_id") or (w.get("address") or "")[:8])
            if wid == str(wallet_id):
                return jsonify({"ok": True, "wallet": _ensure_wallet_render(w, include_balance=include_balance, rpc_url=rpc)})
    return jsonify({"ok": False, "error": "wallet not found"}), 404

@bp.get("/wallets/<wallet_id>/export")
@require_api_key
def export_wallet(wallet_id: str):
    """Exporte un wallet en JSON brut (adresse + clé privée)."""
    base = current_app.config["DATA_DIR"]
    for pdir in iter_project_dirs(base):
        pr = load_project(pdir)
        pd = pr.to_dict() or {}
        for w in (pd.get("wallets") or []):
            wid = str(w.get("id") or w.get("wallet_id") or (w.get("address") or "")[:8])
            if wid == str(wallet_id):
                out = {
                    "type": "wallet_backup",
                    "timestamp": _now_iso(),
                    "project": {"project_id": pr.project_id, "name": pr.name, "slug": pr.slug},
                    "wallet": {"address": w.get("address") or w.get("pubkey"), "private_key": w.get("private_key_base58_64") or w.get("private_key") or w.get("secret")}
                }
                return jsonify(out)
    return jsonify({"ok": False, "error": "wallet not found"}), 404

@bp.post("/<project_id>/wallets/import")
@require_api_key
def import_wallets(project_id: str):
    """Importe un ou plusieurs wallets via clés privées (base58 ou tableau JSON de 64 octets)."""
    data = request.get_json(force=True, silent=True) or {}
    base = current_app.config["DATA_DIR"]
    pdir = _project_dir(base, project_id)
    pr = load_project(pdir)
    pd = pr.to_dict() or {}
    wl = pd.get("wallets") or []
    keys = []
    if "private_key" in data:
        keys.append(data["private_key"])
    keys.extend(data.get("private_keys") or [])
    imported = []
    for key in keys:
        priv = key
        try:
            # On stocke tel quel (base58 ou liste) et laisser le service générer l'address si nécessaire
            w = {"private_key": priv}
            wl.append(w)
            imported.append(w)
        except Exception:
            continue
    pd["wallets"] = wl
    pr.wallets = wl
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "imported": len(imported), "wallets": [ _ensure_wallet_render(w) for w in imported ]})
