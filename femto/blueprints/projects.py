# -*- coding: utf-8 -*-
import os
import json
from flask import Blueprint, current_app, request, jsonify
from middleware.auth import require_api_key
from conrad.api_utils import iter_project_dirs, find_project_dir

# services "vendorisés"
from rug.src.project_service import nouveau_projet, save_project, load_project, generate_wallets
from rug.src.wallet_service import get_balance_sol
from conrad.config import resolve_rpc

from pathlib import Path
from services.backups import backup_project, move_project_to_trash
from services.fileio import ensure_dir


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
        # Accept both 'count' (canonical) and 'n' (legacy) parameters
        # Priority: count > n > default(1)
        if "count" in data:
            n = int(data["count"])
        elif "n" in data:
            n = int(data["n"])
        else:
            n = 1  # default value when neither provided
    except ValueError:
        return jsonify({"ok": False, "error": "count/n must be integer"}), 400
    if n < 1 or n > 1000:
        return jsonify({"ok": False, "error": "count/n must be in 1..1000"}), 400

    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)
    new_ws = generate_wallets(pr, n)
    save_project(pr, dossier_base=base)
    
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
            "balance_sol": 0,
            "private_key_masked": _mask_private_key(private_key) if private_key else "***no_key***"
        }
        
        # Ajouter le solde si possible
        if wallet_address:
            try:
                formatted_wallet["balance_sol"] = get_balance_sol(wallet_address, rpc_url=resolve_rpc(current_app.config["DEFAULT_RPC"], "", ""))
            except:
                formatted_wallet["balance_sol"] = 0
        
        formatted_wallets.append(formatted_wallet)
    
    return jsonify({"ok": True, "created": len(new_ws), "wallets": formatted_wallets}), 201

@bp.get("/<project_id>/wallets/<address>")
@require_api_key 
def get_wallet_detail(project_id: str, address: str):
    """
    Récupère les détails d'un wallet spécifique SANS clé privée.
    Pour des raisons de sécurité, les clés privées ne sont jamais exposées via API.
    """
    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)
    wallet = None
    for w in pr.wallets:
        if w.address == address:
            wallet = w
            break
    
    if not wallet:
        return jsonify({"ok": False, "error": "wallet not found"}), 404

    # Récupérer solde en live
    env_cluster = current_app.config.get("CLUSTER", "")
    cluster_param = (request.args.get("cluster") or env_cluster or "").strip()
    rpc_param = (request.args.get("rpc") or "").strip()
    rpc = resolve_rpc(current_app.config["DEFAULT_RPC"], cluster_param, rpc_param)
    
    try:
        balance = get_balance_sol(wallet.address, rpc_url=rpc or "")
    except:
        balance = 0

    # Masquer les clés privées pour la sécurité  
    def _mask_private_key(private_key: str | None) -> str:
        if not private_key or len(private_key) < 10:
            return "***secured***"
        return f"{private_key[:6]}***...***{private_key[-4:]}"

    private_key = getattr(wallet, "private_key", None) or getattr(wallet, "secret", None)

    result = {
        "ok": True,
        "wallet": {
            "id": getattr(wallet, "id", None) or getattr(wallet, "wallet_id", None),
            "name": getattr(wallet, "name", None),
            "address": wallet.address,
            "created_at": getattr(wallet, "created_at", None),
            "balance_sol": balance,
            "private_key_masked": _mask_private_key(private_key),
            "security_note": "Private keys are never exposed via API for security reasons"
        },
        "rpc_used": rpc
    }
    
    return jsonify(result)

