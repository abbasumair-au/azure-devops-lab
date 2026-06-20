# Lab 2 — Decorators & Context Managers

## Objectif
Implémenter un decorator `@retry` et un context manager `AzureSession`.

## Concepts pratiqués
- Decorators avec paramètres (`@retry(times=3, delay=1)`)
- `functools.wraps` (préserver les métadonnées de la fonction)
- Context managers avec `__enter__` / `__exit__`
- `unittest.mock` : `MagicMock`, `side_effect`
- `pytest.mark.parametrize`

## Setup
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Done condition
```
tests/test_decorators.py — 12 tests PASSED
```

## Fichiers
| Fichier | Statut |
|---------|--------|
| `retry.py` | À compléter |
| `azure_session.py` | À compléter |
| `tests/test_decorators.py` | Complet — ne pas modifier |

## Hints
- `@retry` doit utiliser `functools.wraps(func)` pour préserver `__name__`
- `__exit__` reçoit `(exc_type, exc_val, exc_tb)` — retourner `False` pour ne pas supprimer l'exception
- Pour tester le délai sans attendre : le test passe `delay=0`
- `side_effect=[ValueError, ValueError, "ok"]` fait que le mock échoue 2x puis réussit

## Questions d'entretien associées
- "Qu'est-ce que `functools.wraps` et pourquoi c'est important ?"
- "Quelle est la différence entre un context manager et un decorator ?"
- "Comment mocker une fonction qui échoue puis réussit avec pytest ?"
