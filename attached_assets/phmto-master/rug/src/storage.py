# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path
from typing import Dict

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)

def write_json(path: Path, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try: os.chmod(path, 0o600)
    except Exception: pass

def write_text(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    try: os.chmod(path, 0o600)
    except Exception: pass

def read_json(path: Path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
