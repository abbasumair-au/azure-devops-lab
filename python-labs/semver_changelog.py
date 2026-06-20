#!/usr/bin/env python3
"""
Génère un bump de version sémantique et des notes de release depuis les commits Git.
Suit la convention Conventional Commits :
  feat:             → bump minor
  fix:              → bump patch
  BREAKING CHANGE   → bump major

Usage:
    python semver_changelog.py --repo . --auto
    python semver_changelog.py --repo . --bump minor --output CHANGELOG.md
    python semver_changelog.py --repo . --auto --tag --dry-run
"""

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional

import git  # pip install gitpython

logger = logging.getLogger(__name__)

# ── PATTERNS CONVENTIONAL COMMITS ────────────────────────────────────────────
# La convention Conventional Commits définit un format standardisé :
# <type>(<scope>)!: <description>
#
# - type   : feat, fix, chore, docs, refactor, ci, test, etc.
# - scope  : composant affecté (optionnel), ex: fix(auth): ...
# - !      : indique un BREAKING CHANGE (alternative à "BREAKING CHANGE" dans le body)
#
# POURQUOI re.compile() en dehors des fonctions ?
# Les expressions régulières sont compilées (parsées) au moment de re.compile().
# Si on appelait re.match(pattern_str, text) dans une boucle, Python recompilerait
# le pattern à chaque itération (lent pour des milliers de commits).
# En compilant une fois au démarrage, la regex est réutilisée sans recompilation.
PATTERNS = {
    # breaking : cherche dans TOUT le message (pas seulement la première ligne)
    # "BREAKING CHANGE" dans le body OR "!:" dans l'en-tête
    "breaking": re.compile(r"BREAKING CHANGE|!:"),
    # feat, fix, etc. : match seulement en DÉBUT de ligne (^)
    # (\(.+\))? : scope optionnel entre parenthèses
    # !?        : "!" optionnel pour BREAKING CHANGE inline
    "feat":     re.compile(r"^feat(\(.+\))?!?:"),
    "fix":      re.compile(r"^fix(\(.+\))?!?:"),
    "refactor": re.compile(r"^refactor(\(.+\))?:"),
    "ci":       re.compile(r"^ci(\(.+\))?:"),
    "docs":     re.compile(r"^docs(\(.+\))?:"),
    "chore":    re.compile(r"^chore(\(.+\))?:"),
}


def parse_version(version_str: str) -> Tuple[int, int, int]:
    """
    Parse une string semver en tuple de 3 entiers.

    lstrip("v") : supprimer le "v" préfixe optionnel.
    "v1.2.3".lstrip("v") → "1.2.3"
    "1.2.3".lstrip("v")  → "1.2.3" (pas de "v" = pas de changement)

    Retourne un tuple car les tuples sont immuables et hashables.
    On compare les versions avec les opérateurs Python natifs sur les tuples :
    (1, 2, 3) < (1, 3, 0) → True (compare élément par élément)
    """
    parts = version_str.lstrip("v").split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid semver: {version_str}")
    # tuple() sur un générateur d'ints
    return tuple(int(p) for p in parts)


def bump_version(current: Tuple[int, int, int], bump_type: str) -> Tuple[int, int, int]:
    """
    Applique les règles SemVer 2.0 :

    MAJOR (breaking change) : X.0.0
    - Incrémenter MAJOR, réinitialiser minor ET patch à 0
    - 1.5.3 → 2.0.0

    MINOR (nouvelle feature, backward-compatible) : x.Y.0
    - Incrémenter MINOR, réinitialiser patch à 0
    - 1.5.3 → 1.6.0

    PATCH (bug fix, backward-compatible) : x.y.Z
    - Incrémenter PATCH seulement
    - 1.5.3 → 1.5.4

    IMPORTANT : on retourne un NOUVEAU tuple, pas de mutation.
    Les tuples étant immuables, Python nous force à cette bonne pratique.
    """
    major, minor, patch = current  # déstructuration du tuple en 3 variables
    if bump_type == "major":
        return major + 1, 0, 0   # reset minor et patch
    elif bump_type == "minor":
        return major, minor + 1, 0  # reset patch seulement
    elif bump_type == "patch":
        return major, minor, patch + 1
    raise ValueError(f"Unknown bump type: {bump_type}")


