# Architecture détaillée

## Flux de données

```
Joueur (navigateur)
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  OpenWebUI :3000                                        │
│  - Interface chat                                       │
│  - Gestion des comptes (admin/enquêteurs)               │
│  - Connexion aux providers LLM (OpenAI-compatible)      │
│  - Consomme le tool server mcpo via OpenAPI             │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP + Bearer MCPO_API_KEY
               ▼
┌─────────────────────────────────────────────────────────┐
│  mcpo :8000  (dans l'image tools)                       │
│  - Proxy MCP → OpenAPI                                  │
│  - Lance server.py en transport stdio                   │
│  - Auto-génère le schema OpenAPI depuis les @mcp.tool() │
│  - Route /openapi.json (schéma)                         │
│  - Route /docs (Swagger UI)                             │
└──────────────┬──────────────────────────────────────────┘
               │ stdio (subprocess)
               ▼
┌─────────────────────────────────────────────────────────┐
│  server.py (FastMCP)                                    │
│  ├── interroger_suspect() → llm.py                      │
│  │     └── LLM_BASE_URL (appel OpenAI-compatible)       │
│  ├── get_document()       → case/documents/{nom}.md     │
│  └── cctv()               → case/cctv_logs.json         │
└──────────────────────────────────────────────────────────┘
```

## Enregistrement du tool server dans OpenWebUI

OpenWebUI ne pré-charge pas les tool servers au démarrage : ils doivent être
enregistrés via l'API. Le bootstrap le fait automatiquement :

```
POST /api/v1/configs/tool_servers
Authorization: Bearer <token admin>
{
  "TOOL_SERVER_CONNECTIONS": [{
    "url": "http://tools:8000",
    "path": "/openapi.json",
    "type": "openapi",
    "auth_type": "bearer",
    "key": "<MCPO_API_KEY>",
    "config": {"enable": true},   // ← OBLIGATOIRE (voir gotchas.md)
    "info": {}                    // ← OBLIGATOIRE (voir gotchas.md)
  }]
}
```

Après ce POST, OpenWebUI appelle `set_tool_servers()` qui va chercher le schema
et peuple `app.state.TOOL_SERVERS`. Ce cache est utilisé à chaque appel de chat.

## Chargement des prompts suspects

```
interroger_suspect("ambrine", "Où étiez-vous...")
  └─ case_loader.get_suspect("ambrine")
       └─ suspects.json → {"id": "ambrine", "nom": "...", "role": "..."}
  └─ case_loader.load_suspect_prompt("ambrine")
       └─ case/prompts/ambrine.md → contenu verbatim (system prompt)
  └─ llm.interroger_suspect_llm(suspect, case, question)
       └─ OpenAI(base_url=LLM_BASE_URL).chat.completions.create(
            model=LLM_MODEL,
            messages=[
              {"role": "system", "content": <contenu ambrine.md>},
              {"role": "user", "content": question}
            ]
          )
```

Le prompt est lu depuis le fichier à chaque appel (pas de cache) → les
modifications de `case/prompts/*.md` sont effectives après un `restart tools`.

## Réseau Docker interne

- `openwebui` contacte `tools` via `http://tools:8000` (réseau interne compose).
- `tools` contacte `LLM_BASE_URL` (réseau externe, le LLM provider).
- `bootstrap` contacte `openwebui` via `http://openwebui:8080` (port interne 8080, mappé sur 3000 côté host).
- Depuis le host : OpenWebUI = `localhost:3000`, tools = `localhost:8000`.

## Volumes persistants

- `openwebui-data` : base SQLite OpenWebUI (comptes, paramètres, historiques, config tool server).
  Le bootstrap ne recrée pas les comptes si ce volume existe.
  La config du tool server (`/api/v1/configs/tool_servers`) est stockée dans ce volume.

## Modèle d'accès LLM (agnostique provider)

OpenWebUI supporte plusieurs connexions OpenAI-compatible simultanées :
```
OPENAI_API_BASE_URLS=https://api.openai.com/v1;https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_API_KEYS=sk-openai-xxx;AIza-gemini-xxx
```
Le MCP tools utilise une connexion séparée (`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`),
indépendante d'OpenWebUI — ce qui permet d'utiliser un modèle différent (moins cher) pour
jouer les suspects.
