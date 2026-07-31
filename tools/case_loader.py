"""Chargement des données de l'enquête depuis le dossier `case/`.

Toute l'enquête est pilotée par les données : pour créer une nouvelle affaire,
il suffit d'éditer les fichiers de `case/` sans toucher au code.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# Emplacement du dossier de l'enquête. Surchageable via la variable
# d'environnement CASE_DIR (utile en conteneur).
CASE_DIR = Path(os.environ.get("CASE_DIR", Path(__file__).resolve().parent.parent / "case"))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def load_case() -> dict[str, Any]:
    """Métadonnées de l'affaire (case.json)."""
    return _read_json(CASE_DIR / "case.json")


@lru_cache(maxsize=1)
def load_suspects() -> list[dict[str, Any]]:
    """Construit la liste des suspects depuis les fichiers de prompts disponibles."""
    prompts_dir = CASE_DIR / "prompts"
    if not prompts_dir.exists():
        return []
    suspects = []
    for path in sorted(prompts_dir.glob("*.md")):
        suspect_id = path.stem
        content = path.read_text(encoding="utf-8")
        # Chercher le nom uniquement dans la section IDENTITÉ pour éviter
        # les faux-positifs du header ("Tu es actuellement dans une salle...").
        section = re.search(r"### 1\..*?IDENTIT.*?\n(.*?)(?=###|\Z)", content, re.DOTALL | re.IGNORECASE)
        search_in = section.group(1) if section else content
        m = re.search(r"Tu es ([^,\.\n\(]+)", search_in)
        nom = m.group(1).strip() if m else suspect_id
        suspects.append({"id": suspect_id, "nom": nom})
    return suspects


@lru_cache(maxsize=1)
def load_camera_logs() -> list[dict[str, Any]]:
    """Logs des caméras de surveillance (camera_logs.json)."""
    return _read_json(CASE_DIR / "camera_logs.json")


def get_suspect(identifiant: str) -> dict[str, Any] | None:
    """Retrouve un suspect par son id, prénom, nom ou extrait de nom."""
    besoin = identifiant.strip().lower()
    suspects = load_suspects()
    # 1. Correspondance exacte sur id ou nom complet.
    for s in suspects:
        if s["id"].lower() == besoin or s["nom"].lower() == besoin:
            return s
    # 2. Le terme est contenu dans le nom (ex: "sophie" dans "Sophie Duval").
    for s in suspects:
        if besoin in s["nom"].lower():
            return s
    # 3. Un mot du terme est contenu dans le nom (ex: "duval" ou "mme sophie duval").
    mots = [m for m in re.split(r"[\s_\-]+", besoin) if len(m) > 2]
    for mot in mots:
        for s in suspects:
            if mot in s["nom"].lower() or mot == s["id"].lower():
                return s
    return None


def list_suspects_publics() -> list[dict[str, str]]:
    """Vue publique des suspects (sans les secrets ni la solution)."""
    return [
        {"id": s["id"], "nom": s["nom"]}
        for s in load_suspects()
    ]


def list_documents() -> list[dict[str, str]]:
    """Liste des documents disponibles dans case/documents."""
    docs_dir = CASE_DIR / "documents"
    documents: list[dict[str, str]] = []
    if not docs_dir.exists():
        return documents
    for path in sorted(p for p in docs_dir.iterdir() if p.suffix in (".md", ".json")):
        titre = path.stem
        if path.suffix == ".md":
            try:
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
                if first_line.startswith("#"):
                    titre = first_line.lstrip("# ").strip()
            except (OSError, IndexError):
                pass
        documents.append({"reference": path.stem, "titre": titre})
    return documents


def load_suspect_prompt(suspect_id: str) -> str | None:
    """Charge le prompt système d'un suspect depuis case/prompts/{id}.md.

    Les prompts système sont stockés en dehors du code Python, dans des fichiers
    Markdown dédiés. Pour modifier le comportement d'un personnage, éditez
    uniquement le fichier correspondant dans case/prompts/ sans toucher au code.
    """
    prompt_file = CASE_DIR / "prompts" / f"{suspect_id.strip().lower()}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return None


def _normalize_ref(s: str) -> str:
    """Dépluralise chaque segment pour une recherche flexible (ex: guests_list → guest_list)."""
    return "_".join(w.rstrip("s") for w in s.split("_"))


def read_document(reference: str) -> str | None:
    """Renvoie le contenu d'un document par sa référence (nom de fichier sans extension)."""
    ref = reference.strip().lower().removesuffix(".md").removesuffix(".json")
    docs_dir = CASE_DIR / "documents"
    if not docs_dir.exists():
        return None
    candidates = [p for p in docs_dir.iterdir() if p.suffix in (".md", ".json")]

    def _match(ref_key: str) -> str | None:
        # Correspondance exacte, .md prioritaire sur .json.
        for suffix in (".md", ".json"):
            for path in candidates:
                if path.suffix == suffix and path.stem.lower() == ref_key:
                    return path.read_text(encoding="utf-8")
        # Correspondance partielle.
        for suffix in (".md", ".json"):
            for path in candidates:
                if path.suffix == suffix and ref_key in path.stem.lower():
                    return path.read_text(encoding="utf-8")
        return None

    result = _match(ref)
    if result is None:
        # Deuxième passe avec normalisation (dépluralisation).
        result = _match(_normalize_ref(ref))
    return result
