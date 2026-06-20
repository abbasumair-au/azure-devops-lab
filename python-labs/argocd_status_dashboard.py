#!/usr/bin/env python3
"""
Tableau de bord du statut sync/health de toutes les apps ArgoCD.
Détecte le drift entre Git et le cluster. Optionnellement bloque le CI si drift détecté.

Usage:
    python argocd_status_dashboard.py --server argocd.example.com --token <tok>
    python argocd_status_dashboard.py --server argocd.example.com --token <tok> --fail-on-drift
    python argocd_status_dashboard.py --server argocd.example.com --token <tok> --no-verify-ssl
"""

import argparse
import json
import logging
import sys
from typing import List, Dict, Any

import requests
import urllib3

# urllib3 est la bibliothèque sous-jacente utilisée par requests.
# disable_warnings() supprime les warnings SSL qui apparaissent quand verify=False.
# Sans cette ligne, chaque requête afficherait :
#   InsecureRequestWarning: Unverified HTTPS request is being made to host 'argocd.example.com'
#
# On désactive globalement parce que dans un lab/staging, le cert self-signed est attendu.
# En production avec un cert valide, ne pas utiliser --no-verify-ssl.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


def get_apps(server: str, token: str, verify_ssl: bool = True) -> List[Dict[str, Any]]:
    """
    Récupère toutes les applications ArgoCD via l'API REST.

    AUTHENTIFICATION ARGOCD :
    Le token s'obtient de deux façons :
    1. argocd login + argocd account generate-token
    2. POST /api/v1/session avec {"username": "...", "password": "..."} → retourne {"token": "..."}

    STRUCTURE DE LA RÉPONSE :
    {
      "items": [
        {
          "metadata": {"name": "myapp"},
          "spec": {
            "destination": {"namespace": "prod"},
            "project": "default",
            "source": {"repoURL": "https://github.com/..."}
          },
          "status": {
            "sync":   {"status": "Synced",  "revision": "abc1234def"},
            "health": {"status": "Healthy"}
          }
        }
      ]
    }

    DEUX STATUTS DISTINCTS (à ne pas confondre) :
    - sync_status  : état GitOps → Git == Cluster ?
      * Synced    : le cluster correspond exactement à Git
      * OutOfSync : le cluster diverge de Git (drift)
      * Unknown   : ArgoCD ne peut pas vérifier

    - health_status : état de l'application elle-même
      * Healthy     : tous les pods Running + Ready
      * Progressing : en cours de déploiement/rollout
      * Degraded    : pods KO, crash, timeout
      * Suspended   : sync désactivé manuellement
      * Missing     : la ressource n'existe pas dans le cluster

    Un app peut être "Synced" mais "Degraded" :
    le cluster a bien le bon manifeste, mais les pods ne démarrent pas.

    verify=verify_ssl : False pour les certs self-signed (labs/staging).
    """
    url = f"https://{server}/api/v1/applications"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"}, verify=verify_ssl)
    resp.raise_for_status()

    return [
        {
            "name": app["metadata"]["name"],
            "namespace": app["spec"].get("destination", {}).get("namespace", ""),
            "project": app["spec"].get("project", "default"),
            "sync_status": app["status"].get("sync", {}).get("status", "Unknown"),
            "health_status": app["status"].get("health", {}).get("status", "Unknown"),
            "repo": app["spec"].get("source", {}).get("repoURL", ""),
            # [:7] : raccourcir le SHA Git à 7 caractères (comme GitHub l'affiche)
            "revision": app["status"].get("sync", {}).get("revision", "")[:7],
        }
        for app in resp.json().get("items", [])
    ]


def format_dashboard(apps: List[Dict[str, Any]]) -> str:
    """
    Tableau ASCII avec icônes Unicode pour une lecture rapide dans le terminal.

    Alignement avec f-string format specs :
    {app['name']:<22} : aligner à gauche dans 22 caractères
    {sync:<18}        : aligner à gauche dans 18 caractères
    Cela crée des colonnes alignées même si les noms ont des longueurs différentes.

    Les icônes sont suffisamment distinctes pour être lisibles même en noir et blanc.
    """
    sync_icons = {"Synced": "✅", "OutOfSync": "⚠️ ", "Unknown": "❓"}
    health_icons = {
        "Healthy": "💚", "Progressing": "🔄", "Degraded": "🔴",
        "Suspended": "⏸️ ", "Missing": "❌", "Unknown": "❓",
    }
    sep = "-" * 70
    lines = [
        "", "ArgoCD Application Status", sep,
        f"{'APP':<22} {'SYNC':<18} {'HEALTH':<18} {'REV'}", sep,
    ]

    for app in apps:
        sync = f"{sync_icons.get(app['sync_status'], '?')} {app['sync_status']}"
        health = f"{health_icons.get(app['health_status'], '?')} {app['health_status']}"
        lines.append(f"{app['name']:<22} {sync:<18} {health:<18} {app['revision']}")

    lines.append(sep)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ArgoCD Applications Status Dashboard")
    parser.add_argument("--server", required=True, help="Hostname ArgoCD (sans https://)")
    parser.add_argument("--token", required=True, help="ArgoCD API token")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Désactiver la vérification SSL")
    parser.add_argument("--output-json", help="Exporter les données en JSON")
    parser.add_argument(
        "--fail-on-drift", action="store_true",
        help="Exit 1 si une app est OutOfSync ou Degraded (gate CI post-déploiement)",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    """
    Cas d'usage CI/CD :
    Après un déploiement ArgoCD, lancer ce script avec --fail-on-drift pour
    vérifier que la synchronisation s'est bien terminée avant de continuer
    (ex: avant de lancer les tests d'intégration).
    """
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        # parsed.no_verify_ssl = True → verify_ssl = False
        apps = get_apps(parsed.server, parsed.token, verify_ssl=not parsed.no_verify_ssl)
        # print() plutôt que logger : le tableau va sur stdout (propre)
        # Les logs d'erreur vont sur stderr via logging (séparables par redirection)
        print(format_dashboard(apps))

        drift = [a for a in apps if a["sync_status"] == "OutOfSync"]
        degraded = [a for a in apps if a["health_status"] == "Degraded"]

        if drift:
            logger.warning(f"{len(drift)} app(s) OutOfSync: {[a['name'] for a in drift]}")
        if degraded:
            logger.error(f"{len(degraded)} app(s) Degraded: {[a['name'] for a in degraded]}")

        if parsed.output_json:
            with open(parsed.output_json, "w") as f:
                json.dump(apps, f, indent=2)
            logger.info(f"Data saved to {parsed.output_json}")

        # drift OR degraded : l'un OU l'autre suffit pour bloquer le pipeline
        if parsed.fail_on_drift and (drift or degraded):
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
