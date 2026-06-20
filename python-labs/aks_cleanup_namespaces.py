#!/usr/bin/env python3
"""
Nettoyage des namespaces éphémères (environnements PR) inactifs depuis X jours.
Un namespace est considéré inactif si aucun de ses pods n'a été créé récemment.

Usage:
    python aks_cleanup_namespaces.py --prefix pr- --max-age-days 7
    python aks_cleanup_namespaces.py --prefix pr- --max-age-days 7 --delete --dry-run
"""

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from kubernetes import client, config

logger = logging.getLogger(__name__)


def load_kube_config(in_cluster: bool = False) -> None:
    """Charge la config Kubernetes (locale ou in-cluster)."""
    if in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def list_namespaces(prefix: str) -> list:
    """
    Liste uniquement les namespaces qui commencent par le préfixe donné.

    SÉCURITÉ CRITIQUE : filtrer par préfixe protège les namespaces système.
    Sans filtre, on risquerait de supprimer :
    - kube-system  : composants essentiels du cluster (coredns, kube-proxy...)
    - monitoring   : Prometheus, Grafana
    - argocd       : le système de déploiement lui-même
    - cert-manager : gestion des certificats TLS

    Convention : les envs PR utilisent un préfixe clair comme "pr-" ou "preview-"
    Ce préfixe ne sera JAMAIS utilisé pour des namespaces système.
    """
    v1 = client.CoreV1Api()
    # list_namespace() = équivalent de `kubectl get namespaces`
    # On filtre après récupération car l'API K8s ne supporte pas le filtrage par préfixe
    return [
        ns for ns in v1.list_namespace().items
        if ns.metadata.name.startswith(prefix)
    ]


def get_last_activity(namespace: str) -> Optional[datetime]:
    """
    Estime la dernière activité d'un namespace.

    On utilise la DATE DE CRÉATION DU POD LE PLUS RÉCENT comme proxy d'activité.
    C'est une heuristique, pas une mesure exacte, mais elle est fiable pour
    les environnements PR : s'il y a eu une activité récente, des pods ont été créés.

    CAS PARTICULIER : namespace vide (aucun pod)
    Si aucun pod ne tourne, on revient à la date de création du namespace.
    Un namespace créé il y a 30 jours sans pods est probablement abandonné.

    TIMEZONE-AWARENESS IMPORTANT :
    Les timestamps Kubernetes sont timezone-aware (UTC avec info de timezone).
    datetime.now() sans timezone est timezone-naive (pas d'info de timezone).
    Python ne peut pas comparer les deux → on doit utiliser datetime.now(timezone.utc).
    """
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace=namespace).items

    if not pods:
        # Fallback : date de création du namespace
        ns = v1.read_namespace(name=namespace)
        return ns.metadata.creation_timestamp

    # max() avec key= pour trouver le pod le plus récemment créé
    # key=lambda p: p.metadata.creation_timestamp compare les datetimes
    return max(pods, key=lambda p: p.metadata.creation_timestamp).metadata.creation_timestamp


def is_stale(namespace_name: str, max_age_days: int) -> Tuple[bool, int]:
    """
    Détermine si un namespace est considéré obsolète.

    Retourne un tuple (est_obsolète, age_en_jours) :
    - Tuple plutôt qu'un seul bool pour éviter d'appeler get_last_activity() deux fois
    - L'age est utile pour le logging (informer l'opérateur de l'ancienneté)

    timedelta.days : partie entière du nombre de jours écoulés
    (now - last_activity) retourne un timedelta, .days donne les jours entiers
    """
    last_activity = get_last_activity(namespace_name)
    if not last_activity:
        # Pas de timestamp = considéré obsolète avec age inconnu
        return True, -1

    # timezone.utc rend datetime.now() comparable aux timestamps K8s (timezone-aware)
    now = datetime.now(timezone.utc)
    age_days = (now - last_activity).days
    return age_days >= max_age_days, age_days


def delete_namespace(name: str, dry_run: bool = True) -> str:
    """
    Supprime un namespace et TOUTES ses ressources (cascade automatique).

    La suppression d'un namespace est IRRVERSIBLE et COMPLÈTE :
    - Pods, Services, ConfigMaps, Secrets, PVCs...
    - Les PVs liés peuvent être libérés selon la reclaimPolicy

    C'est pourquoi dry_run=True est la valeur par défaut.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would delete: {name}")
        return "dry-run"
    client.CoreV1Api().delete_namespace(name=name)
    logger.warning(f"Deleted namespace: {name}")
    return "deleted"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cleanup stale ephemeral Kubernetes namespaces")
    parser.add_argument("--prefix", required=True, help="Préfixe des namespaces cibles (ex: pr-)")
    parser.add_argument("--max-age-days", type=int, default=7, help="Age max avant suppression (défaut: 7)")
    parser.add_argument("--delete", action="store_true", help="Supprimer les namespaces obsolètes")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans supprimer")
    parser.add_argument("--in-cluster", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        load_kube_config(in_cluster=parsed.in_cluster)

        namespaces = list_namespaces(parsed.prefix)
        logger.info(f"Found {len(namespaces)} namespace(s) with prefix '{parsed.prefix}'")

        stale = []
        for ns in namespaces:
            name = ns.metadata.name
            # is_stale retourne un tuple → déstructuration en deux variables
            is_old, age = is_stale(name, parsed.max_age_days)
            label = f"STALE ({age}d)" if is_old else f"active ({age}d)"
            logger.info(f"  {name}: {label}")
            if is_old:
                stale.append(name)

        logger.info(f"{len(stale)} namespace(s) to clean up")

        if parsed.delete:
            for name in stale:
                delete_namespace(name, dry_run=parsed.dry_run)

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
