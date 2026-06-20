#!/usr/bin/env python3
"""
Rotation de secrets Azure Key Vault avec propagation vers GitHub Actions Secrets.
Flux : générer nouveau secret → stocker dans Key Vault → chiffrer + pousser vers GitHub.

Usage:
    python azure_secret_rotation.py --vault myvault --secret db-password --dry-run
    python azure_secret_rotation.py --vault myvault --secret db-password \
        --github-repo org/repo --github-token <PAT>
"""

import argparse
import base64
import logging
import secrets  # module stdlib pour la crypto — différent du module "secrets" Azure
import string
import sys
from typing import Optional

import requests
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# PyNaCl = binding Python pour libsodium (bibliothèque crypto de référence).
# GitHub exige ce chiffrement pour les secrets :
# - Le secret ne transite JAMAIS en clair sur le réseau
# - Seul GitHub peut déchiffrer avec sa clé privée correspondante
from nacl import encoding, public

logger = logging.getLogger(__name__)

SECRET_LENGTH = 32
# string.ascii_letters = a-z + A-Z
# string.digits = 0-9
# Combinaison = 62 + 8 = 70 caractères possibles
# Entropie : log2(70^32) ≈ 197 bits — très difficile à brute-forcer
SECRET_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*"


def get_keyvault_client(vault_name: str) -> SecretClient:
    """
    Crée un client Key Vault.

    L'URL suit TOUJOURS le pattern : https://<vault-name>.vault.azure.net
    On construit l'URL depuis le nom pour éviter les erreurs de saisie.
    """
    credential = DefaultAzureCredential()
    vault_url = f"https://{vault_name}.vault.azure.net"
    return SecretClient(vault_url=vault_url, credential=credential)


def generate_secret(length: int = SECRET_LENGTH) -> str:
    """
    Génère un secret cryptographiquement sûr.

    DIFFÉRENCE CRITIQUE :
    - random.choice()  → pseudo-aléatoire (prévisible, basé sur une seed)
    - secrets.choice() → cryptographiquement sûr (basé sur os.urandom())

    Pour les mots de passe et tokens, toujours utiliser le module `secrets`.
    Le module `random` est réservé aux simulations et au jeu.
    """
    return "".join(secrets.choice(SECRET_ALPHABET) for _ in range(length))


def rotate_keyvault_secret(client: SecretClient, secret_name: str, dry_run: bool = False) -> str:
    """
    Génère un nouveau secret et le stocke dans Key Vault.

    set_secret() crée une NOUVELLE VERSION du secret si le nom existe déjà.
    Key Vault garde l'historique des versions — on peut revenir en arrière.
    La version précédente reste accessible via son ID de version.

    Retourne la nouvelle valeur pour la propager (ex: vers GitHub Secrets).
    """
    new_value = generate_secret()
    if dry_run:
        logger.info(f"[DRY RUN] Would rotate secret '{secret_name}' in Key Vault")
        return new_value
    client.set_secret(secret_name, new_value)
    logger.info(f"Secret '{secret_name}' rotated in Key Vault")
    return new_value


def get_github_public_key(repo: str, token: str) -> dict:
    """
    Récupère la clé publique du repo GitHub.

    Pourquoi une clé publique ?
    GitHub utilise le chiffrement asymétrique :
    - On chiffre le secret avec la CLÉ PUBLIQUE de GitHub
    - Seul GitHub peut déchiffrer avec sa CLÉ PRIVÉE correspondante
    - Même si quelqu'un intercepte la requête API, le secret reste illisible

    La réponse contient :
    - "key"    : la clé publique encodée en Base64
    - "key_id" : l'identifiant de cette clé (doit accompagner le secret chiffré)
    """
    url = f"https://api.github.com/repos/{repo}/actions/secrets/public-key"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    return resp.json()


def encrypt_secret_for_github(public_key_b64: str, secret_value: str) -> str:
    """
    Chiffre le secret avec libsodium (algorithme SealedBox).

    SealedBox = chiffrement asymétrique ANONYME :
    - "Anonyme" signifie que le message chiffré ne révèle pas l'identité de l'expéditeur
    - Seul le destinataire (GitHub) peut déchiffrer
    - Même l'expéditeur ne peut pas déchiffrer après coup

    Étapes :
    1. Décoder la clé publique Base64 → bytes
    2. Créer un SealedBox avec cette clé
    3. Chiffrer le secret (bytes)
    4. Ré-encoder en Base64 → string (l'API GitHub attend du Base64)
    """
    # La clé publique de GitHub est encodée en Base64
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    # .encrypt() retourne des bytes → on les encode en Base64 pour l'API
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(
    repo: str, token: str, secret_name: str, secret_value: str, dry_run: bool = False
) -> None:
    """
    Met à jour un secret GitHub Actions.

    PUT /repos/{repo}/actions/secrets/{name} :
    - Crée le secret s'il n'existe pas
    - Met à jour s'il existe déjà (idempotent)

    Le payload doit contenir :
    - encrypted_value : le secret chiffré en Base64
    - key_id          : l'ID de la clé publique utilisée pour chiffrer
      (GitHub doit savoir quelle clé privée utiliser pour déchiffrer)
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would update GitHub secret '{secret_name}' in {repo}")
        return
    pub_key_data = get_github_public_key(repo, token)
    encrypted = encrypt_secret_for_github(pub_key_data["key"], secret_value)
    url = f"https://api.github.com/repos/{repo}/actions/secrets/{secret_name}"
    resp = requests.put(
        url,
        headers={"Authorization": f"Bearer {token}"},
        json={"encrypted_value": encrypted, "key_id": pub_key_data["key_id"]},
    )
    resp.raise_for_status()
    logger.info(f"GitHub secret '{secret_name}' updated in {repo}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Azure Key Vault Secret Rotation")
    parser.add_argument("--vault", required=True, help="Nom du Key Vault")
    parser.add_argument("--secret", required=True, help="Nom du secret à rotation")
    parser.add_argument("--github-repo", help="Repo GitHub (org/repo) pour propagation")
    parser.add_argument("--github-token", help="GitHub PAT avec scope 'secrets'")
    parser.add_argument("--github-secret-name", help="Nom du secret GitHub (défaut: même nom)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser


def main(args=None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args)
    logging.basicConfig(level=parsed.log_level, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        kv_client = get_keyvault_client(parsed.vault)
        new_value = rotate_keyvault_secret(kv_client, parsed.secret, dry_run=parsed.dry_run)

        if parsed.github_repo:
            if not parsed.github_token:
                logger.error("--github-token required when --github-repo is specified")
                return 1
            # Convention de nommage : "db-password" dans KV → "DB_PASSWORD" dans GitHub
            # Les noms de secrets GitHub ne peuvent pas contenir de tirets, seulement underscores
            gh_name = parsed.github_secret_name or parsed.secret.upper().replace("-", "_")
            update_github_secret(
                parsed.github_repo, parsed.github_token, gh_name, new_value,
                dry_run=parsed.dry_run,
            )

        logger.info("Rotation complete")
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