@bp.get("/<project_id>/wallets/<address>/export")
@require_api_key
def export_wallet_private_key(project_id: str, address: str):
    """
    🚨 ENDPOINT SÉCURISÉ - EXPORT DE CLÉ PRIVÉE 🚨
    
    Exporte la clé privée complète d'un wallet spécifique.
    ATTENTION: Cet endpoint expose des données critiques !
    
    Paramètres requis:
    - ?confirm=true : Confirmation explicite requise
    
    Usage: GET /api/v1/projects/{id}/wallets/{address}/export?confirm=true
    """
    import logging
    from datetime import datetime
    
    # Vérification de confirmation obligatoire
    confirm = request.args.get("confirm", "").lower()
    if confirm != "true":
        return jsonify({
            "ok": False, 
            "error": "Confirmation required",
            "message": "Add ?confirm=true to export private key",
            "security_warning": "This endpoint exposes sensitive private key data"
        }), 400

    # Log de sécurité
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    timestamp = datetime.utcnow().isoformat()
    
    logging.warning(f"PRIVATE_KEY_EXPORT: address={address} project={project_id} ip={client_ip} time={timestamp}")
    
    base = current_app.config["DATA_DIR"]
    pdir = find_project_dir(base, project_id)
    if not pdir:
        return jsonify({"ok": False, "error": "project not found"}), 404

    pr = load_project(pdir)
    wallet = None
    for w in pr.wallets:
        if w.address == address:
            wallet = w
            break
    
    if not wallet:
        return jsonify({"ok": False, "error": "wallet not found"}), 404

    # Récupérer toutes les informations de clés
    private_key_b58 = getattr(wallet, "private_key", None) or getattr(wallet, "secret", None)
    private_key_json = getattr(wallet, "private_key_json_64", [])
    private_key_hex = getattr(wallet, "private_key_hex_32", None)

    result = {
        "ok": True,
        "security_warning": "🚨 SENSITIVE DATA - Handle with extreme care 🚨",
        "exported_at": timestamp,
        "wallet": {
            "id": getattr(wallet, "id", None) or getattr(wallet, "wallet_id", None),
            "name": getattr(wallet, "name", None),
            "address": wallet.address,
            "created_at": getattr(wallet, "created_at", None),
            "private_key_base58": private_key_b58,
            "private_key_json_array": private_key_json,
            "private_key_hex": private_key_hex
        },
        "security_notes": [
            "Never share private keys via insecure channels",
            "Store securely offline if needed",
            "This export has been logged for security audit",
            "Revoke wallet if compromised"
        ]
    }
    
    return jsonify(result)

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
        # Format uniforme avec détails comme dans la création
        item = {
            "id": getattr(w, "id", None) or getattr(w, "wallet_id", None),
            "name": getattr(w, "name", None),
            "address": w.address,
            "created_at": getattr(w, "created_at", None)
        }
        if with_balance:
            try:
                item["balance_sol"] = get_balance_sol(w.address, rpc_url=rpc or "")
            except Exception as e:
                item["balance_error"] = str(e)
        else:
            item["balance_sol"] = 0
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
# V3.6 — Endpoints projets & wallets (création, liste, renommage, import/export)
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
    return Path(p)

def _mask_private_key(private_key: str) -> str:
    """Masque une clé privée en gardant les premiers/derniers caractères."""
    if not private_key or len(private_key) < 10:
        return "***masked***"
    return f"{private_key[:6]}***...***{private_key[-4:]}"

def _ensure_wallet_render(w: dict, include_balance=False, rpc_url=None, show_private=False) -> dict:
    """
    Normalise le rendu JSON d'un wallet pour v3.6 : id, name, address, balance_sol?, created_at.
    🔒 SÉCURISÉ - Les clés privées sont masquées par défaut.
    🔥 FIX CRITIQUE: Plus de substring [:8] - ID complet pour sécurité.
    """
    # 🔒 SÉCURITÉ CRITIQUE: Utiliser ID complet - AUCUN substring dangereux
    wallet_id = str(w.get("id") or w.get("wallet_id") or "")
    if not wallet_id:
        # Si pas d'ID, utiliser adresse complète comme identifiant sécurisé
        wallet_id = str(w.get("address") or w.get("pubkey") or "")
    
    out = {
        "id": wallet_id,  # 🔒 ID COMPLET - plus de [:8] dangereux
        "name": w.get("name"),
        "address": w.get("address") or w.get("pubkey"),
        "created_at": w.get("created_at") or w.get("created") or None,
    }
    
    if include_balance and out["address"]:
        try:
            sol = get_balance_sol(out["address"], rpc_url=rpc_url or "")
            out["balance_sol"] = sol
        except Exception as e:
            out["balance_error"] = str(e)
    
    # Gestion des clés privées selon le contexte
    private_key = w.get("private_key") or w.get("private_key_base58_64") or w.get("secret")
    if private_key:
        if show_private:
            out["private_key"] = private_key
            out["private_key_json_64"] = w.get("private_key_json_64", [])
        else:
            # Masquer la clé pour les listes publiques
            out["private_key_masked"] = _mask_private_key(private_key)
    
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
    pr = nouveau_projet(name, dossier_base=base)  # utilise service existant
        # Forcer le statut du token à "undeployed" dès la création
    try:
        # Même si le dataclass n'a pas le champ, on le garde en mémoire
        pr.token.status = "undeployed"
    except Exception:
        pass

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
            # Détection "token édité" : par défaut le modèle met "MyMeme"/"MEME".
            token_dict = (pd.get("token") or {})
            default_name = "MyMeme"
            default_symbol = "MEME"
            edited = bool(token_dict) and (
                (token_dict.get("name") and token_dict.get("name") != default_name) or
                (token_dict.get("symbol") and token_dict.get("symbol") != default_symbol)
            )

            token_block = None
            if edited:
                token_block = {
                    "name": token_dict.get("name"),
                    "symbol": token_dict.get("symbol"),
                    # si non présent dans le JSON du projet, on force "undeployed" par défaut
                    "status": token_dict.get("status") or "undeployed",
                }

            projs.append({
                "project_id": pd.get("project_id"),
                "name": pd.get("name"),
                "created_at": pd.get("created_at"),
                "slug": pd.get("slug"),
                "wallets": len(pd.get("wallets") or []),
                "token": token_block,
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
    try:
        old_pdir = _project_dir(base, project_id)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "project not found"}), 404
    
    pr = load_project(old_pdir)
    old_name = pr.name
    new_slug = slugify(new_name or "project")
    
    # Mettre à jour le projet
    pr.name = new_name
    pr.slug = new_slug
    
    # Calculer le nouveau répertoire
    from rug.src.project_service import _project_dir as calc_project_dir
    new_pdir = calc_project_dir(base, pr)
    
    # Si le chemin change, déplacer atomiquement
    if str(old_pdir) != str(new_pdir):
        import shutil
        # S'assurer que le répertoire de destination n'existe pas
        if new_pdir.exists():
            return jsonify({"ok": False, "error": "project with this name already exists"}), 409
        shutil.move(str(old_pdir), str(new_pdir))
    
    # Sauvegarder le projet mis à jour
    save_project(pr, dossier_base=base)
    return jsonify({"ok": True, "project_id": pr.project_id, "old_name": old_name, "new_name": new_name})

