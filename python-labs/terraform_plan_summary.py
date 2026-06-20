#!/usr/bin/env python3
"""
Parse le JSON d'un plan Terraform et affiche un résumé lisible.
Conçu pour être intégré dans un commentaire de PR GitHub.

Usage:
    terraform show -json tfplan.binary > tfplan.json
    python terraform_plan_summary.py --plan tfplan.json
    python terraform_plan_summary.py --plan tfplan.json --output-md summary.md --fail-on-destroy
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# ── CODES COULEUR ANSI ────────────────────────────────────────────────────────
# \033[NNm = séquence d'échappement ANSI (ESC + [ + code + m)
# \033[0m  = reset (revenir à la couleur par défaut)
# 32 = vert, 33 = jaune, 31 = rouge, 35 = magenta
# Ces séquences fonctionnent dans les terminaux Unix/Mac/Linux et Windows 10+
COLORS = {
    "create":  "\033[32m+\033[0m",   # + en vert  → nouvelle ressource
    "update":  "\033[33m~\033[0m",   # ~ en jaune → modification in-place
    "delete":  "\033[31m-\033[0m",   # - en rouge → suppression
    "replace": "\033[35m±\033[0m",   # ± en magenta → destroy + re-create
}


def load_plan(filepath: str) -> Dict[str, Any]:
    """
    Charge et valide la structure minimale d'un plan Terraform JSON.

    COMMENT GÉNÉRER CE FICHIER :
    1. terraform plan -out=tfplan.binary
    2. terraform show -json tfplan.binary > tfplan.json

    La clé "resource_changes" contient tous les changements prévus.
    Sa présence est le minimum requis pour que ce script fonctionne.

    logger.debug (pas info) car le format_version n'est intéressant qu'en debug.
    """
    with open(filepath) as f:
        plan = json.load(f)
    if "resource_changes" not in plan:
        raise ValueError("Invalid Terraform plan JSON: missing 'resource_changes'")
    logger.debug(f"Plan format version: {plan.get('format_version', '?')}")
    return plan


def extract_changes(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait les ressources qui changent réellement (ignore les no-op).

    STRUCTURE DE resource_changes :
    Chaque ressource a un champ "change" avec :
    - actions : liste des actions → ["no-op"], ["create"], ["update"], ["delete"],
                                    ou ["delete", "create"] pour un REPLACE
    - before  : état avant (null si création)
    - after   : état après (null si suppression)

    CAS PARTICULIER : REPLACE
    ["delete", "create"] signifie que Terraform doit :
    1. DÉTRUIRE l'ancienne ressource
    2. RECRÉER une nouvelle ressource
    C'est différent de ["update"] qui modifie en place.
    Un replace est plus risqué car il y a une période sans la ressource.

    On utilise set(actions) pour la comparaison car l'ordre peut varier.
    """
    changes = []
    for resource in plan.get("resource_changes", []):
        actions = resource.get("change", {}).get("actions", ["no-op"])

        # {"delete", "create"} == {"create", "delete"} → insensible à l'ordre
        if set(actions) == {"delete", "create"}:
            action = "replace"
        elif len(actions) == 1:
            action = actions[0]  # "no-op", "create", "update", ou "delete"
        else:
            action = "no-op"

        # On exclut les no-op du résumé (pas de changement = pas intéressant)
        if action == "no-op":
            continue

        changes.append({
            "action": action,
            "type": resource.get("type", "unknown"),    # ex: azurerm_resource_group
            "name": resource.get("name", "unknown"),    # ex: main
            "address": resource.get("address", ""),     # ex: azurerm_resource_group.main
        })
    return changes


def summarize(changes: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Compte les changements par type d'action.

    defaultdict(int) : un dict où les clés manquantes valent 0 par défaut.
    Sans defaultdict, on devrait écrire :
        counts[action] = counts.get(action, 0) + 1
    Avec defaultdict :
        counts[action] += 1  (plus simple)

    On convertit en dict normal à la fin pour la compatibilité avec json.dumps.
    """
    counts: Dict[str, int] = defaultdict(int)
    for c in changes:
        counts[c["action"]] += 1
    return dict(counts)


def format_terminal(changes: List[Dict[str, Any]], summary: Dict[str, int]) -> str:
    """
    Résumé coloré pour le terminal.

    f"{c['action']:<8}" : alignement à gauche dans 8 caractères
    (équivalent de "%-8s" en C ou str.ljust(8))
    Cela aligne toutes les adresses sur la même colonne.
    """
    lines = ["", "Terraform Plan Summary", "=" * 50]
    for c in changes:
        symbol = COLORS.get(c["action"], "?")
        lines.append(f"  {symbol} {c['action']:<8} {c['address']}")
    lines += [
        "",
        # summary.get("create", 0) : 0 si la clé n'existe pas (aucune création)
        f"Plan: {summary.get('create', 0)} to add, "
        f"{summary.get('update', 0)} to change, "
        f"{summary.get('delete', 0)} to destroy, "
        f"{summary.get('replace', 0)} to replace.",
    ]
    return "\n".join(lines)


def format_markdown(changes: List[Dict[str, Any]], summary: Dict[str, int]) -> str:
    """
    Format Markdown pour commentaire de PR GitHub.

    <details><summary>...</summary>...</details> :
    Balise HTML que GitHub rend comme un accordion.
    Les détails sont cachés par défaut → PR propre même si le plan est long.
    Le lecteur peut cliquer pour développer.

    Ce format est directement utilisable dans :
    - GitHub Actions step avec `gh pr comment`
    - GitHub Apps avec l'API commentaires
    """
    emoji = {"create": "🟢", "update": "🟡", "delete": "🔴", "replace": "🟣"}
    lines = [
        "## Terraform Plan Summary",
        "",
        "| Action | Count |",
        "|--------|-------|",
    ]
    for action, count in summary.items():
        lines.append(f"| {emoji.get(action, '⚪')} {action} | {count} |")

    # Le bloc ``` (code fence) préserve l'espacement dans le commentaire GitHub
    lines += [
        "",
        "<details><summary>Resource details</summary>",
        "",
        "```",
    ]
    for c in changes:
        lines.append(f"{emoji.get(c['action'], '?')} {c['action']:<8} {c['address']}")
    lines += ["```", "", "</details>"]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Terraform Plan JSON Summary")
    parser.add_argument("--plan", "-p", required=True, help="Chemin vers tfplan.json")
    parser.add_argument("--output-md", help="Exporter en Markdown (pour PR comment GitHub)")
    parser.add_argument(
        "--fail-on-destroy", action="store_true",
        help="Exit 1 si des ressources sont détruites — sécurité CI contre les destructions accidentelles",
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        plan = load_plan(parsed.plan)
        changes = extract_changes(plan)
        summary = summarize(changes)

        # print() plutôt que logger.info() : le résumé va sur stdout
        # Les logs vont sur stderr → les deux peuvent être redirigés séparément
        print(format_terminal(changes, summary))

        if parsed.output_md:
            with open(parsed.output_md, "w") as f:
                f.write(format_markdown(changes, summary))
            logger.info(f"Markdown saved to {parsed.output_md}")

        # Gate de sécurité : refuser les plans qui détruisent des ressources
        # sans validation explicite (force l'opérateur à utiliser --fail-on-destroy=false)
        if parsed.fail_on_destroy and summary.get("delete", 0) > 0:
            logger.error(f"Plan contains {summary['delete']} deletion(s) — failing pipeline")
            return 1

        return 0

    except FileNotFoundError:
        logger.error(f"Plan file not found: {parsed.plan}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid plan: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
