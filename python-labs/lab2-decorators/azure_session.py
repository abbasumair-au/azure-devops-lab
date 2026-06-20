import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class AzureConnectionError(Exception):
    """Levée quand la connexion Azure échoue."""
    pass


class AzureSession:
    """
    Context manager pour les sessions Azure.

    Usage:
        with AzureSession(subscription_id="xxx") as session:
            resources = session.get_resources()
    """

    def __init__(self, subscription_id: str, timeout: int = 30):
        self.subscription_id = subscription_id
        self.timeout = timeout
        self._connected = False
        self._client: Optional[Dict[str, Any]] = None

    def __enter__(self) -> "AzureSession":
        # TODO:
        # - Logger "Connecting to Azure subscription <id>..."
        # - Si subscription_id est vide ou None → lever AzureConnectionError
        # - Sinon: self._connected = True, self._client = {"subscription": subscription_id}
        # - Retourner self
        raise NotImplementedError

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # TODO:
        # - Logger "Closing Azure session"
        # - Reset self._connected = False, self._client = None
        # - Retourner False (ne pas supprimer les exceptions)
        raise NotImplementedError

    def get_resources(self) -> list:
        """Retourne les ressources de la session courante."""
        # TODO:
        # - Si pas connecté → lever RuntimeError("Session not active")
        # - Sinon retourner [{"id": "vm-001", "subscription": self.subscription_id}]
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        return self._connected
