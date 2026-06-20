# Lab 1 — Resource Inventory (OOP + Fichiers + Tests)

## Objectif
Implémenter une classe `ResourceInventory` qui charge un JSON de ressources Azure, filtre par type/région/conformité, et expose une représentation propre.

## Concepts pratiqués
- Classes Python, `__repr__`, `__eq__`, `__len__`
- `@classmethod`, type hints
- Gestion d'exceptions (`FileNotFoundError`, `ValueError`)
- Comprehensions + méthodes chaînables
- `pytest` : fixtures, `tmp_path`, `pytest.raises`

## Setup
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Done condition
```
tests/test_resource_inventory.py — 14 tests PASSED
```

## Fichiers
| Fichier | Statut |
|---------|--------|
| `resource_inventory.py` | À compléter (TODOs) |
| `tests/test_resource_inventory.py` | Complet — ne pas modifier |
| `data/resources.json` | Données de test |

## Hints
- `filter_by_type` / `filter_by_region` retournent un **nouveau** `ResourceInventory` (méthodes chaînables)
- Utilise `.lower()` pour les comparaisons case-insensitive
- `json.JSONDecodeError` hérite de `ValueError` — tu peux le re-raise directement

## Questions d'entretien associées
- "Quelle est la différence entre `__str__` et `__repr__` ?"
- "Quand utiliser `@classmethod` vs `@staticmethod` ?"
- "Comment tester du code qui lit des fichiers sans toucher le disque ?"
