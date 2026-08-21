# 🕵️ Sherlock AI — Serious game d'enquête piloté par IA

Un jeu d'enquête où les joueurs mènent l'investigation à l'aide d'une IA. Ils
interrogent des suspects (joués dynamiquement par un LLM), consultent les pièces
du dossier et examinent les enregistrements de vidéosurveillance pour démasquer
le coupable.

L'ensemble est packagé avec **Docker Compose** : une seule commande pour tout
lancer. Toute la configuration — clés de licence, comptes, modèles — tient dans
un unique fichier `.env`.

## 🧩 Architecture

```
Joueur (navigateur)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Open WebUI :3000                                       │
│  Interface enquêteur — agnostique du provider LLM       │
└──────────────┬──────────────────────────────────────────┘
               │ HTTP + MCPO_API_KEY
               ▼
┌─────────────────────────────────────────────────────────┐
│  tools :8000  (mcpo → serveur MCP stdio)                │
│  • interroger_suspect   agent-to-agent : LLM joue les suspects
│  • get_document         lit case/documents/{nom}.md     │
│  • cctv                 filtre case/cctv_logs.json      │
└──────────────┬──────────────────────────────────────────┘
               │ OpenAI-compatible (LLM_BASE_URL)
               ▼
          Provider LLM (suspects)
```

