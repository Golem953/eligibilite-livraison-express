from __future__ import annotations

from app.domain.interface.experiment_tracker_interface import ExperimentTrackerInterface


class FakeTracker(ExperimentTrackerInterface):
    """Tracker factice : garde en mémoire ce qu'on lui envoie, sans MLflow."""

    def __init__(self):
        self.runs: list[dict] = []

    def log_run(self, run_name, params, metrics, model) -> str:
        self.runs.append({"run_name": run_name, "params": params, "metrics": metrics})
        return f"run-{len(self.runs)}"