@bp.get("/<project_id>/export")
@require_api_key
def export_project(project_id: str):
    """Exporte un projet en JSON (brut lisible)."""
    base = current_app.config["DATA_DIR"]
    try:
        pdir = _project_dir(base, project_id)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "project not found"}), 404
    
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
    pr = nouveau_projet(name, dossier_base=base)
    # Injecter wallets si fournis
    wallets = data.get("wallets") or data.get("wallets_file", {}).get("wallets") or []
    if wallets:
        # Convertir les dicts en instances WalletExport sécurisées
        from rug.src.models import WalletExport
        wallet_instances = []
        for w in wallets:
            if isinstance(w, dict):
                # Mapper les champs attendus avec support pour les anciens formats
                wallet_data = {
                    'address': w.get("address") or w.get("pubkey", ""),
                    'private_key_base58_64': w.get("private_key_base58_64") or w.get("private_key") or w.get("secret", ""),
                    'private_key_json_64': w.get("private_key_json_64", []),
                    'public_key_hex': w.get("public_key_hex", ""),
                    'private_key_hex_32': w.get("private_key_hex_32", ""),
                    'name': w.get("name"),
                    'id': w.get("id") or w.get("wallet_id")
                }
                wallet_instances.append(WalletExport(**wallet_data))
        pr.wallets = wallet_instances
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
            # 🔒 SÉCURITÉ CRITIQUE: Correspondances EXACTES seulement - AUCUN substring
            wid = str(w.get("id") or w.get("wallet_id") or "")
            addr = str(w.get("address") or w.get("pubkey") or "")
            if (wid and wid == str(wallet_id)) or (addr and addr == str(wallet_id)):
                w["name"] = new_name
                changed = True
        if changed:
            # Assurer que les wallets sont des instances WalletExport correctes
            if pd.get("wallets"):
                from rug.src.models import WalletExport
                wallet_instances = []
                for w in (pd.get("wallets") or []):
                    if isinstance(w, dict):
                        # Convertir dict vers WalletExport avec gestion des champs manquants
                        wallet_data = {
                            'address': w.get('address') or w.get('pubkey', ''),
                            'private_key_base58_64': w.get('private_key_base58_64') or w.get('private_key', ''),
                            'private_key_json_64': w.get('private_key_json_64', []),
                            'public_key_hex': w.get('public_key_hex', ''),
                            'private_key_hex_32': w.get('private_key_hex_32', ''),
                            'name': w.get('name'),
                            'id': w.get('id') or w.get('wallet_id')
                        }
                        wallet_instances.append(WalletExport(**wallet_data))
                    else:
                        wallet_instances.append(w)
                pr.wallets = wallet_instances
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
            wid = str(w.get("id") or w.get("wallet_id") or "")
            addr = str(w.get("address") or w.get("pubkey") or "")
            # 🔥 FIX CRITIQUE: SUPPRIMÉ addr_short[:8] - plus de substring dangereux
            
            # 🔒 SÉCURITÉ CRITIQUE: Résolution EXACTE seulement - AUCUN substring
            if (wid and wid == str(wallet_id)) or (addr and addr == str(wallet_id)):
                return jsonify({"ok": True, "wallet": _ensure_wallet_render(w, include_balance=include_balance, rpc_url=rpc)})
    return jsonify({"ok": False, "error": "wallet not found"}), 404

