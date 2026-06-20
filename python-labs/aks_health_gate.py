#!/usr/bin/env python3
"""
Health gate AKS : vérifie que tous les pods d'un namespace sont Ready.
Utilisé en CI/CD comme étape bloquante entre le déploiement et les tests.
Exit 0 = tout OK, Exit 1 = pods KO ou timeout (bloque le pipeline).

Usage:
    python aks_health_gate.py --namespace myapp
    python aks_health_gate.py --namespace myapp --timeout 120 --label-selector app=myapp
    python aks_health_gate.py --namespace myapp --in-cluster   # depuis un pod CI
"""

import argparse
import logging
import sys
import time
from typing import List, Optional

# Le SDK kubernetes Python expose la même API que kubectl mais en Python.
# Il respecte les mêmes conventions : CoreV1Api pour pods/services/configmaps,
# AppsV1Api pour deployments/daemonsets/statefulsets, etc.
from kubernetes import client, config
from kubernetes.client import V1Pod

logger = logging.getLogger(__name__)


def load_kube_config(in_cluster: bool = False) -> None:
    """
    Charge la configuration Kubernetes.

    DEUX MODES selon l'environnement d'exécution :

    Mode IN-CLUSTER (in_cluster=True) :
    → Le script tourne DANS un pod Kubernetes (ex: job CI dans le cluster)
    → Kubernetes monte automatiquement le token et le CA cert dans /var/run/secrets/
    → config.load_incluster_config() lit ces fichiers montés
    → Zéro configuration manuelle, sécurisé par le RBAC du ServiceAccount

    Mode EXTERNE (in_cluster=False) :
    → Le script tourne en local ou dans un runner CI hors-cluster
    → config.load_kube_config() lit ~/.kube/config (ou la var KUBECONFIG)
    → En GitHub Actions : az aks get-credentials génère ce fichier avant l'exécution
    """
    if in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def get_pods(namespace: str, label_selector: Optional[str] = None) -> List[V1Pod]:
    """
    Retourne la liste des pods d'un namespace.

    label_selector suit exactement la syntaxe kubectl :
    - "app=myapp"              → un seul label
    - "app=myapp,env=prod"     → combinaison AND
    - "app in (myapp, myapp2)" → IN
    - "!deprecated"            → NOT

    Pourquoi filtrer par labels ?
    Un namespace peut contenir des pods système ou de migration temporaires.
    On veut vérifier seulement les pods de l'application déployée.
    """
    v1 = client.CoreV1Api()
    kwargs = {"namespace": namespace}
    if label_selector:
        kwargs["label_selector"] = label_selector
    return v1.list_namespaced_pod(**kwargs).items


def is_pod_ready(pod: V1Pod) -> bool:
    """
    Détermine si un pod est prêt à recevoir du trafic.

    DEUX CONDITIONS REQUISES :

    1. Phase == "Running"
       Les phases possibles : Pending, Running, Succeeded, Failed, Unknown
       - Pending   : en attente de scheduling ou de pull d'image
       - Succeeded : terminé normalement (pour les Jobs — pas pour les Services)
       - Failed    : crashé sans redémarrage
       - Running   : le(s) container(s) tourne(nt) — mais pas forcément prêts !

    2. Condition "Ready" == True
       Un pod "Running" n'est pas forcément prêt :
       - La liveness probe peut être KO
       - La readiness probe peut échouer (ex: app en train de démarrer)
       Kubernetes ajoute la condition "Ready" seulement quand la readiness probe passe.

       status.conditions est une liste de conditions (PodScheduled, Initialized, Ready, etc.)
       On cherche spécifiquement type="Ready".
       La valeur est une STRING "True"/"False" (pas un bool Python).
    """
    if pod.status.phase != "Running":
        return False
    if not pod.status.conditions:
        return False
    for condition in pod.status.conditions:
        if condition.type == "Ready":
            return condition.status == "True"  # comparaison string, pas bool
    return False


def check_health(
    namespace: str,
    label_selector: Optional[str] = None,
    timeout: int = 120,
    interval: int = 5,
) -> bool:
    """
    Polling actif jusqu'à ce que tous les pods soient Ready ou timeout.

    Pourquoi polling et pas un Watch Kubernetes ?
    - Watch est plus efficace (pas de requêtes inutiles) mais plus complexe à implémenter
    - Pour un health gate en CI, le polling simple est suffisant et plus lisible
    - L'intervalle de 5s évite de surcharger l'API server

    deadline = time.time() + timeout : timestamp absolu de fin
    On compare time.time() < deadline à chaque itération.
    C'est plus robuste que compter les itérations (resistant aux lenteurs réseau).
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        pods = get_pods(namespace, label_selector)

        if not pods:
            # Pas de pods = le déploiement n'a peut-être pas encore créé les pods
            logger.warning(f"No pods found in namespace '{namespace}' — retrying...")
            time.sleep(interval)
            continue

        # List comprehension pour récupérer les noms des pods NOT ready
        not_ready = [p.metadata.name for p in pods if not is_pod_ready(p)]

        if not not_ready:
            # Liste vide = TOUS les pods sont ready
            logger.info(f"All {len(pods)} pod(s) Ready in '{namespace}' ✓")
            return True

        remaining = int(deadline - time.time())
        logger.info(f"Waiting... {len(not_ready)} not ready: {not_ready} ({remaining}s left)")
        time.sleep(interval)

    # Timeout atteint : afficher l'état détaillé pour le diagnostic en CI
    logger.error(f"Timeout after {timeout}s. Final pod states:")
    for pod in get_pods(namespace, label_selector):
        state = "Ready" if is_pod_ready(pod) else "NOT READY"
        logger.error(f"  {pod.metadata.name}: {state} (phase={pod.status.phase})")
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AKS Health Gate — bloque le pipeline si les pods ne sont pas Ready"
    )
    parser.add_argument("--namespace", "-n", required=True)
    parser.add_argument("--label-selector", "-l", help="Filtre labels, ex: app=myapp")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout en secondes (défaut: 120)")
    parser.add_argument("--interval", type=int, default=5, help="Intervalle de polling en secondes")
    parser.add_argument("--in-cluster", action="store_true", help="Utiliser la config in-cluster (pod CI)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    """
    Exit codes utilisés comme gate CI :
    - 0 : tous les pods sont Ready → le pipeline continue
    - 1 : timeout ou erreur → le pipeline s'arrête
    """
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        load_kube_config(in_cluster=parsed.in_cluster)
        logger.info(f"Checking health of namespace '{parsed.namespace}'...")

        ok = check_health(
            namespace=parsed.namespace,
            label_selector=parsed.label_selector,
            timeout=parsed.timeout,
            interval=parsed.interval,
        )

        if ok:
            logger.info("Health gate PASSED")
            return 0

        logger.error(f"Health gate FAILED — timeout after {parsed.timeout}s")
        return 1

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
