import pytest
import json
import sys
from pathlib import Path

# sys.path.insert : ajoute le dossier parent (lab1-resource-inventory/) au chemin de recherche
# de Python, pour qu'on puisse faire "from resource_inventory import ..."
# sans installer le module. __file__ = chemin de CE fichier de test.
sys.path.insert(0, str(Path(__file__).parent.parent))
from resource_inventory import Resource, ResourceInventory


# ─── FIXTURES ────────────────────────────────────────────────────────────────
# Une fixture pytest est une fonction décorée avec @pytest.fixture.
# pytest l'injecte automatiquement dans les tests qui déclarent son nom
# comme paramètre. C'est l'équivalent d'un "setup" réutilisable.

@pytest.fixture
def sample_file(tmp_path):
    # tmp_path est une fixture BUILT-IN de pytest : elle crée un dossier
    # temporaire unique pour chaque test, supprimé automatiquement après.
    # Cela évite de polluer le disque avec des fichiers de test.
    data = [
        {"id": "vm-001", "type": "VirtualMachine",  "region": "eastus",     "tags": {"env": "prod"}, "compliant": True},
        {"id": "sa-001", "type": "StorageAccount",   "region": "westeurope", "tags": {"env": "dev"},  "compliant": False},
        {"id": "vm-002", "type": "VirtualMachine",   "region": "westeurope", "tags": {"env": "dev"},  "compliant": True},
        {"id": "pip-001","type": "PublicIPAddress",  "region": "eastus",     "tags": {},              "compliant": False},
        {"id": "sa-002", "type": "StorageAccount",   "region": "eastus",     "tags": {"env": "prod"}, "compliant": True},
    ]
    # tmp_path / "resources.json" : syntaxe Path pour construire un chemin
    # write_text() écrit le contenu dans le fichier (le crée s'il n'existe pas)
    # json.dumps() convertit la liste Python en string JSON
    f = tmp_path / "resources.json"
    f.write_text(json.dumps(data))
    return str(f)  # retourne le chemin en string car load_from_file attend un str


@pytest.fixture
def inventory(sample_file):
    # Cette fixture DÉPEND de sample_file : pytest résout les dépendances automatiquement.
    # Résultat : chaque test qui utilise "inventory" reçoit un ResourceInventory
    # déjà chargé avec les 5 ressources de sample_file.
    return ResourceInventory.load_from_file(sample_file)


# ─── TESTS DE LA CLASSE Resource ─────────────────────────────────────────────
# Convention pytest : les classes de test commencent par "Test", les méthodes par "test_".
# Pas besoin de __init__ ni d'hériter d'une classe de base.

class TestResource:

    def test_repr_contains_id(self):
        r = Resource("vm-001", "VirtualMachine", "eastus", {"env": "prod"}, True)
        # repr(r) appelle __repr__ sur l'objet.
        # On vérifie que l'id est INCLUS dans la représentation (pas qu'il soit exactement égal),
        # ce qui laisse de la flexibilité sur le format exact.
        assert "vm-001" in repr(r)

    def test_repr_contains_type(self):
        r = Resource("vm-001", "VirtualMachine", "eastus", {}, True)
        assert "VirtualMachine" in repr(r)

    def test_equality_same_id(self):
        # Cas clé : deux objets avec le MÊME id mais des attributs différents.
        # r1 est une VM prod, r2 est un StorageAccount dev → mais même id "vm-001".
        # Le test vérifie que __eq__ compare UNIQUEMENT sur l'id.
        r1 = Resource("vm-001", "VirtualMachine", "eastus", {}, True)
        r2 = Resource("vm-001", "StorageAccount", "westeurope", {}, False)
        assert r1 == r2  # doit être True car même id

    def test_inequality_different_id(self):
        # Cas inverse : mêmes attributs sauf l'id → doivent être inégaux.
        r1 = Resource("vm-001", "VirtualMachine", "eastus", {}, True)
        r2 = Resource("vm-002", "VirtualMachine", "eastus", {}, True)
        assert r1 != r2  # != appelle __eq__ et inverse le résultat

    def test_to_dict_keys(self):
        r = Resource("vm-001", "VirtualMachine", "eastus", {"env": "prod"}, True)
        d = r.to_dict()
        # On vérifie chaque champ individuellement pour avoir un message d'erreur précis
        # si un champ est manquant ou incorrect.
        assert d["id"] == "vm-001"
        assert d["type"] == "VirtualMachine"
        assert d["region"] == "eastus"
        # "is True" (identité) plutôt que "== True" (égalité) :
        # en Python, 1 == True mais 1 is not True. On veut vraiment un bool.
        assert d["compliant"] is True


