"""Serveur MCP « Sherlock AI ».

Outils d'investigation disponibles :
- interroger_suspect  — dialogue agent-to-agent avec un suspect joué par un LLM
- get_document        — accès à un document du dossier par son nom
- cctv                — consultation des logs caméra avec filtres optionnels

Transport stdio : le serveur est lancé par `mcpo`, qui l’expose ensuite
en OpenAPI pour Open WebUI.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

import case_loader
from llm import interroger_suspect_llm

mcp = FastMCP("sherlock-ai")

CASE_DIR = Path(os.environ.get("CASE_DIR", Path(__file__).resolve().parent.parent / "case"))


@mcp.tool()
def interroger_suspect(nom_suspect: str, question: str) -> str:
    """Interroge un suspect en tête-à-tête. 

    Args:
        nom_suspect: prénom, nom complet ou identifiant du suspect.
        question: la question posée par l'enquêteur.
    """
    suspect = case_loader.get_suspect(nom_suspect)
    if suspect is None:
        # Ne jamais révéler la liste des suspects existants : une mauvaise
        # requête ne doit donner aucun indice à l'enquêteur.
        return f"Aucun suspect nommé « {nom_suspect} » n'a été trouvé."
    case = case_loader.load_case()
    reponse = interroger_suspect_llm(suspect, case, question)
    return f"**{suspect['nom']}** répond :\n\n{reponse}"


@mcp.tool()
def get_document(nom: str) -> str:
    """Accède à un document du dossier d'enquête par son nom.

    Args:
        nom: nom du document demandé (ex: "liste_invite", "rapport").
    """
    nom_clean = nom.strip().lower()

    contenu = case_loader.read_document(nom_clean)
    if contenu is None:
        # Ne jamais révéler la liste des documents existants : une mauvaise
        # requête ne doit donner aucun indice à l'enquêteur.
        return f"Document « {nom} » introuvable."
    return contenu


@mcp.tool()
def cctv(camera: str = "", heure_debut: str = "", heure_fin: str = "") -> str:
    """Consulte les enregistrements des caméras de surveillance.

    Args:
        camera: filtre sur le nom ou l'emplacement de la caméra
                (ex: "bar", "grille").
        heure_debut: heure de début au format HH:MM (ex: "21:45"). 
        heure_fin:   heure de fin au format HH:MM (ex: "22:10"). 
    """
    cctv_path = CASE_DIR / "camera_logs.json"
    if not cctv_path.exists():
        return "[Logs CCTV indisponibles — fichier case/camera_logs.json introuvable]"

    try:
        logs: list[dict] = json.loads(cctv_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"[Erreur de lecture des logs CCTV : {exc}]"

    def to_minutes(ts: str) -> int | None:
        # Accepte HH:MM, HH:MM:SS et HHhMM.
        ts = ts.strip()
        if not ts:
            return None
        parts = ts.replace("h", ":").split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None

    # Certains clients LLM envoient la plage dans un seul champ ("12:00->00:00").
    if not heure_fin and "->" in heure_debut:
        heure_debut, heure_fin = heure_debut.split("->", 1)

    debut = to_minutes(heure_debut)
    fin   = to_minutes(heure_fin)

    # 00:00 comme borne de fin signifie fin de journée, pas minuit passé.
    if fin == 0 and heure_fin.strip():
        fin = 1440
    # Si fin < debut (ex: 12:00 → 00:00 non corrigé), on wrappe sur 24h.
    if debut is not None and fin is not None and fin < debut:
        fin += 1440
    filtre_camera = camera.strip().lower()

    resultats = []
    for log in logs:
        cam_id = str(log.get("camera_id", "")).lower()
        location = str(log.get("location", "")).lower()
        if filtre_camera and filtre_camera not in cam_id and filtre_camera not in location:
            continue
        t = to_minutes(str(log.get("timestamp", "")))
        if debut is not None and (t is None or t < debut):
            continue
        if fin is not None and (t is None or t > fin):
            continue
        heure_affichee = log.get("timestamp", "?")[:5]
        resultats.append(
            f"- `{heure_affichee}` — **{log.get('camera_id', '?')}** ({log.get('location', '?')}) : {log.get('description', '')}"
        )

    if not resultats:
        return "Aucun enregistrement ne correspond aux critères demandés."

    entete = "## Enregistrements CCTV"
    if filtre_camera:
        entete += f" — caméra : « {camera} »"
    if heure_debut or heure_fin:
        entete += f" — {heure_debut or '?'}→{heure_fin or '?'}"
    return entete + "\n" + "\n".join(resultats)


if __name__ == "__main__":
    mcp.run()
