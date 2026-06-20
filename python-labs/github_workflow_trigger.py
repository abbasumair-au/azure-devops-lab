#!/usr/bin/env python3
"""
Pilote les GitHub Actions via l'API REST : déclenche des workflows, liste les runs, gère les labels PR.

Usage:
    python github_workflow_trigger.py trigger --repo org/repo --workflow deploy.yml --token <tok>
    python github_workflow_trigger.py trigger --repo org/repo --workflow deploy.yml --token <tok> --wait
    python github_workflow_trigger.py list-runs --repo org/repo --workflow deploy.yml --token <tok>
    python github_workflow_trigger.py label-pr --repo org/repo --pr 42 --label deployed --token <tok>
"""

import argparse
import json
import logging
import sys
import time
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def make_headers(token: str) -> Dict[str, str]:
    """
    Headers communs pour toutes les requêtes GitHub API.

    Authorization: Bearer <token> : le token peut être :
    - Personal Access Token (PAT) : pour usage local/automation
    - GITHUB_TOKEN : token éphémère fourni automatiquement dans les Actions CI

    Accept: application/vnd.github+json : format de réponse JSON v3.
    Sans ce header, l'API peut retourner un format différent.

    X-GitHub-Api-Version: 2022-11-28 : épingle une version stable de l'API.
    GitHub garantit la compatibilité des endpoints pour chaque version datée.
    Sans ce header, on reçoit la version "latest" qui peut changer.
    """
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def trigger_workflow(
    repo: str,
    workflow_id: str,
    token: str,
    ref: str = "main",
    inputs: Optional[Dict[str, str]] = None,
) -> None:
    """
    Déclenche un workflow via l'événement workflow_dispatch.

    workflow_id peut être :
    - Le nom du fichier : "deploy.yml"
    - L'ID numérique du workflow : 12345678

    ref : branche ou tag sur lequel déclencher le workflow.
    La branche doit avoir le workflow_dispatch activé dans son fichier YAML :
      on:
        workflow_dispatch:
          inputs:
            env:
              required: true

    inputs : paramètres passés au workflow (définis dans on.workflow_dispatch.inputs).
    inputs or {} : évite d'envoyer None si inputs n'est pas fourni.

    La réponse est 204 No Content si succès — pas de JSON à parser.
    raise_for_status() lève une exception si le statut HTTP est >= 400.
    """
    url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow_id}/dispatches"
    resp = requests.post(url, headers=make_headers(token), json={"ref": ref, "inputs": inputs or {}})
    resp.raise_for_status()
    logger.info(f"Workflow '{workflow_id}' triggered on ref '{ref}'")


