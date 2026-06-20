# Lab 3 — Flask API (Routes + Testing)

## Objectif
Créer une API Flask avec 3 endpoints : `/health`, `/metrics`, `/webhook`, et les tester avec `app.test_client()`.

## Concepts pratiqués
- Routes Flask, méthodes HTTP
- `request.is_json`, `request.get_json()`, `jsonify()`
- Error handlers (`@app.errorhandler`)
- Testing Flask avec `pytest` + `test_client()`
- Status codes HTTP (200, 400, 404, 405)

## Setup
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Done condition
```
tests/test_api.py — 13 tests PASSED
```

## Fichiers
| Fichier | Statut |
|---------|--------|
| `app.py` | À compléter |
| `tests/test_api.py` | Complet — ne pas modifier |

## Endpoints attendus

| Method | Route | Succès | Erreur |
|--------|-------|--------|--------|
| GET | `/health` | 200 `{"status": "ok", "timestamp": "..."}` | — |
| GET | `/metrics` | 200 `{"requests_total": N, ...}` | — |
| POST | `/webhook` | 200 `{"status": "received", "event_type": "..."}` | 400 si manque `event_type` ou non-JSON |

## Hints
- `app.config["TESTING"] = True` désactive les error handlers natifs de Flask en test
- `response.get_json()` retourne `None` si le Content-Type n'est pas JSON
- `datetime.utcnow().isoformat()` pour le timestamp

## Questions d'entretien associées
- "Comment tester une API Flask sans démarrer un vrai serveur ?"
- "Quelle est la différence entre 400 et 422 ?"
- "Comment gérer les erreurs globalement dans Flask ?"
