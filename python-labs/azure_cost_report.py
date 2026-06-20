#!/usr/bin/env python3
"""
Reporting de coûts Azure groupés par tag (équipe, projet, env).
Utilise l'API Cost Management pour agréger sur une période donnée.

Usage:
    python azure_cost_report.py --subscription <id> --tag-key team
    python azure_cost_report.py --subscription <id> --days 7 --output-csv costs.csv
"""

import argparse
import csv
import logging
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
# Ces modèles construisent la requête de coût de façon typée
from azure.mgmt.costmanagement.models import (
    QueryDefinition,   # définit le type de coût et la période
    QueryDataset,      # définit les agrégations et groupements
    QueryAggregation,  # comment agréger (Sum, Avg, etc.)
    QueryGrouping,     # comment grouper (par tag, par resource group, etc.)
    TimeframeType,     # CUSTOM, MonthToDate, LastMonth, etc.
)

logger = logging.getLogger(__name__)


def get_client() -> CostManagementClient:
    """
    CostManagementClient est différent de ResourceManagementClient :
    il ne prend PAS le subscription_id dans son constructeur.

    Pourquoi ? Parce que l'API Cost Management peut couvrir différents scopes :
    - /subscriptions/{id}               → une subscription
    - /subscriptions/{id}/resourceGroups/{rg} → un resource group
    - /providers/Microsoft.Management/managementGroups/{id} → toute l'org

    Le scope est passé dans chaque requête, pas dans le client.
    """
    return CostManagementClient(DefaultAzureCredential())


def get_cost_by_tag(
    client: CostManagementClient,
    subscription_id: str,
    tag_key: str = "team",
    days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Agrège les coûts groupés par valeur d'un tag sur les X derniers jours.

    Exemple de résultat pour tag_key="team" :
    [
        {"Cost": 142.50, "Currency": "EUR", "team": "platform"},
        {"Cost": 89.20,  "Currency": "EUR", "team": "data"},
    ]

    Structure de la requête :
    - type="ActualCost" : coûts réels facturés (vs AmortizedCost qui lisse les réservations)
    - granularity="None" : total sur la période (pas jour par jour)
    - aggregation : additionner les coûts → Sum(Cost)
    - grouping : regrouper par valeur du tag spécifié
    """
    # Le scope définit le périmètre de la requête
    scope = f"/subscriptions/{subscription_id}"
    now = datetime.utcnow()

    # QueryDefinition construit la requête de façon typée (pas de string JSON à la main)
    query = QueryDefinition(
        type="ActualCost",
        timeframe=TimeframeType.CUSTOM,  # période personnalisée (vs des presets comme LastMonth)
        time_period={
            # strftime("%Y-%m-%dT00:00:00Z") = format ISO 8601 attendu par l'API
            "from": (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z"),
            "to": now.strftime("%Y-%m-%dT00:00:00Z"),
        },
        dataset=QueryDataset(
            granularity="None",  # pas de découpage temporel → un seul total
            # aggregation : dict avec nom personnalisé → fonction d'agrégation
            aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
            # grouping : regrouper par clé de tag
            # type="TagKey" = grouper par la valeur du tag (ex: team=platform, team=data)
            grouping=[QueryGrouping(type="TagKey", name=tag_key)],
        ),
    )

    result = client.query.usage(scope=scope, parameters=query)

    # ── FORMAT DE RÉPONSE DE L'API ────────────────────────────────────────────
    # L'API Cost Management retourne les données sous forme TABULAIRE :
    # result.columns = [Column(name="Cost"), Column(name="Currency"), Column(name="team")]
    # result.rows    = [[142.50, "EUR", "platform"], [89.20, "EUR", "data"]]
    #
    # C'est plus compact que JSON mais moins lisible.
    # On "zippe" les colonnes et les lignes pour obtenir des dicts :
    # zip(["Cost", "Currency", "team"], [142.50, "EUR", "platform"])
    # → [("Cost", 142.50), ("Currency", "EUR"), ("team", "platform")]
    # → dict(...) → {"Cost": 142.50, "Currency": "EUR", "team": "platform"}
    columns = [col.name for col in result.columns]
    return [dict(zip(columns, row)) for row in result.rows]


def export_csv(data: List[Dict[str, Any]], filepath: str) -> None:
    """
    Exporte les données de coût en CSV.
    data[0].keys() donne les noms de colonnes dynamiquement
    (on ne sait pas à l'avance quels tags existent).
    """
    if not data:
        logger.warning("No data to export")
        return
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    logger.info(f"Exported to {filepath}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure Cost Report by Tag")
    parser.add_argument("--subscription", "-s", required=True, help="Azure Subscription ID")
    parser.add_argument("--tag-key", default="team", help="Tag de regroupement (défaut: team)")
    # type=int : argparse convertit automatiquement la string en int
    parser.add_argument("--days", type=int, default=30, help="Période en jours (défaut: 30)")
    parser.add_argument("--output-csv", help="Exporter en CSV")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        client = get_client()
        data = get_cost_by_tag(client, parsed.subscription, parsed.tag_key, parsed.days)

        logger.info(f"Cost by '{parsed.tag_key}' (last {parsed.days} days):")
        for row in data:
            logger.info(f"  {row}")

        if parsed.output_csv:
            export_csv(data, parsed.output_csv)

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
