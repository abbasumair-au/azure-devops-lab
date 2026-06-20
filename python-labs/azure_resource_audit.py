#!/usr/bin/env python3
"""
Audit et nettoyage des ressources Azure orphelines.
Identifie les Resource Groups sans tag 'owner', optionnellement les supprime.

Usage:
    python azure_resource_audit.py --subscription <id>
    python azure_resource_audit.py --subscription <id> --delete --dry-run
    python azure_resource_audit.py --subscription <id> --output-csv rapport.csv
"""

import argparse
import csv
import logging
import sys
from typing import List, Dict, Any, Optional

# ── AUTHENTIFICATION ──────────────────────────────────────────────────────────
# DefaultAzureCredential est le standard recommandé par Microsoft.
# Il essaie plusieurs méthodes dans l'ordre, sans que le code change :
#
#   1. Variables d'env : AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID
#      → utilisé en CI/CD (GitHub Actions avec service principal)
#   2. Managed Identity : quand le script tourne dans un pod AKS ou une VM Azure
#      → zéro credential à gérer, la sécurité est gérée par Azure
#   3. Azure CLI : quand tu travailles en local avec `az login`
#
# Avantage : le même code fonctionne en local ET en CI sans modification.
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

logger = logging.getLogger(__name__)


def get_client(subscription_id: str) -> ResourceManagementClient:
    """
    Crée un client Azure Resource Management authentifié.
    Le subscription_id est passé ici car le client est scopé à une subscription.
    """
    credential = DefaultAzureCredential()
    # ResourceManagementClient expose toutes les opérations sur les ressources Azure :
    # resource groups, resources, deployments, policy assignments, etc.
    return ResourceManagementClient(credential, subscription_id)


def list_resource_groups(client: ResourceManagementClient) -> List[Dict[str, Any]]:
    """
    Retourne tous les Resource Groups de la subscription.
    On convertit en dicts pour découpler le code de l'objet SDK Azure
    (les objets SDK changent entre versions — les dicts sont stables).
    """
    rgs = []
    for rg in client.resource_groups.list():
        rgs.append({
            "name": rg.name,
            "location": rg.location,
            # rg.tags peut être None si aucun tag n'a jamais été défini
            # On utilise `or {}` pour toujours avoir un dict (pas None)
            "tags": rg.tags or {},
            "provisioning_state": rg.properties.provisioning_state,
        })
    return rgs


def find_orphaned(
    resource_groups: List[Dict[str, Any]],
    required_tag: str = "owner",
) -> List[Dict[str, Any]]:
    """
    Identifie les RGs sans le tag requis.

    Pourquoi chercher les RGs sans tag 'owner' ?
    Un RG sans propriétaire déclaré est souvent :
    - Un environnement de test oublié
    - Une ressource créée manuellement sans gouvernance
    - Un coût fantôme qui persiste inutilement

    List comprehension avec condition :
    [expression for item in liste if condition]
    Ici : garder seulement les RGs où 'owner' n'est PAS dans les tags.
    """
    return [rg for rg in resource_groups if required_tag not in rg["tags"]]


def delete_resource_group(
    client: ResourceManagementClient,
    name: str,
    dry_run: bool = True,
) -> str:
    """
    Supprime un Resource Group et toutes ses ressources.

    IMPORTANT : begin_delete() est une opération ASYNCHRONE longue durée.
    Elle retourne un LROPoller (Long Running Operation Poller).
    .wait() bloque jusqu'à la fin de l'opération.

    Sans .wait(), le script continuerait avant la fin de la suppression,
    ce qui peut causer des problèmes si d'autres opérations dépendent de l'état.

    dry_run=True par défaut pour éviter les suppressions accidentelles.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would delete: {name}")
        return "dry-run"
    logger.warning(f"Deleting resource group: {name}")
    poller = client.resource_groups.begin_delete(name)
    poller.wait()  # bloque jusqu'à la fin de la suppression
    return "deleted"


def export_csv(resource_groups: List[Dict[str, Any]], filepath: str) -> None:
    """
    Exporte la liste des RGs en CSV pour reporting ou revue humaine.

    csv.DictWriter : écrit des dicts comme des lignes CSV.
    fieldnames définit l'ordre des colonnes.
    newline="" est requis sur Windows pour éviter les doubles sauts de ligne.
    """
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "location", "tags", "provisioning_state"])
        writer.writeheader()
        writer.writerows(resource_groups)
    logger.info(f"Exported {len(resource_groups)} entries to {filepath}")


def build_parser() -> argparse.ArgumentParser:
    """
    Séparer build_parser() de main() permet de tester le parsing en isolation
    et de réutiliser le parser depuis d'autres scripts.
    """
    parser = argparse.ArgumentParser(description="Azure Resource Group Audit Tool")
    parser.add_argument("--subscription", "-s", required=True, help="Azure Subscription ID")
    parser.add_argument("--required-tag", default="owner", help="Tag obligatoire (défaut: owner)")
    # action="store_true" : crée un flag booléen — présent = True, absent = False
    parser.add_argument("--delete", action="store_true", help="Supprimer les RGs orphelins")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans supprimer")
    parser.add_argument("--output-csv", help="Exporter les résultats en CSV")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    """
    Point d'entrée principal. Retourne un code de sortie entier.

    args=None → utilise sys.argv (comportement normal en ligne de commande).
    args=[...] → utile pour les tests : main(["--subscription", "xxx"]).

    Codes de retour :
      0 = succès, aucun orphelin
      1 = succès, mais orphelins trouvés (gate CI : bloque si tag manquant)
      2 = erreur inattendue
    """
    parser = build_parser()
    parsed = parser.parse_args(args)

    # logging.basicConfig configure le logger racine (root logger).
    # %(asctime)s = timestamp, %(levelname)s = INFO/WARNING/etc.
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        client = get_client(parsed.subscription)
        all_rgs = list_resource_groups(client)
        logger.info(f"Found {len(all_rgs)} resource groups")

        orphaned = find_orphaned(all_rgs, required_tag=parsed.required_tag)
        logger.info(f"{len(orphaned)} orphaned (missing tag '{parsed.required_tag}')")

        # logger.warning pour les orphelins : visible même avec --log-level WARNING
        for rg in orphaned:
            logger.warning(f"  ORPHANED: {rg['name']} ({rg['location']}) — tags: {rg['tags']}")

        if parsed.output_csv:
            export_csv(orphaned, parsed.output_csv)

        if parsed.delete:
            for rg in orphaned:
                result = delete_resource_group(client, rg["name"], dry_run=parsed.dry_run)
                logger.info(f"  {rg['name']}: {result}")

        # Exit 1 si des orphelins existent — utile comme gate en CI.
        # Le pipeline peut décider de bloquer ou juste de notifier selon le contexte.
        return 0 if not orphaned else 1

    except Exception as e:
        logger.error(f"Error: {e}")
        return 2  # code 2 = erreur technique, différent de 1 (résultat logique)


if __name__ == "__main__":
    # sys.exit() transmet le code de retour au shell
    # Sans sys.exit(), le script retourne toujours 0 même en cas d'erreur
    sys.exit(main())