def list_workflow_runs(repo: str, workflow_id: str, token: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retourne les dernières exécutions d'un workflow.

    CHAMPS IMPORTANTS :
    - status     : "queued" → "in_progress" → "completed"
    - conclusion : "success" | "failure" | "cancelled" | "skipped" | None
                   None si le run n'est pas encore terminé (status != "completed")

    params={"per_page": limit} : demande à l'API de retourner au plus `limit` items.
    GitHub API retourne 30 items par page par défaut, max 100.

    On extrait seulement les champs utiles — les runs GitHub contiennent ~50 champs.
    """
    url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{workflow_id}/runs"
    resp = requests.get(url, headers=make_headers(token), params={"per_page": limit})
    resp.raise_for_status()
    return [
        {
            "id": r["id"],
            "status": r["status"],
            "conclusion": r["conclusion"],  # None si en cours
            "created_at": r["created_at"],
            "html_url": r["html_url"],      # lien direct vers le run dans l'UI GitHub
        }
        for r in resp.json().get("workflow_runs", [])
    ]


def wait_for_run(repo: str, run_id: int, token: str, timeout: int = 300, interval: int = 10) -> str:
    """
    Polling actif jusqu'à ce qu'un run soit terminé.

    PATTERN DEADLINE :
    deadline = time.time() + timeout : timestamp absolu de fin
    Plus robuste que compter les itérations car résistant aux lenteurs réseau.

    VALEURS DE CONCLUSION POSSIBLES :
    "success" | "failure" | "cancelled" | "timed_out" | "skipped" | "stale" | "neutral"

    TimeoutError est une exception stdlib Python (pas besoin d'importer).
    Elle signale que l'attente a expiré — différent d'une erreur réseau.
    """
    deadline = time.time() + timeout
    url = f"{GITHUB_API}/repos/{repo}/actions/runs/{run_id}"

    while time.time() < deadline:
        data = requests.get(url, headers=make_headers(token)).json()
        if data["status"] == "completed":
            logger.info(f"Run {run_id} completed: {data['conclusion']}")
            return data["conclusion"]
        remaining = int(deadline - time.time())
        logger.info(f"Run {run_id}: {data['status']}... ({remaining}s left)")
        time.sleep(interval)

    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")


def add_label_to_pr(repo: str, pr_number: int, label: str, token: str) -> None:
    """
    Ajoute un label à une Pull Request.

    PARTICULARITÉ DE L'API GITHUB :
    Les Pull Requests sont techniquement des Issues dans GitHub.
    L'endpoint pour les labels PR est donc /issues/{pr}/labels, PAS /pulls/{pr}/labels.
    C'est contre-intuitif mais documenté officiellement.

    json={"labels": [label]} : l'API attend une liste même pour un seul label.
    On peut en ajouter plusieurs en une seule requête.
    """
    url = f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/labels"
    requests.post(url, headers=make_headers(token), json={"labels": [label]}).raise_for_status()
    logger.info(f"Label '{label}' added to PR #{pr_number}")


def build_parser() -> argparse.ArgumentParser:
    """
    Argparse avec SOUS-COMMANDES via add_subparsers().

    Chaque sous-commande a ses propres arguments :
    - trigger   : --workflow, --ref, --inputs, --wait
    - list-runs : --workflow, --limit
    - label-pr  : --pr, --label

    Les arguments communs (--token, --repo, --log-level) sont sur le parser principal.
    required=True dans add_subparsers() → erreur si aucune sous-commande fournie.
    dest="command" → parsed.command contient la sous-commande choisie ("trigger", etc.)
    """
    parser = argparse.ArgumentParser(description="GitHub Actions Workflow Controller")
    parser.add_argument("--token", required=True, help="GitHub Personal Access Token")
    parser.add_argument("--repo", required=True, help="Repository au format org/repo")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("trigger", help="Déclencher un workflow")
    t.add_argument("--workflow", required=True, help="Nom du fichier workflow (ex: deploy.yml)")
    t.add_argument("--ref", default="main", help="Branche ou tag (défaut: main)")
    t.add_argument("--inputs", help="Inputs JSON (ex: '{\"env\": \"prod\"}')")
    # --wait : bloquer jusqu'à la fin du run et utiliser sa conclusion comme exit code
    # Utile pour : déclencher un workflow de déploiement et attendre qu'il soit OK
    t.add_argument("--wait", action="store_true", help="Attendre la fin du run avant de quitter")

    lr = sub.add_parser("list-runs", help="Lister les derniers runs")
    lr.add_argument("--workflow", required=True)
    lr.add_argument("--limit", type=int, default=5)

    lp = sub.add_parser("label-pr", help="Ajouter un label à une PR")
    lp.add_argument("--pr", type=int, required=True, help="Numéro de la PR")
    lp.add_argument("--label", required=True)

    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        if parsed.command == "trigger":
            # json.loads() convertit la string JSON en dict Python
            # Si --inputs n'est pas fourni, parsed.inputs est None → on utilise {}
            inputs = json.loads(parsed.inputs) if parsed.inputs else {}
            trigger_workflow(parsed.repo, parsed.workflow, parsed.token, parsed.ref, inputs)

            if parsed.wait:
                # PROBLÈME CONNU : workflow_dispatch est asynchrone.
                # Le run n'apparaît pas immédiatement dans l'API après le POST.
                # On attend 3s pour que GitHub enregistre et expose le nouveau run.
                # Sans ce délai, list_workflow_runs() retournerait l'ANCIEN dernier run.
                time.sleep(3)
                runs = list_workflow_runs(parsed.repo, parsed.workflow, parsed.token, limit=1)
                if runs:
                    conclusion = wait_for_run(parsed.repo, runs[0]["id"], parsed.token)
                    # Exit 0 si "success", exit 1 pour tous les autres résultats
                    return 0 if conclusion == "success" else 1

        elif parsed.command == "list-runs":
            for run in list_workflow_runs(parsed.repo, parsed.workflow, parsed.token, parsed.limit):
                logger.info(f"  #{run['id']} [{run['status']}] {run['conclusion']} — {run['created_at']}")

        elif parsed.command == "label-pr":
            add_label_to_pr(parsed.repo, parsed.pr, parsed.label, parsed.token)

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
