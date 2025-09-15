# -*- coding: utf-8 -*-
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from slugify import slugify
from .models import Project, TokenMetadata, PumpFunConfig, WalletExport, new_project_id
from .storage import ensure_dir, write_json, write_text, read_json
from .wallet_gen import generate_wallet
import os
try:
    from flask import current_app
except Exception:
    current_app = None

def resolve_data_dir() -> Path:
    """
    Résout le DATA_DIR dans l'ordre :
    - current_app.config["DATA_DIR"] si Flask est dispo
    - variable d'environnement DATA_DIR
    - ./data (par défaut)
    Garantit l'existence du dossier et retourne un Path.
    """
    base = None
    try:
        if current_app is not None:
            base = current_app.config.get("DATA_DIR")
    except Exception:
        base = None
    if not base:
        base = os.environ.get("DATA_DIR")
    if not base:
        base = "./data"
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _project_dir(base: Path | str, project: Project) -> Path:
    return Path(base) / f"{project.project_id}_{project.slug}"

def nouveau_projet(nom: str, dossier_base: Path | str = "./data") -> Project:
    project_id = new_project_id()
    slug = slugify(nom) or "projet"
    created_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    project = Project(
        project_id=project_id,
        name=nom,
        slug=slug,
        created_at=created_at,
    )
    base = _project_dir(dossier_base, project)
    ensure_dir(base)
    write_json(base / "project.json", project.to_dict())
    write_text(base / "README.txt", f"# {nom} — {project_id}\nCréé le {created_at}\n")
    return project

def load_project(path: Path | str) -> Project:
    data = read_json(Path(path) / "project.json")
    # reconstruction simple avec gestion des anciens formats :
    wallets = []
    for w in data.get("wallets", []):
        if isinstance(w, dict):
            # Gérer les anciens formats sans champ id
            wallet_data = w.copy()
            wallets.append(WalletExport(**wallet_data))
        else:
            # Déjà un WalletExport ou autre
            wallets.append(w)
    
    token = TokenMetadata(**data["token"])

    token_data = (data.get("token") or {}).copy()
    token_status = token_data.pop("status", None)  # ignorer les champs non supportés par le dataclass
    token = TokenMetadata(**token_data)
    if token_status is not None:
        setattr(token, "status", token_status)  # on rattache l'attribut dynamiquement

    pumpfun = PumpFunConfig(**data["pumpfun"])
    return Project(
        project_id=data["project_id"],
        name=data["name"],
        slug=data["slug"],
        created_at=data["created_at"],
        wallets=wallets,
        token=token,
        pumpfun=pumpfun,
        extras=data.get("extras", {})
    )

def save_project(project: Project, dossier_base: Path | str = "./data") -> Path:
        # Résoudre le répertoire du projet (prend en compte DATA_DIR auto)
    base_dir = Path(dossier_base) if dossier_base else resolve_data_dir()
    base = base_dir / f"{project.project_id}_{project.slug}"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise RuntimeError(f"Cannot create project dir {base}: {e}")

    # Construire un dict sauvegardable et injecter 'token.status' si posé dynamiquement
    d = project.to_dict()
    try:
        if getattr(project, "token", None) is not None and getattr(project.token, "status", None) is not None:
            d.setdefault("token", {})
            d["token"]["status"] = project.token.status
    except Exception:
        pass

    # DEBUG optionnel: trace où on écrit (tu peux enlever plus tard)
    # print(f"[save_project] Writing to {base}")

    write_json(base / "project.json", d)
    write_json(base / "wallets.json", {"wallets": [asdict(w) for w in project.wallets]})
    return base

def generate_wallets(project: Project, n: int) -> List[WalletExport]:
    new_ws: List[WalletExport] = []
    # Compter les wallets existants pour continuer la numérotation
    existing_count = len(project.wallets)
    
    for i in range(n):
        d = generate_wallet()
        # Ajouter le nom automatique "Wallet 1", "Wallet 2", etc.
        d["name"] = f"Wallet {existing_count + i + 1}"
        wallet = WalletExport(**d)
        # S'assurer que l'id est généré correctement via __post_init__
        new_ws.append(wallet)
    project.wallets.extend(new_ws)
    return new_ws

def import_wallets_from_lines(project: Project, lines: List[str]) -> List[WalletExport]:
    """
    Accepte pour chaque ligne :
    - Base58 sk+pk (64 bytes) -> on reconstruit l'adresse
    - JSON [64] -> sk+pk -> on reconstruit l'adresse
    - Format 'address;base58_skpk64' (adresse explicite + secret)
    """
    import base58, json
    from nacl.signing import SigningKey

    imported: List[WalletExport] = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        addr = None
        secret_json = None
        secret_b58 = None

        if ";" in s:  # address;base58sk
            addr, right = s.split(";", 1)
            try:
                b = base58.b58decode(right.strip())
                if len(b) != 64: raise ValueError
                secret_b58 = right.strip()
                # derive pub from secret:
                priv32, pub32 = b[:32], b[32:]
            except Exception:
                raise ValueError(f"Format invalide: {s}")
        elif s.startswith("[") and s.endswith("]"):
            arr = json.loads(s)
            b = bytes(arr)
            if len(b) != 64: raise ValueError(f"JSON 64 attendu: {s[:20]}...")
            secret_json = arr
            priv32, pub32 = b[:32], b[32:]
        else:
            # Base58 ?
            b = base58.b58decode(s)
            if len(b) != 64: raise ValueError(f"Base58 64 attendu: {s[:20]}...")
            secret_b58 = s
            priv32, pub32 = b[:32], b[32:]

        if addr is None:
            addr = base58.b58encode(pub32).decode()

        if secret_json is None:
            secret_json = list(priv32 + pub32)
        if secret_b58 is None:
            secret_b58 = base58.b58encode(bytes(secret_json)).decode()

        wallet = WalletExport(
            address=addr,
            private_key_base58_64=secret_b58,
            private_key_json_64=secret_json,
            public_key_hex=pub32.hex(),
            private_key_hex_32=priv32.hex(),
        )
        # L'id sera généré automatiquement via __post_init__
        imported.append(wallet)
    project.wallets.extend(imported)
    return imported

def move_project_to_trash(project_dir: Path, data_dir: Path) -> None:
    trash = data_dir / ".trash"
    trash.mkdir(parents=True, exist_ok=True)
    target = trash / project_dir.name
    # éviter collisions en ajoutant un suffixe numérique si besoin
    i = 1
    while target.exists():
        target = trash / f"{project_dir.name}-{i}"
        i += 1
    project_dir.rename(target)