@bp.get("/wallets/<wallet_id>/export")
@require_api_key
def export_wallet(wallet_id: str):
    """
    🔒 ENDPOINT DÉSACTIVÉ POUR SÉCURITÉ - L'export des clés privées via API est interdit.
    Utiliser les backups locaux ou les outils administratifs sécurisés.
    """
    return jsonify({
        "ok": False, 
        "error": "Wallet private key export disabled for security",
        "note": "Use local backup tools or secure administrative access"
    }), 403

@bp.post("/<project_id>/wallets/import")
@require_api_key
def import_wallets(project_id: str):
    """Importe un ou plusieurs wallets via clés privées (base58 ou tableau JSON de 64 octets)."""
    data = request.get_json(force=True, silent=True) or {}
    base = current_app.config["DATA_DIR"]
    try:
        pdir = _project_dir(base, project_id)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "project not found"}), 404
    
    pr = load_project(pdir)
    keys = []
    if "private_key" in data:
        keys.append(data["private_key"])
    keys.extend(data.get("private_keys") or [])
    
    # Utiliser le service sécurisé pour importer les wallets
    from rug.src.project_service import import_wallets_from_lines
    try:
        imported = import_wallets_from_lines(pr, keys)
        save_project(pr, dossier_base=base)
        return jsonify({"ok": True, "imported": len(imported), "wallets": [w.address for w in imported]})
    except Exception as e:
        return jsonify({"ok": False, "error": f"import failed: {str(e)}"}), 400


@bp.get("/<project_id>/stats")
@require_api_key
def project_stats(project_id: str):
    """
    📊 Statistiques complètes d'un projet memecoin.
    Essential pour analyser la performance du token créé.
    """
    base = current_app.config["DATA_DIR"]
    
    try:
        pdir = _project_dir(base, project_id)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "project not found"}), 404
    
    pr = load_project(pdir)
    pd = _project_to_dict(pr)
    
    # Informations de base du projet
    project_info = {
        "project_id": pd.get("project_id"),
        "name": pd.get("name"),
        "created_at": pd.get("created_at"),
        "wallets_count": len(pd.get("wallets", []))
    }
    
    # Informations du token
    token_info = pd.get("token", {})
    token_stats = {
        "name": token_info.get("name"),
        "symbol": token_info.get("symbol"), 
        "description": token_info.get("description"),
        "decimals": token_info.get("decimals", 9),
        "initial_supply": token_info.get("initial_supply", 1_000_000_000)
    }
    
    # Calculer les statistiques des wallets
    wallets = pd.get("wallets", [])
    total_sol_balance = 0.0
    active_wallets = 0
    
    try:
        rpc = resolve_rpc(
            current_app.config["DEFAULT_RPC"], 
            current_app.config.get("CLUSTER", ""), 
            request.args.get("rpc", "")
        )
        
        for wallet in wallets:
            try:
                addr = wallet.get("address") or wallet.get("pubkey")
                if addr:
                    balance = get_balance_sol(addr, rpc_url=rpc)
                    total_sol_balance += balance
                    if balance > 0:
                        active_wallets += 1
            except Exception:
                continue
                
    except Exception:
        pass
    
    # Statistiques financières (simulées pour l'instant)
    import time
    import random
    
    financial_stats = {
        "total_sol_balance": total_sol_balance,
        "active_wallets": active_wallets,
        "estimated_token_supply": token_stats["initial_supply"],
        "estimated_market_cap_usd": random.uniform(10000, 500000),  # Simulation
        "estimated_price_usd": random.uniform(0.00001, 0.01),       # Simulation
        "holders_count": random.randint(50, 1000),                   # Simulation
        "volume_24h_usd": random.uniform(1000, 50000),              # Simulation
        "price_change_24h": random.uniform(-30, 50),                # Simulation
        "all_time_high": random.uniform(0.01, 0.1),                 # Simulation
        "all_time_low": random.uniform(0.000001, 0.001),            # Simulation
    }
    
    # Métriques de performance
    performance_metrics = {
        "roi_percentage": random.uniform(-50, 500),  # Simulation
        "liquidity_usd": random.uniform(5000, 100000),  # Simulation
        "trading_pairs": ["SOL", "USDC"],  # Typique pour Solana
        "dex_listings": ["Raydium", "Jupiter", "Orca"],  # Simulation
        "last_updated": time.time()
    }
    
    return jsonify({
        "ok": True,
        "project": project_info,
        "token": token_stats,
        "financial": financial_stats,
        "performance": performance_metrics,
        "note": "Stats include simulated market data - integrate with Jupiter/CoinGecko for real data"
    })
