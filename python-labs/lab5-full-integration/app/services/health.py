from datetime import datetime
from typing import List, Dict, Any, Optional

_RESOURCES = [
    {"id": "vm-001", "type": "VirtualMachine", "region": "eastus", "compliant": True},
    {"id": "sa-001", "type": "StorageAccount", "region": "westeurope", "compliant": False},
    {"id": "vm-002", "type": "VirtualMachine", "region": "westeurope", "compliant": True},
    {"id": "pip-001", "type": "PublicIPAddress", "region": "eastus", "compliant": False},
]


class HealthService:

    def get_status(self) -> Dict[str, Any]:
        # TODO: retourner {"status": "ok", "timestamp": <ISO>, "version": "1.0.0"}
        raise NotImplementedError

    def get_resources(
        self,
        resource_type: Optional[str] = None,
        region: Optional[str] = None,
        compliant: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Filtre _RESOURCES selon les paramètres.
        `compliant` est une string "true"/"false" (venant des query params).
        """
        # TODO: filtrer case-insensitive, convertir compliant string → bool si fourni
        raise NotImplementedError

    def get_resource(self, resource_id: str) -> Optional[Dict[str, Any]]:
        # TODO: retourner le resource avec cet id, ou None si pas trouvé
        raise NotImplementedError
