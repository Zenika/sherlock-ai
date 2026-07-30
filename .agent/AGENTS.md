# Sherlock AI — Agent Instructions

Serious game d'enquête policière piloté par IA. Les joueurs (enquêteurs) interrogent des suspects
joués par un LLM, consultent des documents et des vidéos de surveillance pour résoudre une affaire.

## Stack en un coup d'œil

| Service | Image/build | Port | Rôle |
|---------|-------------|------|------|
| `openwebui` | `ghcr.io/open-webui/open-webui:main` | 3000 | Interface enquêteur |
| `tools` | build `./tools/` | 8000 | Serveur MCP → OpenAPI via mcpo |
| `bootstrap` | `python:3.12-slim` (one-shot) | — | Crée les comptes au 1er boot |

## Commandes essentielles

```bash
# Démarrer le daemon Docker (macOS, utilise Colima — pas Docker Desktop)
colima start

# Lancer toute la stack
docker-compose up -d --build

# Rebuilder uniquement les outils (après modif de tools/ ou case/)
docker-compose up -d --build tools

# Redémarrer OpenWebUI (après modif de .env)
docker-compose up -d openwebui

# Voir les logs d'un service
docker logs sherlock-tools
docker logs sherlock-openwebui
docker logs sherlock-bootstrap

# Relancer le bootstrap (si comptes perdus)
docker-compose run --rm bootstrap
```

> **Important macOS** : utiliser `docker-compose` (avec tiret, v5.2.0) et non `docker compose`.
> La variable zsh `$path` est liée à `$PATH` — ne jamais l'utiliser comme variable de boucle.

## Les 3 outils MCP exposés

| Tool | Paramètres | Source de données |
|------|-----------|-------------------|
| `interroger_suspect` | `nom_suspect`, `question` | LLM (prompt depuis `case/prompts/{id}.md`) |
| `get_document` | `nom` | `case/documents/{nom}.md` |
| `cctv` | `camera`, `heure_debut`, `heure_fin` | `case/cctv_logs.json` |

## Ajouter/modifier du contenu sans toucher au code

```
case/
├── case.json              ← méta-données de l'affaire (titre, résumé, solution)
├── suspects.json          ← liste des suspects (id, nom, role) — pas de prompts ici
├── cctv_logs.json         ← logs caméra (id, camera, heure HH:MM, description)
├── prompts/
│   ├── ambrine.md         ← system prompt verbatim du personnage
│   ├── alexandre.md
│   └── ...                ← un fichier par suspect (id = nom du fichier)
└── documents/
    ├── accounts.md        ← 8 documents fixes
    ├── autopsy.md
    └── ...
```

**Nouvelle enquête** : éditer les fichiers `case/`, puis `docker-compose restart tools`.  
**Nouveau personnage** : ajouter `case/prompts/{id}.md` + entrée dans `suspects.json`.

## Configuration dans `.env`

| Variable | Rôle |
|----------|------|
| `OPENAI_API_BASE_URLS` | URL(s) provider LLM pour OpenWebUI (`;`-séparés) |
| `OPENAI_API_KEYS` | Clés associées (même ordre) |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Provider qui joue les suspects (MCP) |
| `MCPO_API_KEY` | Clé d'auth mcpo → OpenWebUI |
| `ENABLE_MODEL_FILTER` | `true` = filtre les modèles vus par les enquêteurs |
| `MODEL_FILTER_LIST` | Modèles autorisés aux enquêteurs (`;`-séparés) |
| `DEFAULT_MODELS` | Modèle présélectionné par défaut |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Compte administrateur |
| `INVESTIGATOR_COUNT` / `INVESTIGATOR_PASSWORD` | Comptes enquêteurs génériques |

Après tout changement de `.env` : `docker-compose up -d openwebui` (ou `tools` selon la variable).

## Fichiers à ne pas modifier sans raison

- `case/prompts/*.md` — system prompts verbatim fournis par le game designer, ne pas reformater
- `bootstrap/init_accounts.py` — logique d'enregistrement du tool server dans OpenWebUI (bugs subtils, voir `.agent/gotchas.md`)
- `tools/requirements.txt` — contrainte de version critique `mcp>=1.9.0,<2.0.0`
