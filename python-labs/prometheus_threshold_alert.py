#!/usr/bin/env python3
"""
Interroge Prometheus avec une requête PromQL et génère une alerte si un seuil est dépassé.
Complémentaire à Alertmanager : pour les checks one-shot en CI/cron qui ne justifient pas
une règle permanente.

Usage:
    python prometheus_threshold_alert.py \
        --url http://localhost:9090 \
        --query 'sum(rate(http_requests_total{status="500"}[5m]))' \
        --threshold 10 --operator gt --fail-on-alert
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import List, Dict, Any

import requests

logger = logging.getLogger(__name__)


def query_prometheus(base_url: str, query: str, timeout: int = 10) -> List[Dict[str, Any]]:
    """
    Exécute une requête PromQL instantanée via /api/v1/query.

    DIFFÉRENCE /api/v1/query vs /api/v1/query_range :
    - /api/v1/query       : valeur à UN instant (maintenant par défaut)
    - /api/v1/query_range : série temporelle sur une plage (utile pour les graphes)

    FORMAT DE RÉPONSE :
    {
      "status": "success",
      "data": {
        "resultType": "vector",
        "result": [
          {
            "metric": {"__name__": "http_requests_total", "status": "500", "job": "api"},
            "value": [1718800000.123, "42.5"]
          }
        ]
      }
    }

    PIÈGE : value[1] est TOUJOURS une STRING, même pour les nombres.
    L'API Prometheus sérialise toutes les valeurs numériques en JSON string.
    On doit explicitement convertir avec float(item["value"][1]).

    value[0] = timestamp Unix (float)
    value[1] = valeur de la métrique (string → float)

    Une requête PromQL peut retourner PLUSIEURS séries (plusieurs labels).
    Ex: http_requests_total groupé par job → une série par job.
    On retourne une liste → le caller vérifie CHAQUE série contre le seuil.

    rstrip("/") : normaliser l'URL pour éviter les doubles slashes
    Ex: "http://prometheus:9090/" → "http://prometheus:9090"
    """
    url = f"{base_url.rstrip('/')}/api/v1/query"
    resp = requests.get(url, params={"query": query}, timeout=timeout)
    resp.raise_for_status()

    data = resp.json()
    if data["status"] != "success":
        raise RuntimeError(f"Prometheus query failed: {data.get('error', 'unknown')}")

    return [
        {
            "labels": item["metric"],          # dict de labels identifiant la série
            "value": float(item["value"][1]),  # TOUJOURS string → float obligatoire
            "timestamp": item["value"][0],     # timestamp Unix (utile pour le debug)
        }
        for item in data["data"]["result"]
    ]


def check_threshold(value: float, threshold: float, operator: str) -> bool:
    """
    Vérifie si la valeur déclenche une alerte selon l'opérateur.

    PATTERN DICT DE FONCTIONS :
    Au lieu d'un if/elif/else pour chaque opérateur, on utilise un dict
    qui mappe l'opérateur vers son expression booléenne.

    Avantages :
    - Extensible : ajouter un opérateur = ajouter une entrée au dict
    - Pas d'erreur d'oubli dans un elif
    - Plus lisible : tous les opérateurs sont visibles d'un coup d'œil

    Le check `if operator not in ops` utilise le même dict pour valider.
    """
    ops = {
        "gt":  value > threshold,   # greater than
        "lt":  value < threshold,   # less than
        "gte": value >= threshold,  # greater or equal
        "lte": value <= threshold,  # less or equal
        "eq":  value == threshold,  # equal (rarement utile pour des métriques float)
    }
    if operator not in ops:
        raise ValueError(f"Unknown operator '{operator}'. Use: {list(ops.keys())}")
    return ops[operator]


def format_alert(
    query: str,
    results: List[Dict[str, Any]],
    threshold: float,
    operator: str,
    triggered: List[Dict[str, Any]],
) -> str:
    """
    Formate le rapport d'alerte pour affichage dans les logs CI ou un outil de monitoring.

    datetime.utcnow().isoformat() + "Z" : timestamp ISO 8601 en UTC.
    Le "Z" indique UTC (équivalent de +00:00).
    Plus lisible que le timestamp Unix pour les humains.

    :.4f : format à 4 décimales.
    Les métriques Prometheus sont souvent des flottants avec beaucoup de décimales.
    4 décimales donnent une précision suffisante pour la plupart des cas.

    Séparer les séries "ALERT" des séries "OK" donne une vue d'ensemble
    sans avoir à filtrer mentalement.
    """
    lines = [
        f"[{datetime.utcnow().isoformat()}Z] Prometheus Threshold Alert",
        f"Query    : {query}",
        f"Threshold: {operator} {threshold}",
        f"Results  : {len(results)} series, {len(triggered)} triggered",
        "",
    ]
    for r in triggered:
        lines.append(f"  ALERT  value={r['value']:.4f}  labels={r['labels']}")
    # Afficher aussi les séries OK pour contexte (facilite le debug)
    for r in [r for r in results if r not in triggered]:
        lines.append(f"  OK     value={r['value']:.4f}  labels={r['labels']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prometheus Threshold Alert")
    parser.add_argument("--url", required=True, help="URL Prometheus (ex: http://localhost:9090)")
    parser.add_argument("--query", required=True, help="Requête PromQL")
    parser.add_argument("--threshold", type=float, required=True, help="Valeur seuil")
    parser.add_argument(
        "--operator", default="gt", choices=["gt", "lt", "gte", "lte", "eq"],
        help="Opérateur de comparaison (défaut: gt = greater than)",
    )
    parser.add_argument("--output-json", help="Exporter les résultats en JSON")
    parser.add_argument(
        "--fail-on-alert", action="store_true",
        help="Exit 1 si seuil dépassé (gate CI : bloque si error rate trop élevé avant déploiement)",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    """
    Cas d'usage typique en CI/CD :
    Avant de déployer en prod, vérifier que le taux d'erreur actuel est < 1% :
    python prometheus_threshold_alert.py \
        --url http://prometheus:9090 \
        --query 'rate(http_errors_total[5m]) / rate(http_requests_total[5m])' \
        --threshold 0.01 --operator lt --fail-on-alert

    Le pipeline bloque si le taux d'erreur actuel est déjà élevé.
    """
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        results = query_prometheus(parsed.url, parsed.query)
        logger.info(f"Query returned {len(results)} series")

        # List comprehension : filtrer les séries qui dépassent le seuil
        triggered = [
            r for r in results
            if check_threshold(r["value"], parsed.threshold, parsed.operator)
        ]

        # print() pour le rapport principal → stdout (séparable des logs stderr)
        print(format_alert(parsed.query, results, parsed.threshold, parsed.operator, triggered))

        if parsed.output_json:
            with open(parsed.output_json, "w") as f:
                # Séparer "triggered" et "all" dans le JSON pour faciliter le parsing
                json.dump({"triggered": triggered, "all": results}, f, indent=2)

        if triggered:
            logger.warning(f"{len(triggered)} series exceeded threshold")
            if parsed.fail_on_alert:
                return 1

        return 0

    except requests.exceptions.ConnectionError:
        # ConnectionError spécifique : Prometheus inaccessible (réseau, port, DNS)
        # Séparé de l'Exception générale pour un message d'erreur plus clair
        logger.error(f"Cannot connect to Prometheus at {parsed.url}")
        return 1
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
