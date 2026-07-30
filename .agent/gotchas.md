# Bugs connus et contraintes critiques

## 1. `mcp` 2.x incompatible avec `mcpo` 0.0.20

**Symptôme** : `sherlock-tools` crashe en boucle (Restarting).
```
ImportError: cannot import name 'streamablehttp_client' from 'mcp.client.streamable_http'
```
**Cause** : `mcp` 2.0 a renommé l'API interne que `mcpo` utilise.  
**Fix** : `tools/requirements.txt` épingle `mcp>=1.9.0,<2.0.0`. **Ne pas retirer cette contrainte.**

---

## 2. Tool server ignoré silencieusement si `config.enable` absent

**Symptôme** : OpenWebUI montre le tool server dans les intégrations mais aucun outil n'apparaît.  
**Cause** : `get_tool_servers_data()` dans OpenWebUI vérifie `server.get('config', {}).get('enable')`.
Avec `config: {}` (dict vide), `enable` est absent → falsy → le serveur est sauté sans erreur.  
**Fix** : toujours envoyer `"config": {"enable": true}` dans la payload d'enregistrement.

---

## 3. `info: null` provoque un crash silencieux dans `set_tool_servers`

**Symptôme** : log OpenWebUI `'NoneType' object has no attribute 'get'` dans `set_tool_servers`.
Aucun outil chargé.  
**Cause** : `info = server.get('info', {})` retourne `None` quand la clé existe avec la valeur `null`
(Python `dict.get(key, default)` n'utilise `default` que si la clé est **absente**).
Ensuite `info.get('id')` lève l'exception.  
**Fix** : toujours envoyer `"info": {}` (dict vide), jamais `null`.

---

## 4. `zsh` : `$path` est lié à `$PATH`

**Symptôme** : après une boucle `for path in ...`, les commandes système (`ls`, `curl`, etc.) ne se
trouvent plus.  
**Cause** : en zsh, `path` (minuscule) est un tableau lié à `$PATH`. La boucle l'écrase.  
**Fix** : utiliser un autre nom de variable (`ep`, `url`, `item`, etc.) dans les boucles zsh.
Pour restaurer : `export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"`.

---

## 5. `docker compose` (espace) vs `docker-compose` (tiret)

**Sur cette machine** : le plugin `docker compose` (v2) n'est pas correctement résolu.
Utiliser systématiquement `docker-compose` (avec tiret, binaire `/opt/homebrew/bin/docker-compose`).

---

## 6. Le bootstrap rejoue si le volume `openwebui-data` est absent

Le script `bootstrap/init_accounts.py` est idempotent via la logique applicative (tentative de
login avant signup, vérification d'existence du tool server). Mais OpenWebUI lui-même est
réinitialisé si le volume Docker est supprimé (`docker volume rm`). Dans ce cas, le bootstrap
doit re-tourner pour recréer les comptes et ré-enregistrer le tool server.

---

## 7. `case_loader` utilise `lru_cache` — modifications à chaud non visibles

Les fonctions `load_case()`, `load_suspects()`, `load_camera_logs()` sont décorées `@lru_cache`.
Toute modification de `case/*.json` pendant que le conteneur tourne n'est visible qu'après un
restart (`docker-compose restart tools`). `load_suspect_prompt()` **n'est pas** mis en cache —
les changements de prompts `*.md` sont lus à chaque appel, mais uniquement après restart du
conteneur (car le volume est monté en lecture seule `:ro`).

---

## 8. Le volume `case/` est monté en lecture seule dans `tools`

`docker-compose.yml` monte `./case:/app/case:ro`. Le code ne peut pas écrire dans `case/` depuis
le conteneur. Pour modifier les données, éditer sur le host puis `docker-compose restart tools`.

---

## 9. OpenWebUI : `ENABLE_SIGNUP` doit rester `false`

Si `ENABLE_SIGNUP=true`, n'importe qui peut créer un compte. Le bootstrap crée les comptes via
`/api/v1/auths/add` (endpoint admin) après connexion. Cette route fonctionne même avec
`ENABLE_SIGNUP=false`.

---

## 11. Modèles providers non visibles aux non-admins par défaut

**Symptôme** : les enquêteurs voient 0 modèles dans le sélecteur de chat OpenWebUI.  
**Cause** : Dans cette version d'OpenWebUI (main), les modèles providers (OpenAI) ne sont pas
accessibles aux non-admins par défaut. Seuls les **custom models** (entrées en DB) avec un
access grant `{principal_type:"user", principal_id:"*", permission:"read"}` apparaissent dans
`/api/models` pour les non-admins.  
**Règle critique** : le custom model doit avoir `base_model_id: null`. Avec `base_model_id` non-null,
le modèle est une "dérivation" et n'apparaît PAS dans `/api/models` (seulement dans `/api/v1/models/list`).

**Fix** : endpoint `POST /api/v1/models/create` avec `base_model_id: null` et
`access_grants: [{principal_type:"user", principal_id:"*", permission:"read"}]`.  
Le bootstrap (`ensure_public_models`) s'en charge automatiquement via `ENABLED_MODELS` dans `.env`.

**Ne pas utiliser** :
- `ENABLE_MODEL_FILTER` + `MODEL_FILTER_LIST` env vars — ne fonctionnent pas sur instance déjà initialisée (DB prend le dessus)
- `base_model_id: "gpt-4o-mini"` dans la payload de création (modèle traité comme dérivation, invisible)
- `POST /api/v1/models/model/access/update` seul (crée une entrée avec base_model_id non-null)

Dans `case_loader.py`, les fonctions JSON utilisent `@lru_cache(maxsize=1)`.
`load_suspect_prompt()` n'a pas de cache car elle prend un paramètre string.
Si besoin d'ajouter un cache sur cette fonction : utiliser `@lru_cache(maxsize=None)` ou
`@lru_cache(maxsize=32)` — pas `@lru_cache(maxsize=1)` qui n'est utile que pour les fonctions
sans paramètre.
