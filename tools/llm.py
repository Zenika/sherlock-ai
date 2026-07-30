"""Client LLM agnostique du provider pour faire « jouer » les suspects.

Le serveur MCP agit comme un agent-to-agent : quand l'enquêteur interroge un
suspect, ce module appelle un LLM (via un endpoint compatible OpenAI) avec la
persona du suspect pour générer une réponse en personnage.

Provider-agnostique : fonctionne avec OpenAI, Gemini (endpoint /openai),
Anthropic (endpoint compat), Groq, vLLM, Ollama, ou une passerelle LiteLLM,
tant que l'endpoint est compatible OpenAI. Se configure par variables
d'environnement :

- LLM_BASE_URL : URL de base compatible OpenAI (ex: https://api.openai.com/v1)
- LLM_API_KEY  : clé d'API du provider
- LLM_MODEL    : identifiant du modèle (ex: gpt-4o-mini)
"""
from __future__ import annotations

import os
from typing import Any

from openai import OpenAI

_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")


def _client() -> OpenAI:
    base_url = os.environ.get("LLM_BASE_URL") or None
    api_key = os.environ.get("LLM_API_KEY", "")
    return OpenAI(base_url=base_url, api_key=api_key)


def interroger_suspect_llm(
    suspect: dict[str, Any],
    case: dict[str, Any],
    question: str,
) -> str:
    """Appelle le LLM pour générer la réponse du suspect à une question.

    Le prompt système est chargé depuis case/prompts/{id}.md — il n'est jamais
    codé en dur dans ce fichier. Pour modifier un personnage, éditez uniquement
    son fichier de prompt.
    """
    import case_loader

    system_prompt = case_loader.load_suspect_prompt(suspect["id"])
    if system_prompt is None:
        return (
            f"[Persona non disponible pour {suspect['nom']} — "
            f"fichier case/prompts/{suspect['id']}.md introuvable]"
        )

    try:
        response = _client().chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.8,
            max_tokens=600,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - on renvoie une erreur lisible au jeu
        return (
            f"[Le suspect reste silencieux — le service d'interrogatoire est indisponible : {exc}]"
        )


def interroger_suspect_llm(
    suspect: dict[str, Any],
    case: dict[str, Any],
    question: str,
) -> str:
    """Appelle le LLM pour générer la réponse du suspect à une question."""
    system_prompt = _build_system_prompt(suspect, case)
    try:
        response = _client().chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0.8,
            max_tokens=400,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 - on renvoie une erreur lisible au jeu
        return (
            f"[Le suspect reste silencieux — le service d'interrogatoire est indisponible : {exc}]"
        )
