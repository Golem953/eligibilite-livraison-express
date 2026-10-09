from application.port.inbound.train_model_interface import (
    TrainingReport,
    TrainModelInterface,
)
from application.port.outbound.model_repository_interface import (
    ModelRepositoryInterface,
)
from application.port.outbound.model_trainer_interface import ModelTrainerInterface
from application.port.outbound.order_repository_interface import (
    OrderRepositoryInterface,
)


class TrainService(TrainModelInterface):
    """Use case « réentraîner » : lire les commandes labellisées, entraîner,
    enregistrer la nouvelle version, puis la désigner champion si elle fait
    mieux que le champion actuel (ADR-0002, ADR-0003)."""

    def __init__(
        self,
        orders: OrderRepositoryInterface,
        trainer: ModelTrainerInterface,
        models: ModelRepositoryInterface,
        champion_metrics: list[str],
    ) -> None:
        self._orders = orders
        self._trainer = trainer
        self._models = models
        self._champion_metrics = champion_metrics

    def train(self) -> TrainingReport:
        orders = self._orders.find_labelled()
        if not orders:
            raise ValueError("Aucune commande labellisée : rien à entraîner.")
        trained_model = self._trainer.train(orders)
        champion_metrics = self._models.get_champion_metrics()
        version = self._models.save(trained_model)

        promoted = champion_metrics is None or self._beats(
            trained_model.metrics, champion_metrics
        )
        if promoted:
            self._models.promote(version)

        return TrainingReport(
            model_version=version,
            order_count=len(orders),
            metrics=trained_model.metrics,
            promoted=promoted,
            champion_metrics=self._champion_metrics,
            previous_champion_scores=champion_metrics,
        )

    def _beats(self, new: dict[str, float], champion: dict[str, float]) -> bool:
        """Ordre de priorité : le 1er score décide, les suivants départagent les
        égalités. Égalité sur tous les scores : le champion est conservé. Un score
        absent chez le champion (ajouté depuis à la config) donne l'avantage à la
        nouvelle version."""
        for metric in self._champion_metrics:
            if metric not in champion:
                return True
            if new[metric] != champion[metric]:
                return new[metric] > champion[metric]
        return False