- **Open WebUI** : interface des enquêteurs, connexion à un ou plusieurs providers LLM.
- **tools** : serveur MCP exposé en OpenAPI par [`mcpo`](https://github.com/open-webui/mcpo). 3 outils disponibles.
- **bootstrap** : crée admin + comptes enquêteurs + enregistre le tool server + publie les modèles.
- **case/** : tout le contenu de l'enquête — modifiable sans toucher au code.

## 🚀 Démarrage rapide

### 1. Prérequis

```bash
# macOS — démarrer le daemon Docker (Colima)
colima start
```

### 2. Configurer `.env`

```bash
cp .env.example .env
```

Renseignez au minimum :

| Variable | Description |
|----------|-------------|
| `OPENAI_API_BASE_URLS` | URL du provider LLM pour l'interface (ex: `https://api.openai.com/v1`) |
| `OPENAI_API_KEYS` | Clé(s) API associée(s) |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Provider qui joue les suspects |
| `MCPO_API_KEY` | Clé protégeant les outils MCP |
| `WEBUI_SECRET_KEY` | Clé de session OpenWebUI (chaîne aléatoire longue) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Compte administrateur |
| `INVESTIGATOR_PASSWORD` | Mot de passe commun des enquêteurs |
| `ENABLED_MODELS` | Modèles visibles aux enquêteurs (séparés par `;`) |
| `REASONING_MODELS` | Sous-ensemble de `ENABLED_MODELS` nécessitant `reasoning_effort="none"` (modèles reasoning type o1/o3/gpt-5.x) |

### 3. Lancer

```bash
docker-compose up -d --build
```

Au premier démarrage, le bootstrap crée automatiquement :
- le compte admin
- les comptes enquêteurs (`enqueteur1@sherlock.local` … `enqueteurN@sherlock.local`)
- le tool server dans Open WebUI
- les entrées de modèles publics listés dans `ENABLED_MODELS`

### 4. Accéder

| Rôle | URL | Identifiants |
|------|-----|-------------|
| Interface enquêteur | http://localhost:3000 | `enqueteur1@sherlock.local` / `INVESTIGATOR_PASSWORD` |
| Admin | http://localhost:3000 | `ADMIN_EMAIL` / `ADMIN_PASSWORD` |
| Docs outils MCP | http://localhost:8000/docs | clé : `MCPO_API_KEY` |

## 🗂️ Contenu de l'enquête

Tout est piloté par les données dans `case/` — aucun code à modifier.

```
case/
├── case.json          ← méta-données + solution (réservée à l'animateur)
├── suspects.json      ← liste des suspects (id, nom, rôle)
├── cctv_logs.json     ← logs caméra (heure HH:MM, caméra, description)
├── prompts/           ← system prompts verbatim des personnages (1 fichier par suspect)
│   ├── ambrine.md
│   └── ...
└── documents/         ← 8 documents du dossier
    ├── accounts.md    mails.md     expertise.md   autopsy.md
    ├── briefing.md    camera.md    guest_list.md  staff_list.md
```

**Modifier un document** : éditer `case/documents/{nom}.md`, puis `docker-compose restart tools`.

**Modifier un personnage** : éditer `case/prompts/{id}.md` (sans rien reformater), puis `docker-compose restart tools`.

**Nouvelle enquête** : remplacer les fichiers `case/`, puis `docker-compose restart tools`.

## 🛠️ Outils MCP disponibles

| Outil | Paramètres | Rôle |
|-------|-----------|------|
| `interroger_suspect` | `nom_suspect`, `question` | Dialogue agent-to-agent — le suspect répond en personnage (peut mentir) |
| `get_document` | `nom` | Lit un document (`mails`, `autopsy`, `accounts`, etc.) |
| `cctv` | `camera`, `heure_debut`, `heure_fin` | Filtre les enregistrements caméra |

## 🎚️ Gérer les modèles accessibles aux enquêteurs

Les enquêteurs voient uniquement les modèles listés dans `ENABLED_MODELS` (`.env`).

```ini
# Exemple : 3 modèles, du plus léger au plus puissant
ENABLED_MODELS=gpt-4o-mini;gpt-4o;gpt-5-mini
DEFAULT_MODELS=gpt-4o-mini
# gpt-5-mini est un modèle reasoning : reasoning_effort="none" lui est appliqué
# automatiquement (requis pour compatibilité avec le tool calling). Ne pas
# mettre gpt-4o/gpt-4o-mini ici, ce paramètre casse ces modèles.
REASONING_MODELS=gpt-5-mini
```

**Ajouter ou modifier les modèles disponibles** :
1. Mettre à jour `ENABLED_MODELS` dans `.env` (une seule ligne, pas de doublon)
2. `docker-compose run --rm bootstrap`

**Régler la difficulté** (sans toucher au `.env`) : Admin → Modèles → activer/désactiver.

## 🔄 Changer de provider LLM

**Interface enquêteur** — dans `.env` :
```ini
OPENAI_API_BASE_URLS=https://api.openai.com/v1
OPENAI_API_KEYS=sk-...
```
Plusieurs providers séparés par `;`. Puis `docker-compose up -d openwebui`.

**Suspects (agent-to-agent)** — dans `.env` :
```ini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```
Puis `docker-compose up -d tools`.

Endpoints compatibles OpenAI courants :

| Provider | URL |
|----------|-----|
| OpenAI | `https://api.openai.com/v1` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| Anthropic | `https://api.anthropic.com/v1` (mode compat) |

## 🔒 Sécurité

- Les system prompts des suspects sont durcis contre le jailbreak.
- La solution (`case.json → solution`) n'est **jamais** transmise aux suspects ni au LLM.
- Le tool server est protégé par `MCPO_API_KEY`.
- Les inscriptions publiques sont désactivées (`ENABLE_SIGNUP=false`).

## 📋 Commandes utiles

```bash
# Démarrer le daemon Docker (macOS / Colima)
colima start

# Première installation ou rebuild après modif de code
docker-compose up -d --build

# Appliquer un changement de .env (OpenWebUI)
docker-compose up -d openwebui

# Appliquer un changement de contenu (case/) ou de code (tools/)
docker-compose restart tools

# Ajouter/modifier les modèles publics ou recréer les comptes
docker-compose run --rm bootstrap

# Voir les logs d'un service
docker logs sherlock-tools
docker logs sherlock-openwebui
docker logs sherlock-bootstrap
```

> Pour plus de détails sur l'architecture, les bugs connus et comment créer de nouveaux scénarios, consultez [.agent/](.agent/).
