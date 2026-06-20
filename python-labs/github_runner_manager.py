#!/usr/bin/env python3
"""
Gestion des GitHub Actions self-hosted runners.
Identifie et supprime les runners offline. Liste les runners actifs.

Usage:
    python github_runner_manager.py list --org myorg --token <tok>
    python github_runner_manager.py cleanup-offline --org myorg --token <tok> --dry-run
    python github_runner_manager.py cleanup-offline --org myorg --repo myrepo --token <tok>
"""

import argparse
import logging
import sys
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"


def make_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def list_runners(org: str, token: str, repo: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Liste les runners d'une org ou d'un repo spécifique.

    DEUX NIVEAUX DE RUNNERS :
    - Org-level  : partagés entre tous les repos de l'org
      Endpoint : /orgs/{org}/actions/runners
    - Repo-level : disponibles uniquement pour un repo spécifique
      Endpoint : /repos/{org}/{repo}/actions/runners

    PAGINATION MANUELLE (pattern while True) :
    L'API GitHub retourne au plus 100 items par page.
    Pour des orgs avec beaucoup de runners, on doit paginer.

    Algorithme de pagination :
    1. Récupérer la page 1 avec per_page=100
    2. Si len(runners) < 100 → c'est la dernière page → break
    3. Sinon → il peut y avoir une page suivante → incrémenter page et continuer

    POURQUOI pas len(runners) == 0 pour arrêter ?
    La réponse est une liste vide si la page n'existe pas.
    On gère les deux cas : liste vide (if not runners) et dernière page partielle (< 100).

    CHAMPS DES RUNNERS :
    - status : "online" (connecté et prêt) ou "offline" (déconnecté)
    - busy   : True si en train d'exécuter un job (ne pas supprimer !)
    - labels : liste de labels pour le routing des jobs (ex: ["self-hosted", "linux", "x64"])
    """
    if repo:
        url = f"{GITHUB_API}/repos/{org}/{repo}/actions/runners"
    else:
        url = f"{GITHUB_API}/orgs/{org}/actions/runners"

    all_runners, page = [], 1
    while True:
        resp = requests.get(url, headers=make_headers(token), params={"per_page": 100, "page": page})
        resp.raise_for_status()
        runners = resp.json().get("runners", [])
        if not runners:
            break  # réponse vide = plus de runners à récupérer
        all_runners.extend(runners)
        if len(runners) < 100:
            break  # dernière page (partielle)
        page += 1

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "status": r["status"],   # "online" ou "offline"
            "busy": r["busy"],       # True = job en cours → ne pas supprimer !
            # Extraire seulement le nom des labels (pas leur id ni type)
            "labels": [l["name"] for l in r.get("labels", [])],
            "os": r.get("os", "unknown"),  # Linux, Windows, macOS
        }
        for r in all_runners
    ]


def delete_runner(
    org: str, runner_id: int, token: str,
    repo: Optional[str] = None, dry_run: bool = True,
) -> str:
    """
    Supprime un runner de l'org ou du repo.

    L'URL de suppression est différente selon le scope (org vs repo).
    On utilise une expression ternaire (if/else inline) pour construire l'URL.

    dry_run=True par défaut : sécurité contre les suppressions accidentelles.

    La suppression ne fait que désinscrire le runner de l'API GitHub.
    Le runner lui-même (la VM/pod) reste actif — il faut le supprimer séparément.
    Le runner remarquera qu'il n'est plus enregistré et s'arrêtera (ou se réenregistre).
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would delete runner #{runner_id}")
        return "dry-run"
    url = (
        f"{GITHUB_API}/repos/{org}/{repo}/actions/runners/{runner_id}"
        if repo else
        f"{GITHUB_API}/orgs/{org}/actions/runners/{runner_id}"
    )
    requests.delete(url, headers=make_headers(token)).raise_for_status()
    logger.warning(f"Deleted runner #{runner_id}")
    return "deleted"


def build_parser() -> argparse.ArgumentParser:
    """
    --skip-busy : éviter de supprimer un runner qui exécute un job.
    En théorie, un runner offline ne peut pas être busy.
    Mais en pratique, il peut y avoir des états transitoires (ex: runner se déconnecte
    en milieu de job à cause d'un problème réseau). Ce flag est une sécurité supplémentaire.
    """
    parser = argparse.ArgumentParser(description="GitHub Self-Hosted Runner Manager")
    parser.add_argument("--token", required=True)
    parser.add_argument("--org", required=True, help="Organisation GitHub")
    parser.add_argument("--repo", help="Repo spécifique (optionnel, sinon org-level)")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Lister tous les runners")

    cleanup = sub.add_parser("cleanup-offline", help="Supprimer les runners offline")
    cleanup.add_argument("--dry-run", action="store_true")
    cleanup.add_argument(
        "--skip-busy", action="store_true",
        help="Ne pas supprimer les runners offline ET busy (sécurité pour états transitoires)",
    )
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        runners = list_runners(parsed.org, parsed.token, repo=getattr(parsed, "repo", None))
        # Compter les online vs offline pour le rapport initial
        online = [r for r in runners if r["status"] == "online"]
        offline = [r for r in runners if r["status"] == "offline"]
        logger.info(f"Runners — Online: {len(online)}  Offline: {len(offline)}")

        if parsed.command == "list":
            for r in runners:
                # [BUSY] visuellement distinctif pour ne pas supprimer par erreur
                busy = " [BUSY]" if r["busy"] else ""
                logger.info(f"  #{r['id']} {r['name']} ({r['status']}){busy} labels={r['labels']}")

        elif parsed.command == "cleanup-offline":
            # Filtrer : parmi les offline, exclure les busy si --skip-busy
            # `not (parsed.skip_busy and r["busy"])` :
            # - Si --skip-busy=False : garder tous les offline (not False = True)
            # - Si --skip-busy=True et r["busy"]=True : exclure (not True = False)
            # - Si --skip-busy=True et r["busy"]=False : garder (not False = True)
            to_delete = [r for r in offline if not (parsed.skip_busy and r["busy"])]
            logger.info(f"{len(to_delete)} runner(s) to remove")
            for runner in to_delete:
                delete_runner(
                    parsed.org, runner["id"], parsed.token,
                    repo=getattr(parsed, "repo", None),
                    dry_run=parsed.dry_run,
                )

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
