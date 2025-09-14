
# -*- coding: utf-8 -*-
from pathlib import Path
from typing import Optional, List

def iter_project_dirs(base: str | Path) -> List[Path]:
    base = Path(base)
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "project.json").exists()]

def find_project_dir(base: str | Path, project_id: str) -> Optional[Path]:
    for p in iter_project_dirs(base):
        if p.name.startswith(project_id + "_"):
            return p
    return None
