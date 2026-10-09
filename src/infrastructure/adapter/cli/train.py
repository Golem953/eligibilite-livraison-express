"""Outil d'entraînement (ADR-0003) : entraîne le modèle sur toutes les commandes
labellisées de la base (DATABASE_URL), enregistre la nouvelle version dans MLflow et la désigne champion si
elle fait mieux que le champion actuel.
Paramètres : infrastructure/config/training.toml.

Usage : python -m infrastructure.adapter.cli.train
"""

from infrastructure.adapter.dependency_injection.container import get_train_service


def main() -> None:
    report = get_train_service().train()
    print(
        f"Modèle entraîné sur {report.order_count} commandes, "
        f"enregistré en version {report.model_version}."
    )
    for name, value in report.metrics.items():
        print(f"  {name} : {value:.4f}")

    previous = report.previous_champion_scores
    compared = ", ".join(
        f"{metric} {report.metrics[metric]:.4f}"
        + (f" vs {previous[metric]:.4f}" if previous and metric in previous else "")
        for metric in report.champion_metrics
    )
    if previous is None:
        print(f"Version {report.model_version} désignée champion (premier modèle).")
    elif report.promoted:
        print(f"Version {report.model_version} désignée champion ({compared}).")
    else:
        print(f"Le champion est conservé ({compared}).")


if __name__ == "__main__":
    main()