def get_latest_tag(repo: git.Repo) -> str:
    """
    Retourne le dernier tag Git (semver) ou '0.0.0' si aucun tag n'existe.

    git describe --tags --abbrev=0 :
    - --tags    : inclure les tags légers (pas seulement les tags annotés)
    - --abbrev=0 : retourner seulement le nom du tag (pas "v1.2.3-5-gabcdef")

    GitCommandError est levée si aucun tag n'existe dans le repo.
    On retourne "0.0.0" comme version initiale dans ce cas.
    """
    try:
        return repo.git.describe("--tags", "--abbrev=0")
    except git.GitCommandError:
        return "0.0.0"


def get_commits_since_tag(repo: git.Repo) -> List[git.Commit]:
    """
    Retourne les commits depuis le dernier tag (pour générer le changelog).

    iter_commits("tag..HEAD") : notation Git "range"
    "v1.2.3..HEAD" = tous les commits entre le tag et HEAD (non inclus le tag).

    CAS SANS TAG : repo tout neuf sans release.
    iter_commits("HEAD") retourne TOUS les commits depuis le début.
    """
    try:
        last_tag = repo.git.describe("--tags", "--abbrev=0")
        return list(repo.iter_commits(f"{last_tag}..HEAD"))
    except git.GitCommandError:
        return list(repo.iter_commits("HEAD"))


def determine_bump_type(commits: List[git.Commit]) -> str:
    """
    Détermine automatiquement le type de bump selon les messages de commit.

    PRIORITÉ STRICTE (dès qu'un type est trouvé, on s'arrête) :
    1. Breaking change → major (peu importe les autres commits)
    2. Feature         → minor (si pas de breaking)
    3. Sinon           → patch (par défaut conservateur)

    any() avec un générateur : évalue paresseusement — s'arrête au premier True.
    C'est plus efficace que d'itérer tous les commits pour chaque type.

    .search() vs .match() :
    - .match() : cherche seulement en DÉBUT de string
    - .search() : cherche n'importe où dans la string
    Pour "BREAKING CHANGE" on utilise .search() car il peut être dans le body du commit.
    """
    if any(PATTERNS["breaking"].search(c.message) for c in commits):
        return "major"
    if any(PATTERNS["feat"].match(c.message) for c in commits):
        return "minor"
    return "patch"


def group_commits(commits: List[git.Commit]) -> Dict[str, List[str]]:
    """
    Regroupe les commits par type pour le changelog.

    Dict comprehension avec tous les types comme clés initiales (listes vides).
    On exclut "breaking" car ce n'est pas un type de section dans le changelog
    (les commits breaking sont souvent aussi des "feat!" ou "fix!").

    LOGIQUE DE MATCHING :
    1. Prendre seulement la première ligne du message (le sujet)
    2. Essayer chaque pattern dans l'ordre
    3. Premier match → affecter au groupe correspondant → break
    4. Aucun match → "other"

    break après le premier match : évite de classer un commit dans plusieurs groupes.
    """
    groups: Dict[str, List[str]] = {k: [] for k in PATTERNS if k != "breaking"}
    groups["other"] = []

    for commit in commits:
        # strip() : supprimer les espaces/newlines en début/fin
        # split("\n")[0] : garder seulement la première ligne (le sujet)
        subject = commit.message.strip().split("\n")[0]
        matched = False
        for group, pattern in PATTERNS.items():
            if group == "breaking":
                continue  # "breaking" n'est pas une section de changelog
            if pattern.match(subject):
                groups[group].append(subject)
                matched = True
                break
        if not matched:
            groups["other"].append(subject)

    # Ne retourner que les groupes non vides → changelog sans sections vides
    return {k: v for k, v in groups.items() if v}


