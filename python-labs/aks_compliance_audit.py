#!/usr/bin/env python3
"""
Audit de conformité AKS : liste les Deployments sans resource limits/requests.
Un deployment sans limits peut saturer un node et impacter tous les autres workloads.

Usage:
    python aks_compliance_audit.py
    python aks_compliance_audit.py --namespace myapp
    python aks_compliance_audit.py --output-json report.json --fail-on-violation
"""

import argparse
import json
import logging
import sys
from typing import List, Dict, Any, Optional

from kubernetes import client, config

#Crée un objet logger (journaliseur) pour ce module
logger = logging.getLogger(__name__)

#-> None : la fonction ne retourne rien, elle a un effet de bord (configure le client global du SDK Kubernetes).
# Les deux fonctions viennent du package kubernetes (objet config).
def load_kube_config(in_cluster: bool = False) -> None:
    if in_cluster:
        config.load_incluster_config()
    else:
        config.load_kube_config()


def list_deployments(namespace: Optional[str] = None) -> list:
    """
    Liste les deployments Kubernetes.

    DEUX ENDPOINTS SELON LE SCOPE :
    - list_namespaced_deployment(namespace=X)  → un seul namespace
    - list_deployment_for_all_namespaces()     → tous les namespaces
      (équivalent de `kubectl get deploy -A`)

    AppsV1Api gère les workloads : Deployments, DaemonSets, StatefulSets, ReplicaSets.
    """
    apps_v1 = client.AppsV1Api()
    if namespace:
        return apps_v1.list_namespaced_deployment(namespace=namespace).items
    return apps_v1.list_deployment_for_all_namespaces().items


def check_resources(deployment) -> Dict[str, Any]:
    """
    Vérifie que chaque container du deployment a des resource requests ET limits.

    POURQUOI C'EST IMPORTANT :

    REQUESTS (ce que le scheduler réserve) :
    - Le scheduler Kubernetes utilise les requests pour PLACER les pods sur les nodes
    - Sans requests, le scheduler place le pod n'importe où
    - Si le node est saturé, le pod QoS est "BestEffort" et sera le premier tué (OOMKilled)

    LIMITS (le plafond de consommation) :
    - Sans limits CPU : un container peut monopoliser tout le CPU → noisy neighbor problem
    - Sans limits Memory : un container peut consommer toute la RAM → OOMKill de ses voisins

    STRUCTURE D'UN DEPLOYMENT :
    deployment.spec.template.spec.containers = liste des containers
    Chaque container a un champ .resources avec .requests et .limits
    Ces champs peuvent être None si non définis dans le manifest YAML.
    """
    violations = []
    for container in deployment.spec.template.spec.containers:
        missing = []
        res = container.resources
        # resources == None si le bloc resources: {} est absent du manifest
        # On vérifie EXPLICITEMENT la présence de requests ET limits
        if not res or not res.requests:
            missing.append("requests")
        if not res or not res.limits:
            missing.append("limits")
        if missing:
            violations.append({"container": container.name, "missing": missing})

    return {
        "deployment": deployment.metadata.name,
        "namespace": deployment.metadata.namespace,
        # compliant = True seulement si AUCUN container n'a de violation
        "compliant": len(violations) == 0,
        "violations": violations,
    }


def audit_all(namespace: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Audite tous les deployments et retourne un rapport complet.
    List comprehension : applique check_resources() à chaque deployment.
    """
    deployments = list_deployments(namespace)
    logger.info(f"Auditing {len(deployments)} deployment(s)")
    return [check_resources(d) for d in deployments]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AKS Compliance Audit — deployments without resource limits/requests"
    )
    parser.add_argument("--namespace", "-n", help="Namespace à auditer (défaut: tous)")
    parser.add_argument("--output-json", help="Exporter le rapport complet en JSON")
    parser.add_argument(
        "--fail-on-violation", action="store_true",
        help="Exit 1 si au moins une violation (gate CI — bloque le merge)",
    )
    parser.add_argument("--in-cluster", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        load_kube_config(in_cluster=parsed.in_cluster)
        report = audit_all(namespace=parsed.namespace)

        violations = [r for r in report if not r["compliant"]]
        # len(report) - len(violations) = nombre de deployments conformes
        logger.info(f"Compliant: {len(report) - len(violations)}  Violations: {len(violations)}")

        for item in violations:
            # join() pour afficher toutes les violations sur une seule ligne
            details = ", ".join(
                f"{v['container']} missing {v['missing']}" for v in item["violations"]
            )
            logger.warning(f"  VIOLATION {item['namespace']}/{item['deployment']}: {details}")

        if parsed.output_json:
            with open(parsed.output_json, "w") as f:
                # indent=2 → JSON lisible par un humain
                json.dump(report, f, indent=2)
            logger.info(f"Report saved to {parsed.output_json}")

        # --fail-on-violation transforme cet outil en gate CI :
        # le pipeline s'arrête si des deployments non conformes sont trouvés
        if parsed.fail_on_violation and violations:
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
