"""
RÉCAPITULATIF PYTHON POUR DEVOPS AZURE
========================================
Script pédagogique : fonctions, décorateurs, POO avancé.
Chaque section est indépendante et commentée. Lis de haut en bas.
Exécute directement avec : python poo_decorateurs_azure_devops.py
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ============================================================
# 1. FONCTIONS DE BASE — une fonction est un objet en Python
# ============================================================

def deployer_ressource(nom):
    """Fonction normale : prend un argument, retourne un résultat."""
    return f"Ressource {nom} déployée"


# On peut stocker une fonction dans une variable, la passer en argument.
action = deployer_ressource
print(action("vm-prod-01"))


# ============================================================
# 2. DÉCORATEURS — ajouter un comportement SANS modifier le code
# ============================================================
# Analogie : un décorateur = un sidecar container.
# Il s'exécute autour de ta fonction (avant/après), sans toucher
# à sa logique métier.

def chrono(fonction):
    """Décorateur simple : mesure le temps d'exécution."""
    def wrapper(*args, **kwargs):
        debut = time.time()
        resultat = fonction(*args, **kwargs)
        duree = time.time() - debut
        print(f"[chrono] {fonction.__name__} a pris {duree:.4f}s")
        return resultat
    return wrapper


def retry(nb_tentatives=3):
    """
    Décorateur AVEC argument (3 niveaux d'imbrication, normal).
    Utile pour les appels réseau/API Azure qui peuvent échouer
    temporairement (throttling, latence, etc.)
    """
    def decorateur(fonction):
        def wrapper(*args, **kwargs):
            derniere_erreur = None
            for tentative in range(1, nb_tentatives + 1):
                try:
                    return fonction(*args, **kwargs)
                except Exception as e:
                    derniere_erreur = e
                    print(f"[retry] Tentative {tentative} échouée : {e}")
            raise RuntimeError(
                f"Échec après {nb_tentatives} tentatives"
            ) from derniere_erreur
        return wrapper
    return decorateur


@chrono
@retry(nb_tentatives=2)
def appeler_api_azure(service):
    """Simule un appel API Azure (ex: récupérer l'état d'un AKS)."""
    print(f"Appel à l'API Azure pour : {service}")
    return f"{service} : OK"


print(appeler_api_azure("AKS-cluster-prod"))


# ============================================================
# 3. CLASSE DE BASE — état + comportement
# ============================================================

class RessourceAzure:
    """
    Classe parent générique pour toute ressource Azure.
    __init__ = constructeur, s'exécute à la création de chaque objet.
    self = référence à l'instance courante (obligatoire en 1er paramètre).
    """

    def __init__(self, nom, region):
        self.nom = nom
        self.region = region
        self._actif = False          # convention _attribut = "privé"

    def demarrer(self):
        self._actif = True
        return f"{self.nom} démarré dans {self.region}"

    def arreter(self):
        self._actif = False
        return f"{self.nom} arrêté"

    # ---- Méthodes spéciales (dunder) ----
    # Elles définissent le comportement natif de l'objet.

    def __repr__(self):
        """Affichage technique (debug) — utilisé par print() par défaut."""
        return f"RessourceAzure(nom={self.nom!r}, region={self.region!r})"

    def __eq__(self, autre):
        """Permet de comparer deux ressources avec =="""
        return self.nom == autre.nom and self.region == autre.region


# ============================================================
# 4. HÉRITAGE — réutiliser et étendre une classe parent
# ============================================================

class ClusterAKS(RessourceAzure):
    """
    Hérite de RessourceAzure. Ajoute des attributs/méthodes propres
    à un cluster AKS, sans dupliquer le code du parent.
    """

    def __init__(self, nom, region, nb_noeuds):
        super().__init__(nom, region)   # appelle __init__ du parent
        self.nb_noeuds = nb_noeuds

    def demarrer(self):
        """Redéfinition (override) : on réutilise le parent puis on l'étend."""
        base = super().demarrer()
        return f"{base} avec {self.nb_noeuds} nœuds"


cluster = ClusterAKS("aks-prod", "westeurope", 5)
print(cluster.demarrer())
print(cluster)   # utilise __repr__ automatiquement


