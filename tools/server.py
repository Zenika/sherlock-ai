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
    """Interroge un suspect. Le suspect est joué par une IA et répond en
    personnage : il peut mentir, se contredire ou dissimuler des informations.

    Args:
        nom_suspect: nom ou identifiant du suspect (ex: "Dr Finch" ou "finch").
        question: la question posée par l'enquêteur.
    """
    suspect = case_loader.get_suspect(nom_suspect)
    if suspect is None:
        dispo = ", ".join(s["nom"] for s in case_loader.list_suspects_publics())
        return (
            f"Aucun suspect nommé « {nom_suspect} » n'a été trouvé. "
            f"Suspects disponibles : {dispo}."
        )
    case = case_loader.load_case()
    reponse = interroger_suspect_llm(suspect, case, question)
    return f"**{suspect['nom']}** répond :\n\n{reponse}"


@mcp.tool()
def get_document(nom: str) -> str:
    """Accède à un document du dossier d'enquête par son nom.

    Documents disponibles : mails, expertise, autopsy, accounts,
    guest_list, staff_list, briefing, camera.

    Args:
        nom: nom du document demandé (ex: "autopsy", "mails").
             Si vide ou égal à "list", renvoie la liste des documents disponibles.
    """
    nom_clean = nom.strip().lower()
    if not nom_clean or nom_clean == "list":
        docs = case_loader.list_documents()
        if not docs:
            return "Aucun document disponible dans le dossier."
        lignes = [f"- `{d['reference']}`" for d in docs]
        return "## Documents disponibles\n" + "\n".join(lignes)

    contenu = case_loader.read_document(nom_clean)
    if contenu is None:
        docs = case_loader.list_documents()
        dispo = ", ".join(f"`{d['reference']}`" for d in docs)
        return f"Document « {nom} » introuvable. Documents disponibles : {dispo}."
    return contenu


@mcp.tool()
def cctv(camera: str = "", heure_debut: str = "", heure_fin: str = "") -> str:
    """Consulte les enregistrements des caméras de surveillance.

    Args:
        camera: filtre optionnel sur le nom ou l'emplacement de la caméra
                (ex: "bar", "grille"). Si vide, toutes les caméras sont incluses.
        heure_debut: heure de début au format HH:MM (ex: "21:45"). Si vide, pas
                     de borne inférieure.
        heure_fin:   heure de fin au format HH:MM (ex: "22:10"). Si vide, pas
                     de borne supérieure.
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

    debut = to_minutes(heure_debut)
    fin = to_minutes(heure_fin)
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