# ─── TESTS DE LA CLASSE ResourceInventory ────────────────────────────────────

class TestResourceInventory:

    def test_load_count(self, inventory):
        # inventory est injecté par la fixture définie plus haut.
        # len(inventory) appelle __len__ → retourne len(self.resources).
        # 5 ressources dans sample_file → doit retourner 5.
        assert len(inventory) == 5

    def test_load_file_not_found(self):
        # pytest.raises() est un context manager qui ATTEND une exception.
        # Si l'exception n'est pas levée → le test ÉCHOUE.
        # Si une autre exception est levée → le test ÉCHOUE aussi.
        # Ici on vérifie que load_from_file lève bien FileNotFoundError
        # quand le fichier n'existe pas.
        with pytest.raises(FileNotFoundError):
            ResourceInventory.load_from_file("/nonexistent/path.json")

    def test_load_invalid_json(self, tmp_path):
        # On crée un fichier avec du contenu invalide (pas du JSON).
        # On vérifie que load_from_file lève ValueError (pas JSONDecodeError directement),
        # car on a converti l'exception dans load_from_file avec "raise ValueError from e".
        f = tmp_path / "bad.json"
        f.write_text("not json {{{")
        with pytest.raises(ValueError):
            ResourceInventory.load_from_file(str(f))

    def test_filter_by_type(self, inventory):
        vms = inventory.filter_by_type("VirtualMachine")
        # Vérification 1 : le bon nombre de résultats (2 VMs dans les données)
        assert len(vms) == 2
        # Vérification 2 : TOUS les résultats ont bien le bon type.
        # all() retourne True si la condition est vraie pour CHAQUE élément.
        # C'est plus robuste que de vérifier juste le premier élément.
        assert all(r.type == "VirtualMachine" for r in vms.resources)

    def test_filter_by_type_case_insensitive(self, inventory):
        # On passe "virtualmachine" en minuscules → doit quand même trouver 2 VMs.
        # Valide que le .lower() fonctionne des deux côtés de la comparaison.
        vms = inventory.filter_by_type("virtualmachine")
        assert len(vms) == 2

    def test_filter_by_type_empty_result(self, inventory):
        # Cas limite : aucune ressource de type "KeyVault" dans les données.
        # Le filtre doit retourner un inventaire VIDE (pas None, pas une erreur).
        result = inventory.filter_by_type("KeyVault")
        assert len(result) == 0

    def test_filter_by_region(self, inventory):
        # eastus : vm-001, pip-001, sa-002 → 3 ressources
        eastus = inventory.filter_by_region("eastus")
        assert len(eastus) == 3

    def test_filter_non_compliant(self, inventory):
        nc = inventory.filter_non_compliant()
        # sa-001 et pip-001 sont non conformes → 2 résultats
        assert len(nc) == 2
        # all() avec "not r.compliant" : vérifie qu'AUCUNE ressource retournée
        # n'est conforme. Si une ressource conforme s'était glissée → test échoue.
        assert all(not r.compliant for r in nc.resources)

    def test_chained_filters(self, inventory):
        # Test du chaînage : filter_by_type() retourne un ResourceInventory,
        # sur lequel on appelle filter_non_compliant() immédiatement.
        # Résultat attendu : seulement sa-001 (StorageAccount + non conforme)
        result = inventory.filter_by_type("StorageAccount").filter_non_compliant()
        assert len(result) == 1
        # On vérifie l'id exact pour s'assurer que c'est le bon élément
        assert result.resources[0].id == "sa-001"

    def test_repr(self, inventory):
        # repr(inventory) appelle __repr__ → "ResourceInventory(5 resources)"
        # On vérifie juste que "5" apparaît dans la représentation.
        assert "5" in repr(inventory)
