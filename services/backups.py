# -*- coding: utf-8 -*-
import json, shutil, time
from pathlib import Path
from typing import Dict, Any, List, Optional

from services.fileio import atomic_write_json, ensure_dir

# --- Helpers pour retrouver la clé privée d'un wallet ---
def _load_private_key_for_wallet(wallet: Dict[str, Any], project_dir: Path) -> Optional[Any]:
    """
    Essaie de retrouver la clé privée associée à un wallet.
    - Si le wallet possède 'secret_key' ou 'secret' en mémoire -> on l'utilise.
    - Sinon on tente via un chemin stocké ('secret_path' / 'key_path').
    - En dernier recours, on inspecte un stockage JSON local type wallets.json.
    Retourne un objet JSON-sérialisable (liste d'entiers 64, string base58, etc.), ou None si introuvable.
    """
    # 1) Champs en mémoire
    for k in ("secret_key", "secret", "private_key", "priv"):
        if k in wallet and wallet[k]:
            return wallet[k]

    # 2) Chemin sur disque
    for k in ("secret_path", "key_path", "path"):
        sp = wallet.get(k)
        if sp:
            p = (project_dir / sp) if not str(sp).startswith("/") else Path(sp)
            if p.exists():
                try:
                    with p.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                    # Common keys in many Solana tools
                    for kk in ("secret_key", "secret", "private_key", "priv", "keypair", "keypair_bytes"):
                        if kk in data:
                            return data[kk]
                except Exception:
                    pass

    # 3) Fichiers standards dans le projet
    for candidate in ("wallets.json", "keys.json"):
        p = project_dir / candidate
        if p.exists():
            try:
                j = json.loads(p.read_text(encoding="utf-8"))
                # Cherche une entrée correspondant à l'address
                want = wallet.get("address") or wallet.get("pubkey")
                if isinstance(j, list):
                    for w in j:
                        if (w.get("address") or w.get("pubkey")) == want:
                            for kk in ("secret_key", "secret", "private_key", "priv", "keypair", "keypair_bytes"):
                                if kk in w:
                                    return w[kk]
                elif isinstance(j, dict):
                    w = j.get(want) or {}
                    for kk in ("secret_key", "secret", "private_key", "priv", "keypair", "keypair_bytes"):
                        if kk in w:
                            return w[kk]
            except Exception:
                pass

    return None

def _timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.gmtime())

def backup_wallet(project: Dict[str, Any], wallet: Dict[str, Any], project_dir: Path, backups_dir: Path) -> Path:
    ts = _timestamp()
    slug = project.get("slug", project.get("name", "project")).replace(" ", "-")
    addr = wallet.get("address") or wallet.get("pubkey") or "unknown"
    out = backups_dir / "wallets" / f"{ts}_{slug}_{addr}.save.json"

    secret = _load_private_key_for_wallet(wallet, project_dir)
    payload = {
        "type": "wallet_backup",
        "timestamp": ts,
        "project": {
            "project_id": project.get("project_id"),
            "name": project.get("name"),
            "slug": slug,
        },
        "wallet": {
            "address": addr,
            "private_key": secret,  # peut être None si introuvable
        },
    }
    atomic_write_json(out, payload)
    return out

def backup_project(project: Dict[str, Any], project_dir: Path, backups_dir: Path) -> Path:
    ts = _timestamp()
    slug = project.get("slug", project.get("name", "project")).replace(" ", "-")
    pid = project.get("project_id", "noid")
    out = backups_dir / "projects" / f"{ts}_{slug}_{pid}.sauvegarde.json"

    wallets = project.get("wallets") or []
    items: List[Dict[str, Any]] = []
    for w in wallets:
        addr = w.get("address") or w.get("pubkey") or "unknown"
        secret = _load_private_key_for_wallet(w, project_dir)
        items.append({
            "address": addr,
            "private_key": secret,  # peut être None si introuvable
        })

    payload = {
        "type": "project_backup",
        "timestamp": ts,
        "project": {
            "project_id": pid,
            "name": project.get("name"),
            "slug": slug,
        },
        "wallets": items,
    }
    atomic_write_json(out, payload)
    return out

def move_project_to_trash(project_dir: Path, data_dir: Path) -> Path:
    trash = data_dir / ".trash"
    ensure_dir(trash)
    target = trash / project_dir.name
    i = 1
    while target.exists():
        target = trash / f"{project_dir.name}_{i}"
        i += 1
    shutil.move(str(project_dir), str(target))
    return target