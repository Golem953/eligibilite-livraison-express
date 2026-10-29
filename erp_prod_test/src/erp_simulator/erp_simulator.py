"""Point d'entrée du simulateur ERP Dockerisé."""

from __future__ import annotations

import logging

from config import SimulationConfig
from generator import OrderGenerator
from simulator import ErpSimulator
from storage import MongoWriter, PostgresWriter


def main() -> None:
    config = SimulationConfig.from_environment()
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logger = logging.getLogger("erp_simulator")
    logger.info(
        "Démarrage ERP : date=%s, historique PostgreSQL=%d, historique partagé 2023+=%d, live=%s.",
        config.today,
        config.postgres_old_history_orders,
        config.recent_history_orders,
        "illimité" if config.live_order_limit == 0 else config.live_order_limit,
    )
    simulator = ErpSimulator(
        config,
        OrderGenerator(),
        PostgresWriter(config.postgres_dsn),
        MongoWriter(config.mongo_uri),
        logger,
    )
    simulator.run()


if __name__ == "__main__":
    main()
