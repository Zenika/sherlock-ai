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

    Le prompt système est chargé depuis case/prompts/{id}.md. Le contexte
    général de l'affaire (case.json) est injecté en en-tête du prompt.
    """
    import case_loader

    system_prompt = case_loader.load_suspect_prompt(suspect["id"])
    if system_prompt is None:
        return (
            f"[Persona non disponible pour {suspect['nom']} — "
            f"fichier case/prompts/{suspect['id']}.md introuvable]"
        )

    if case.get("resume_public"):
        system_prompt = f"[AFFAIRE : {case.get('titre', '')} — {case['resume_public']}]\n\n{system_prompt}"

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
    except Exception as exc:  # noqa: BLE001
        return (
            f"[Le suspect reste silencieux — le service d'interrogatoire est indisponible : {exc}]"
        )