def generate_changelog(new_version: str, commits: List[git.Commit]) -> str:
    """
    Génère les notes de release en Markdown suivant le format Keep a Changelog.

    Format : ## Version — Date, avec sections par type de commit.

    ORDRE DES SECTIONS :
    section_titles est un dict ordonné (Python 3.7+ garantit l'ordre d'insertion).
    L'ordre ici correspond à l'importance : Features > Bug Fixes > Refactoring > etc.
    On itère dans cet ordre pour le changelog, même si group_commits retourne un autre ordre.

    + [""] à la fin de chaque section : ligne vide entre les sections.
    """
    section_titles = {
        "feat":     "✨ New Features",
        "fix":      "🐛 Bug Fixes",
        "refactor": "♻️  Refactoring",
        "ci":       "⚙️  CI/CD",
        "docs":     "📖 Documentation",
        "chore":    "🔧 Chores",
        "other":    "📝 Other",
    }
    groups = group_commits(commits)
    lines = [f"## {new_version} — {datetime.utcnow().strftime('%Y-%m-%d')}", ""]

    for section, title in section_titles.items():
        if section in groups:
            # [f"- {msg}" for ...] : liste de strings Markdown bullet points
            # + [""] : ajouter une ligne vide après la section
            lines += [f"### {title}"] + [f"- {msg}" for msg in groups[section]] + [""]

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """
    add_mutually_exclusive_group(required=True) :
    Garantit que l'utilisateur choisit EXACTEMENT UNE des deux options.
    - --bump major|minor|patch : bump manuel explicite
    - --auto                   : bump automatique depuis les commits

    required=True : une des deux DOIT être fournie (sinon erreur).
    Les deux ne peuvent pas être fournies en même temps (mutually exclusive).
    Cela remplace une validation manuelle et génère un message d'erreur clair.
    """
    parser = argparse.ArgumentParser(description="Semantic Versioning + Changelog Generator")
    parser.add_argument("--repo", default=".", help="Chemin du repo Git (défaut: .)")

    bump_group = parser.add_mutually_exclusive_group(required=True)
    bump_group.add_argument("--bump", choices=["major", "minor", "patch"], help="Type de bump manuel")
    bump_group.add_argument("--auto", action="store_true", help="Déterminer le bump depuis les commits")

    parser.add_argument("--output", help="Fichier de sortie (ex: CHANGELOG.md) — sera prepend")
    parser.add_argument("--tag", action="store_true", help="Créer un tag Git pour la nouvelle version")
    parser.add_argument("--dry-run", action="store_true", help="Afficher sans écrire ni tagger")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        repo = git.Repo(parsed.repo)
        current_tag = get_latest_tag(repo)
        current_version = parse_version(current_tag)
        logger.info(f"Current version: {current_tag}")

        commits = get_commits_since_tag(repo)
        logger.info(f"Commits since last tag: {len(commits)}")

        # parsed.bump est None si --auto est utilisé, et vice versa
        bump_type = parsed.bump if parsed.bump else determine_bump_type(commits)
        logger.info(f"Bump type: {bump_type}")

        # ".".join(str(v) for v in tuple) : convertit (1, 3, 0) → "1.3.0"
        new_version = "v" + ".".join(str(v) for v in bump_version(current_version, bump_type))
        logger.info(f"New version: {new_version}")

        changelog = generate_changelog(new_version, commits)
        print(changelog)  # toujours afficher, même sans --output

        if parsed.dry_run:
            return 0  # sortir tôt — pas d'écriture, pas de tag

        if parsed.output:
            output_path = Path(parsed.output)
            # PREPEND : ajouter les nouvelles notes AVANT l'ancien contenu.
            # Ainsi le CHANGELOG.md a toujours les versions les plus récentes en haut.
            existing = output_path.read_text() if output_path.exists() else ""
            output_path.write_text(changelog + "\n" + existing)
            logger.info(f"Changelog written to {parsed.output}")

        if parsed.tag:
            # create_tag avec message → tag annoté (recommandé pour les releases)
            # Les tags annotés sont plus lourds (objet Git séparé) mais recommandés
            # pour les releases car ils stockent l'auteur, la date, et le message.
            repo.create_tag(new_version, message=f"Release {new_version}")
            # On NE push PAS automatiquement : la décision de push appartient à l'opérateur
            logger.info(f"Tag '{new_version}' created — push with: git push --tags")

        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
