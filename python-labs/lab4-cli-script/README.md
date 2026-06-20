# Lab 4 — Script CLI (argparse + YAML + logging)

## Objectif
Créer un outil CLI `audit.py` qui charge un fichier YAML de ressources, filtre selon des critères, et affiche les résultats en table ou JSON.

## Concepts pratiqués
- `argparse` : arguments positionnels, flags, choices, valeurs par défaut
- `pyyaml` : chargement de fichiers de config
- `logging` : niveaux, format, configuration dynamique
- Output formaté (table ASCII vs JSON)
- Tests CLI avec `capsys` et `main(args=[...])`

## Setup
```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Done condition
```
tests/test_audit.py — 14 tests PASSED
```

## Fichiers
| Fichier | Statut |
|---------|--------|
| `audit.py` | À compléter |
| `data/resources.yaml` | Données de test |
| `tests/test_audit.py` | Complet — ne pas modifier |

## Usage attendu
```bash
python audit.py --input data/resources.yaml
python audit.py -i data/resources.yaml --resource-type VirtualMachine --output json
python audit.py -i data/resources.yaml --non-compliant --region eastus
python audit.py -i data/resources.yaml --dry-run --log-level DEBUG
```

## Arguments CLI à implémenter
| Argument | Court | Type | Défaut |
|----------|-------|------|--------|
| `--input` | `-i` | str, obligatoire | — |
| `--resource-type` | `-t` | str | None |
| `--region` | `-r` | str | None |
| `--non-compliant` | — | flag bool | False |
| `--output` | `-o` | `json` ou `table` | `table` |
| `--log-level` | — | DEBUG/INFO/WARNING/ERROR | INFO |
| `--dry-run` | — | flag bool | False |

## Hints
- `main(args=["--input", "file.yaml"])` permet de tester sans `sys.argv`
- `capsys.readouterr().out` capture le stdout
- `yaml.safe_load()` est préféré à `yaml.load()`
- `str.ljust(N)` pour aligner les colonnes de la table

## Questions d'entretien associées
- "Comment structurer un script CLI Python pour qu'il soit testable ?"
- "Pourquoi séparer `build_parser()` de `main()` ?"
- "Quelle est la différence entre `logging.info()` et `print()` en production ?"
