#!/usr/bin/env python3
"""Azure Resource Compliance Audit Tool."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml


def setup_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    logging.basicConfig(level=numeric_level, format="%(asctime)s [%(levelname)s] %(message)s")


def load_resources(filepath: str) -> List[Dict[str, Any]]:
    """Charge les ressources depuis un fichier YAML."""
    # TODO:
    # - Lever FileNotFoundError si le fichier n'existe pas
    # - Lire avec yaml.safe_load()
    # - Lever ValueError si le contenu n'est pas une liste
    raise NotImplementedError


def filter_resources(
    resources: List[Dict[str, Any]],
    resource_type: Optional[str] = None,
    region: Optional[str] = None,
    non_compliant_only: bool = False,
) -> List[Dict[str, Any]]:
    """Filtre les ressources. Tous les paramètres sont optionnels, case-insensitive."""
    # TODO: appliquer les 3 filtres (ne filtrer que si le paramètre est fourni)
    raise NotImplementedError


def format_table(resources: List[Dict[str, Any]]) -> str:
    """Formate les ressources en table ASCII."""
    # TODO: retourner un tableau avec colonnes ID | TYPE | REGION | COMPLIANT
    # Le header doit toujours être présent, même si resources est vide
    # Exemple:
    # ID        | TYPE             | REGION       | COMPLIANT
    # ----------+------------------+--------------+----------
    # vm-001    | VirtualMachine   | eastus       | True
    raise NotImplementedError


def format_json(resources: List[Dict[str, Any]]) -> str:
    """Formate les ressources en JSON indenté."""
    # TODO: retourner json.dumps avec indent=2
    raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    """Construit le parser CLI."""
    parser = argparse.ArgumentParser(
        description="Azure Resource Compliance Audit Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # TODO: ajouter tous les arguments (voir README pour la liste complète)
    raise NotImplementedError


def main(args: Optional[List[str]] = None) -> int:
    """Point d'entrée principal. Retourne le code de sortie."""
    parser = build_parser()
    parsed = parser.parse_args(args)

    setup_logging(parsed.log_level)
    logger = logging.getLogger(__name__)

    if parsed.dry_run:
        logger.info("DRY RUN mode — no changes will be made")

    try:
        resources = load_resources(parsed.input)
        logger.info(f"Loaded {len(resources)} resources from {parsed.input}")

        filtered = filter_resources(
            resources,
            resource_type=parsed.resource_type,
            region=parsed.region,
            non_compliant_only=parsed.non_compliant,
        )
        logger.info(f"{len(filtered)} resources after filtering")

        if parsed.output == "json":
            print(format_json(filtered))
        else:
            print(format_table(filtered))

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        return 1
    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
