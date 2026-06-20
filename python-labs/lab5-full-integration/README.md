# Lab 5 — Intégration complète (Flask Blueprints + Service Layer + Docker)

## Objectif
Assembler une Flask app structurée avec blueprints, une couche service séparée, et la dockeriser.

## Concepts pratiqués
- Application factory pattern (`create_app()`)
- Blueprints Flask pour organiser les routes
- Séparation des responsabilités (routes → services)
- `pytest` fixtures avec `conftest.py`
- Docker : `FROM`, `COPY`, `RUN`, `EXPOSE`, `CMD`

## Setup
```bash
pip install -r requirements.txt
pytest tests/ -v

# Tester en Docker
docker build -t lab5 .
docker run -p 5000:5000 lab5
curl http://localhost:5000/api/v1/health
```

## Done condition
```
tests/test_api.py — 11 tests PASSED
+ docker build && curl /api/v1/health retourne {"status": "ok", ...}
```

## Structure du projet
```
lab5-full-integration/
├── app/
│   ├── __init__.py          ← create_app() : enregistrer le blueprint
│   ├── api/v1/
│   │   ├── __init__.py      ← Blueprint défini ici (déjà fait)
│   │   └── routes.py        ← Routes à compléter
│   └── services/
│       └── health.py        ← Service layer à compléter
├── tests/
│   ├── conftest.py          ← Fixtures (déjà fait)
│   └── test_api.py          ← Tests à faire passer
├── Dockerfile               ← À compléter
├── requirements.txt
└── run.py
```

## Endpoints attendus (préfixe `/api/v1`)

| Method | Route | Réponse |
|--------|-------|---------|
| GET | `/api/v1/health` | `{"status": "ok", "timestamp": "...", "version": "1.0.0"}` |
| GET | `/api/v1/resources` | `{"resources": [...], "count": N}` |
| GET | `/api/v1/resources?type=VirtualMachine` | filtré par type |
| GET | `/api/v1/resources?region=eastus` | filtré par région |
| GET | `/api/v1/resources?compliant=true` | filtré par conformité |
| GET | `/api/v1/resources/<id>` | resource ou 404 |

## Ordre de complétion recommandé
1. `app/services/health.py` → `get_status()`, `get_resources()`, `get_resource()`
2. `app/api/v1/routes.py` → utiliser le service dans chaque route
3. `app/__init__.py` → enregistrer le blueprint
4. `Dockerfile` → containeriser
5. `pytest tests/ -v` → tous verts

## Hints
- Le blueprint est déjà créé dans `app/api/v1/__init__.py`, tu dois juste l'enregistrer
- `compliant` arrive comme string `"true"/"false"` depuis les query params → convertir en bool
- `app.register_blueprint(bp, url_prefix="/api/v1")`

## Questions d'entretien associées
- "Pourquoi utiliser une application factory au lieu d'une instance globale ?"
- "Comment organiser une Flask app pour qu'elle soit testable ?"
- "Quelle est la différence entre un Blueprint et une application Flask ?"
