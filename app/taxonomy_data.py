from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.paths import taxonomy_dir


@lru_cache
def load_section_taxonomy(path: Path | None = None) -> dict[str, list[str]]:
    target = path or (taxonomy_dir() / "sections.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    raw = payload.get("canonical_sections", {})
    return {str(key): [str(alias).lower() for alias in aliases] for key, aliases in raw.items()}


@lru_cache
def load_skill_taxonomy(path: Path | None = None) -> list[dict[str, object]]:
    target = path or (taxonomy_dir() / "skills.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    skills = payload.get("skills", [])
    return list(skills)


def skill_alias_map() -> dict[str, tuple[str, str | None]]:
    mapping: dict[str, tuple[str, str | None]] = {}
    for item in load_skill_taxonomy():
        canonical = str(item["canonical_skill"])
        category = item.get("category")
        category_s = str(category) if category else None
        aliases = item.get("aliases") or []
        if not isinstance(aliases, list):
            continue
        for alias in [canonical, *aliases]:
            mapping[str(alias).strip().lower()] = (canonical, category_s)
    return mapping
