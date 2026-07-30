#!/usr/bin/env python3
"""Amorçage des comptes Open WebUI pour « Sherlock AI ».

Au premier démarrage, ce script :
1. attend qu'Open WebUI soit disponible ;
2. crée le compte administrateur (le tout premier compte devient admin) ;
3. crée N comptes enquêteurs génériques.

Il est idempotent : relancé, il ne recrée pas les comptes déjà présents et se
termine proprement (les données Open WebUI sont persistées dans un volume).

Configuration par variables d'environnement :
- OPENWEBUI_URL          : URL interne d'Open WebUI (ex: http://openwebui:8080)
- ADMIN_NAME             : nom affiché de l'admin
- ADMIN_EMAIL            : email de connexion de l'admin
- ADMIN_PASSWORD         : mot de passe de l'admin
- INVESTIGATOR_COUNT     : nombre de comptes enquêteurs à créer
- INVESTIGATOR_PREFIX    : préfixe des emails enquêteurs (ex: enqueteur)
- INVESTIGATOR_DOMAIN    : domaine des emails enquêteurs (ex: sherlock.local)
- INVESTIGATOR_PASSWORD  : mot de passe commun des enquêteurs
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("OPENWEBUI_URL", "http://openwebui:8080").rstrip("/")
ADMIN_NAME = os.environ.get("ADMIN_NAME", "Administrateur")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@sherlock.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-admin")
INVESTIGATOR_COUNT = int(os.environ.get("INVESTIGATOR_COUNT", "5"))
INVESTIGATOR_PREFIX = os.environ.get("INVESTIGATOR_PREFIX", "enqueteur")
INVESTIGATOR_DOMAIN = os.environ.get("INVESTIGATOR_DOMAIN", "sherlock.local")
INVESTIGATOR_PASSWORD = os.environ.get("INVESTIGATOR_PASSWORD", "change-me-enqueteur")


def _post(path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def wait_for_openwebui(timeout: int = 300) -> None:
    """Attend que l'endpoint /health réponde."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=5) as resp:
                if resp.status == 200:
                    print(f"[bootstrap] Open WebUI est prêt ({BASE}).", flush=True)
                    return
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError):
            pass
        print("[bootstrap] En attente d'Open WebUI...", flush=True)
        time.sleep(3)
    raise SystemExit("[bootstrap] Open WebUI n'a pas répondu à temps.")


def ensure_admin() -> str:
    """Crée l'admin si besoin et renvoie un jeton d'accès admin."""
    # Tente d'abord une connexion : si l'admin existe déjà, on récupère le token.
    status, body = _post("/api/v1/auths/signin", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if status == 200 and body.get("token"):
        print("[bootstrap] Admin déjà présent, connexion réussie.", flush=True)
        return body["token"]

    # Connexion échouée avec 401 → mauvais mot de passe, impossible de continuer.
    if status == 401:
        raise SystemExit(
            f"[bootstrap] Mot de passe admin incorrect (email: {ADMIN_EMAIL}). "
            "Vérifiez ADMIN_PASSWORD dans .env."
        )

    # Sinon on crée le tout premier compte, qui devient administrateur.
    status, body = _post(
        "/api/v1/auths/signup",
        {"name": ADMIN_NAME, "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    if status == 200 and body.get("token"):
        print("[bootstrap] Compte administrateur créé.", flush=True)
        return body["token"]

    # signup désactivé (403) → OpenWebUI est déjà initialisé mais le signin a
    # renvoyé un code inattendu. On ne peut rien faire sans token valide.
    if status == 403:
        raise SystemExit(
            "[bootstrap] Impossible de créer le compte admin (inscriptions désactivées). "
            "Vérifiez ADMIN_EMAIL / ADMIN_PASSWORD dans .env."
        )

    raise SystemExit(f"[bootstrap] Impossible de créer/connecter l'admin: {status} {body}")


def ensure_investigators(admin_token: str) -> None:
    """Crée les comptes enquêteurs manquants."""
    created = 0
    for i in range(1, INVESTIGATOR_COUNT + 1):
        email = f"{INVESTIGATOR_PREFIX}{i}@{INVESTIGATOR_DOMAIN}"
        name = f"Enquêteur {i}"
        status, body = _post(
            "/api/v1/auths/add",
            {
                "name": name,
                "email": email,
                "password": INVESTIGATOR_PASSWORD,
                "role": "user",
            },
            token=admin_token,
        )
        if status == 200:
            created += 1
            print(f"[bootstrap] Compte créé : {email}", flush=True)
        elif status in (400, 409) and "email" in json.dumps(body).lower():
            print(f"[bootstrap] Compte déjà existant : {email}", flush=True)
        else:
            print(f"[bootstrap] Avertissement pour {email}: {status} {body}", flush=True)
    print(f"[bootstrap] Terminé. {created} nouveau(x) compte(s) enquêteur créé(s).", flush=True)


TOOLS_URL = os.environ.get("TOOLS_URL", "http://tools:8000")
MCPO_API_KEY = os.environ.get("MCPO_API_KEY", "")
TOOLS_PATH = os.environ.get("TOOLS_PATH", "/sherlock/openapi.json")
DEFAULT_MODELS = os.environ.get("DEFAULT_MODELS", "")
ENABLED_MODELS = os.environ.get("ENABLED_MODELS", "")


def _put(path: str, payload: dict, token: str) -> tuple[int, dict]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"detail": body}
        return exc.code, parsed


def ensure_tool_server(admin_token: str) -> None:
    """Enregistre le serveur d'outils Sherlock dans Open WebUI (idempotent)."""
    if not MCPO_API_KEY:
        print("[bootstrap] MCPO_API_KEY non définie, enregistrement du tool server ignoré.", flush=True)
        return

    # Lecture des connexions existantes.
    req = urllib.request.Request(f"{BASE}/api/v1/configs/tool_servers")
    req.add_header("Authorization", f"Bearer {admin_token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            existing = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception:
        existing = {}

    connections = existing.get("TOOL_SERVER_CONNECTIONS", []) or []

    # Vérifie si déjà enregistré (idempotence sur l'URL).
    for conn in connections:
        if conn.get("url") == TOOLS_URL and conn.get("path") == TOOLS_PATH:
            print(f"[bootstrap] Tool server déjà enregistré : {TOOLS_URL}{TOOLS_PATH}", flush=True)
            return

    connections.append({
        "url": TOOLS_URL,
        "path": TOOLS_PATH,
        "type": "openapi",
        "auth_type": "bearer",
        "key": MCPO_API_KEY,
        "config": {"enable": True},   # requis : sans `enable: true`, le serveur est ignoré
        "headers": None,
        "info": {},   # doit être un dict vide, pas null (info.get() planterait)
    })

    status, body = _put(
        "/api/v1/configs/tool_servers",
        {"TOOL_SERVER_CONNECTIONS": connections},
        admin_token,
    )
    if status == 200:
        print(f"[bootstrap] Tool server enregistré : {TOOLS_URL}{TOOLS_PATH}", flush=True)
    else:
        print(f"[bootstrap] Avertissement : enregistrement tool server {status} — {body}", flush=True)


def ensure_public_models(admin_token: str) -> None:
    """Crée des entrées de modèles publics pour les enquêteurs (non-admins).

    Dans cette version d'OpenWebUI, les modèles providers ne sont pas visibles
    aux non-admins par défaut. Cette fonction crée des entrées "custom model"
    avec access_grants=[{user:*:read}] pour les rendre publics.
    La liste des modèles à publier est dans ENABLED_MODELS (séparés par ';').
    """
    if not ENABLED_MODELS:
        print("[bootstrap] ENABLED_MODELS non défini — aucun modèle public configuré.", flush=True)
        return

    model_ids = [m.strip() for m in ENABLED_MODELS.replace(",", ";").split(";") if m.strip()]
    public_read_grant = {"principal_type": "user", "principal_id": "*", "permission": "read"}

    # Récupère les modèles custom existants (pour éviter les doublons).
    req_list = urllib.request.Request(f"{BASE}/api/v1/models/base")
    req_list.add_header("Authorization", f"Bearer {admin_token}")
    try:
        with urllib.request.urlopen(req_list, timeout=15) as resp:
            existing_models = json.loads(resp.read())
    except Exception:
        existing_models = []

    existing_by_id: dict[str, dict] = {}
    if isinstance(existing_models, list):
        for m in existing_models:
            existing_by_id[m.get("id", "")] = m
    elif isinstance(existing_models, dict):
        for m in existing_models.get("data", []):
            existing_by_id[m.get("id", "")] = m

    for model_id in model_ids:
        if model_id in existing_by_id:
            m = existing_by_id[model_id]
            grants = m.get("access_grants") or []
            already_public = any(
                g.get("principal_type") == "user"
                and g.get("principal_id") == "*"
                and g.get("permission") == "read"
                for g in grants
            )
            # Si base_model_id est non-null le modèle est une dérivation et
            # n'apparaît pas dans /api/models — on le supprime pour le recréer.
            needs_recreate = m.get("base_model_id") is not None
            if already_public and not needs_recreate:
                print(f"[bootstrap] Modèle déjà public : {model_id}", flush=True)
                continue
            if needs_recreate:
                # Suppression de l'entrée invalide
                req_del = urllib.request.Request(
                    f"{BASE}/api/v1/models/model/delete",
                    json.dumps({"id": model_id}).encode(),
                    {"Content-Type": "application/json"},
                )
                req_del.add_header("Authorization", f"Bearer {admin_token}")
                try:
                    urllib.request.urlopen(req_del, timeout=15)
                except Exception:
                    pass

        # Crée l'entrée de modèle public avec base_model_id=null (requis pour
        # que le modèle apparaisse dans /api/models pour les non-admins).
        public_grant = {"principal_type": "user", "principal_id": "*", "permission": "read"}
        payload = json.dumps({
            "id": model_id,
            "name": model_id,
            "base_model_id": None,   # NULL = modèle de base visible dans /api/models
            "params": {},
            "meta": {
                "description": None,
                "profile_image_url": "/static/favicon.png",
                "capabilities": {
                    "vision": True, "file_upload": True, "file_context": True,
                    "web_search": True, "image_generation": False,
                    "code_interpreter": True, "citations": True,
                    "status_updates": True, "memory": True, "builtin_tools": True,
                    "terminal": True,
                },
                "tags": [],
            },
            "access_grants": [public_grant],
            "is_active": True,
        }).encode("utf-8")
        req_create = urllib.request.Request(
            f"{BASE}/api/v1/models/create", payload, {"Content-Type": "application/json"}
        )
        req_create.add_header("Authorization", f"Bearer {admin_token}")
        try:
            with urllib.request.urlopen(req_create, timeout=15) as resp:
                result = json.loads(resp.read())
            grants_set = result.get("access_grants") or []
            is_public = any(
                g.get("principal_type") == "user" and g.get("principal_id") == "*"
                for g in grants_set
            )
            status = "public ✓" if is_public else f"créé (grants={grants_set})"
            print(f"[bootstrap] Modèle {status} : {model_id}", flush=True)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "ignore")
            print(f"[bootstrap] Avertissement modèle {model_id}: {exc.code} {body[:120]}", flush=True)


def ensure_default_model(admin_token: str) -> None:
    """Fixe le modèle par défaut dans la DB OpenWebUI (idempotent).

    Tous les modèles du provider sont accessibles par défaut dans un
    environnement fermé. Cette fonction fixe seulement la présélection.
    """
    if not DEFAULT_MODELS:
        return

    req = urllib.request.Request(f"{BASE}/api/v1/configs/models")
    req.add_header("Authorization", f"Bearer {admin_token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            current = json.loads(resp.read().decode("utf-8") or "{}")
    except Exception:
        current = {}

    if current.get("DEFAULT_MODELS") == DEFAULT_MODELS:
        print(f"[bootstrap] Modèle par défaut déjà configuré : {DEFAULT_MODELS}", flush=True)
        return

    payload = json.dumps({
        "DEFAULT_MODELS": DEFAULT_MODELS,
        "DEFAULT_PINNED_MODELS": current.get("DEFAULT_PINNED_MODELS"),
        "MODEL_ORDER_LIST": current.get("MODEL_ORDER_LIST") or [],
        "DEFAULT_MODEL_METADATA": current.get("DEFAULT_MODEL_METADATA") or {},
        "DEFAULT_MODEL_PARAMS": current.get("DEFAULT_MODEL_PARAMS") or {},
    }).encode("utf-8")
    req2 = urllib.request.Request(f"{BASE}/api/v1/configs/models", payload, {"Content-Type": "application/json"})
    req2.add_header("Authorization", f"Bearer {admin_token}")
    try:
        with urllib.request.urlopen(req2, timeout=15) as resp:
            json.loads(resp.read())
        print(f"[bootstrap] Modèle par défaut configuré : {DEFAULT_MODELS}", flush=True)
    except Exception as exc:
        print(f"[bootstrap] Avertissement modèle par défaut : {exc}", flush=True)


def main() -> None:
    wait_for_openwebui()
    token = ensure_admin()
    ensure_investigators(token)
    ensure_tool_server(token)
    ensure_public_models(token)
    ensure_default_model(token)
    print("[bootstrap] Amorçage des comptes terminé.", flush=True)


if __name__ == "__main__":
    main()
