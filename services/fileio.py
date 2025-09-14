# -*- coding: utf-8 -*-
# services/fileio.py
# -*- coding: utf-8 -*-
import json, os, tempfile
from pathlib import Path
from typing import Any

def ensure_dir(p: Path) -> None:
    """Crée le dossier parent si besoin."""
    p.mkdir(parents=True, exist_ok=True)

def atomic_write_json(path: Path, data: Any) -> None:
    """
    Écriture atomique d'un fichier JSON :
    - écrit d'abord dans un fichier temporaire
    - puis remplace le fichier final par os.replace()
    """
    ensure_dir(path.parent)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise
