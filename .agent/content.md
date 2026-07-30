# Guide : modifier le contenu du scénario

Toute la logique de jeu est pilotée par les données dans `case/`. Aucun code Python à modifier.

## Structure de `case/`

```
case/
├── case.json              ← méta-données et solution (réservée à l'animateur)
├── suspects.json          ← liste publique des suspects
├── cctv_logs.json         ← enregistrements caméra
├── prompts/               ← system prompts verbatim (1 fichier par suspect)
│   ├── ambrine.md
│   ├── alexandre.md
│   ├── sophie.md
│   ├── charles.md
│   ├── frank.md
│   ├── thomas.md
│   ├── julien.md
│   └── marc.md
└── documents/             ← 8 documents du dossier
    ├── accounts.md
    ├── autopsy.md
    ├── briefing.md
    ├── camera.md
    ├── expertise.md
    ├── guest_list.md
    ├── mails.md
    └── staff_list.md
```

## Modifier le contenu d'un document

Éditer directement `case/documents/{nom}.md`, puis :
```bash
docker-compose restart tools
```

## Modifier le prompt d'un personnage

Éditer `case/prompts/{id}.md` **sans reformater ni modifier** le contenu.
Ces fichiers sont fournis tels quels par le game designer.  
```bash
docker-compose restart tools
```

## Créer un nouveau personnage

1. Ajouter une entrée dans `case/suspects.json` :
   ```json
   {"id": "nouveau", "nom": "Prénom Nom", "role": "Rôle dans l'histoire"}
   ```
2. Créer `case/prompts/nouveau.md` avec le system prompt complet.
3. `docker-compose restart tools`

L'identifiant `id` doit être en minuscules sans espaces. Il sert à :
- trouver le fichier prompt (`case/prompts/{id}.md`)
- permettre l'interrogation par l'enquêteur (`interroger_suspect("nouveau", "...")`)

## Format de `case/suspects.json`

```json
{
  "suspects": [
    {"id": "string", "nom": "Nom affiché", "role": "Description du rôle"}
  ]
}
```
Pas de champs de jeu ici. Tout le comportement est dans `case/prompts/{id}.md`.

## Format de `case/cctv_logs.json`

```json
[
  {
    "id": "cam-01",
    "camera": "Nom / lieu de la caméra",
    "heure": "HH:MM",
    "description": "Ce que montre l'enregistrement."
  }
]
```

- `heure` doit être au format `HH:MM` (ex: `"21:45"`, `"22:05"`).
- L'outil `cctv` filtre sur `camera` (substring insensible à la casse) et sur la plage horaire.
- Plusieurs entrées pour la même caméra sont normales.

## Format de `case/case.json`

Champs utilisés par le code :
- `titre` — nom de l'affaire
- `resume_public` — ce que tout le monde sait (injecté dans aucun prompt depuis la migration)
- `heure_du_crime`, `lieu_du_crime` — idem
- `briefing_enqueteur` — consignes générales
- `solution` — réservé à l'animateur, **jamais transmis aux suspects ni au LLM**

## Changer de provider LLM

**Pour OpenWebUI (interface enquêteur)** — dans `.env` :
```ini
OPENAI_API_BASE_URLS=https://api.openai.com/v1
OPENAI_API_KEYS=sk-...
```
Puis `docker-compose up -d openwebui`.

**Pour le MCP (suspects)** — dans `.env` :
```ini
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
```
Puis `docker-compose up -d tools`.

## Régler la difficulté (modèles accessibles aux enquêteurs)

Dans `.env` :
```ini
ENABLE_MODEL_FILTER=true
MODEL_FILTER_LIST=gpt-4o-mini            # modèle facile uniquement
# MODEL_FILTER_LIST=gpt-4o-mini;gpt-4o  # ou les deux
DEFAULT_MODELS=gpt-4o-mini
```
Puis `docker-compose up -d openwebui`. L'admin voit toujours tous les modèles.

## Comptes joueurs

- Admin : `ADMIN_EMAIL` / `ADMIN_PASSWORD`
- Enquêteurs : `enqueteur1@sherlock.local` … `enqueteurN@sherlock.local` / `INVESTIGATOR_PASSWORD`
- `INVESTIGATOR_COUNT` contrôle le nombre de comptes créés au bootstrap.

Pour ajouter des comptes sans recréer le volume : relancer le bootstrap avec un `INVESTIGATOR_COUNT`
plus grand. Le bootstrap est idempotent (il saute les comptes existants).
```bash
docker-compose run --rm bootstrap
```