# ============================================================
# 5. PROPERTY — contrôler l'accès à un attribut (validation)
# ============================================================

class VMAzure(RessourceAzure):
    """
    @property permet de valider une donnée à l'écriture,
    sans changer la façon dont l'appelant écrit le code
    (vm.cpu au lieu de vm.set_cpu(...)).
    """

    def __init__(self, nom, region, cpu):
        super().__init__(nom, region)
        self._cpu = cpu

    @property
    def cpu(self):
        return self._cpu

    @cpu.setter
    def cpu(self, valeur):
        if valeur <= 0:
            raise ValueError("Le nombre de CPU doit être positif")
        self._cpu = valeur


vm = VMAzure("vm-web-01", "francecentral", 4)
print(f"CPU actuel : {vm.cpu}")
vm.cpu = 8                      # passe par le setter (validation incluse)
print(f"CPU mis à jour : {vm.cpu}")
# vm.cpu = -1                   # décommenter pour voir l'erreur levée


# ============================================================
# 6. CLASSE ABSTRAITE — forcer une structure commune
# ============================================================
# Utile quand plusieurs types de ressources doivent TOUTES
# implémenter une méthode (ex: chaque ressource doit savoir
# se "valider" avant déploiement).

class RessourceDeployable(ABC):
    @abstractmethod
    def valider_avant_deploiement(self):
        """Toute sous-classe DOIT implémenter cette méthode."""
        pass


class StorageAccount(RessourceAzure, RessourceDeployable):
    def __init__(self, nom, region, tier):
        super().__init__(nom, region)
        self.tier = tier

    def valider_avant_deploiement(self):
        if self.tier not in ("Standard", "Premium"):
            raise ValueError("Tier invalide")
        return f"{self.nom} validé (tier={self.tier})"


storage = StorageAccount("stoprod001", "westeurope", "Standard")
print(storage.valider_avant_deploiement())

# Si on oublie d'implémenter valider_avant_deploiement() dans une
# sous-classe de RessourceDeployable, Python refuse l'instanciation
# avec une erreur claire — ça évite les oublis silencieux.


# ============================================================
# 7. DATACLASS — réduire le boilerplate pour les classes simples
# ============================================================
# Quand une classe sert surtout à stocker des données (pas de
# logique complexe), @dataclass génère __init__, __repr__, __eq__
# automatiquement.

@dataclass
class TagAzure:
    cle: str
    valeur: str


@dataclass
class ConfigDeploiement:
    nom_ressource: str
    region: str = "westeurope"          # valeur par défaut
    tags: list = field(default_factory=list)  # éviter les listes mutables partagées


config = ConfigDeploiement("aks-prod", tags=[TagAzure("env", "prod")])
print(config)   # __repr__ généré automatiquement, lisible direct


# ============================================================
# 8. CONTEXT MANAGER — garantir un nettoyage (with ...)
# ============================================================
# Pattern courant en infra : ouvrir une connexion/session, et
# être SÛR qu'elle se ferme même en cas d'erreur.

class SessionAzureCLI:
    def __enter__(self):
        print("[session] Connexion à Azure CLI...")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("[session] Déconnexion (toujours exécuté, même en cas d'erreur)")
        return False  # False = ne pas avaler l'exception

    def executer(self, commande):
        print(f"[session] az {commande}")


with SessionAzureCLI() as session:
    session.executer("aks show --name aks-prod")


# ============================================================
# RÉCAP : table de correspondance concept → cas d'usage DevOps
# ============================================================
"""
| Concept            | Cas d'usage typique                              |
|---------------------|---------------------------------------------------|
| Décorateur @retry   | Appels API Azure instables                         |
| Décorateur @chrono  | Mesurer la durée d'un déploiement                  |
| Héritage            | RessourceAzure -> ClusterAKS, VMAzure, etc.        |
| @property           | Valider les inputs (cpu, taille disque, etc.)      |
| Classe abstraite    | Forcer toutes les ressources à se "valider"        |
| Dataclass           | Objets de config légers (sans logique complexe)    |
| Context manager     | Sessions CLI/API, fichiers temporaires, locks       |
"""