from abc import ABC, abstractmethod


class OrderIdGeneratorInterface(ABC):
    """Fournit l'identifiant d'une nouvelle commande, au format CMD-000001."""

    @abstractmethod
    def next_id(self) -> str:
        """Renvoie un identifiant jamais attribué."""
