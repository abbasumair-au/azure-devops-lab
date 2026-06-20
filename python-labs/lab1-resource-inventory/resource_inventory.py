import json
from pathlib import Path
from typing import List, Dict, Any


class Resource:
    """Représente une ressource Azure (VM, StorageAccount, etc.)."""

    def __init__(self, id: str, type: str, region: str, tags: Dict[str, str], compliant: bool):
        # __init__ est appelé automatiquement quand on fait Resource(...)
        # Chaque paramètre devient un attribut de l'objet via self.xxx
        self.id = id
        self.type = type
        self.region = region
        self.tags = tags
        self.compliant = compliant

    def __repr__(self) -> str:
        # __repr__ est la méthode "développeur" : appelée par print(), repr(), et dans le terminal.
        # Convention : retourner quelque chose qui ressemble à du code Python valide.
        # f-string : les {} sont remplacés par la valeur de la variable au runtime.
        return f"Resource(id='{self.id}', type='{self.type}', region='{self.region}')"

    def __eq__(self, other: object) -> bool:
        # __eq__ est appelé quand on fait r1 == r2 ou r1 != r2.
        # Étape 1 : vérifier que l'autre objet est bien un Resource.
        # On retourne NotImplemented (pas False !) pour dire à Python
        # "je ne sais pas comparer avec ce type, délègue à l'autre objet".
        if not isinstance(other, Resource):
            return NotImplemented
        # Étape 2 : deux ressources sont égales si leur id est identique,
        # peu importe le type ou la région.
        return self.id == other.id

    def to_dict(self) -> Dict[str, Any]:
        # Convertit l'objet en dictionnaire Python standard.
        # Utile pour sérialiser en JSON (json.dumps ne connaît pas les classes custom).
        # Dict[str, Any] = dictionnaire avec des clés str et des valeurs de n'importe quel type.
        return {
            "id": self.id,
            "type": self.type,
            "region": self.region,
            "tags": self.tags,
            "compliant": self.compliant,
        }


class ResourceInventory:
    """Collection de ressources Azure avec filtrage chaînable."""

    def __init__(self, resources: List[Resource]):
        self.resources = resources

    @classmethod
    def load_from_file(cls, filepath: str) -> "ResourceInventory":
        """Charge les ressources depuis un fichier JSON."""
        # Path() est plus robuste que les strings pour manipuler des chemins
        # (fonctionne sur Windows et Linux sans se soucier des / vs \).
        path = Path(filepath)

        # Vérifier l'existence AVANT d'ouvrir : donne un message d'erreur plus clair.
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # try/except pour attraper les JSON malformés et les convertir en ValueError.
        # On utilise "raise ... from e" pour garder l'erreur originale dans le traceback
        # (chaînage d'exceptions — visible avec pytest -v).
        try:
            with open(path) as f:
                data = json.load(f)  # parse le JSON → liste de dicts Python
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e

        # List comprehension : pour chaque dict dans data, créer un objet Resource.
        # **item dépaquète le dict en arguments nommés : Resource(id=..., type=..., ...)
        # Équivalent à : [Resource(id=d["id"], type=d["type"], ...) for d in data]
        resources = [Resource(**item) for item in data]

        # cls() au lieu de ResourceInventory() : si une sous-classe hérite de ResourceInventory,
        # cls() créera une instance de la sous-classe, pas de la classe parente.
        return cls(resources)

    def filter_by_type(self, resource_type: str) -> "ResourceInventory":
        """Retourne un NOUVEL inventaire filtré par type (case-insensitive)."""
        # List comprehension avec condition : [expression for item in liste if condition]
        # .lower() sur les deux côtés = comparaison insensible à la casse
        # ("VirtualMachine" == "virtualmachine" → True après .lower())
        filtered = [r for r in self.resources if r.type.lower() == resource_type.lower()]

        # IMPORTANT : on retourne un NOUVEAU ResourceInventory, pas self modifié.
        # Cela permet le chaînage : inventory.filter_by_type("VM").filter_non_compliant()
        # Si on modifiait self, l'inventaire original serait perdu.
        return ResourceInventory(filtered)

    def filter_by_region(self, region: str) -> "ResourceInventory":
        """Retourne un NOUVEL inventaire filtré par région (case-insensitive)."""
        # Même pattern que filter_by_type, mais on compare sur r.region
        filtered = [r for r in self.resources if r.region.lower() == region.lower()]
        return ResourceInventory(filtered)

    def filter_non_compliant(self) -> "ResourceInventory":
        """Retourne un NOUVEL inventaire avec uniquement les ressources non conformes."""
        # "not r.compliant" est équivalent à "r.compliant == False"
        # mais plus idiomatique Python ("Pythonic")
        filtered = [r for r in self.resources if not r.compliant]
        return ResourceInventory(filtered)

    def __len__(self) -> int:
        # __len__ est appelé quand on fait len(inventory).
        # On délègue à len() de la liste interne.
        return len(self.resources)

    def __repr__(self) -> str:
        # len(self) appelle __len__ défini juste au-dessus.
        return f"ResourceInventory({len(self.resources)} resources)"
