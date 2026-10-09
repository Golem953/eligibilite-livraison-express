import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
    DatabaseConstraintError,
    Params,
    Row,
)
from infrastructure.repository.migrations import read_migrations

# Versions déjà appliquées. Mêmes règles STRICT que les autres tables (ADR-0001).
_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY NOT NULL CHECK (length(version) BETWEEN 1 AND 100),
    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    CHECK (datetime(applied_at) IS NOT NULL)
) STRICT
"""


class SqliteConnector(DatabaseConnectorInterface):
    """Connecteur SQLite (dev), configuré au maximum de sa rigueur (ADR-0001).

    Une connexion est ouverte par appel : SQLite l'ouvre instantanément, et cela
    évite de partager une connexion entre les threads de FastAPI.
    """

    def __init__(self, database_path: str | Path, migrations_dir: Path) -> None:
        if str(database_path) == ":memory:":
            raise ValueError(
                "SQLite en mémoire n'est pas supporté : chaque appel ouvre une "
                "nouvelle connexion, donc une base vide. Utiliser un fichier."
            )
        self._database_path = Path(database_path)
        self._migrations_dir = migrations_dir

    def create_schema(self) -> None:
        """Applique les migrations pas encore notées dans schema_migrations."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(_CREATE_MIGRATIONS_TABLE)
            applied = {
                row[0]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for migration in read_migrations(self._migrations_dir):
                if migration.version in applied:
                    continue
                # Script et trace dans la même transaction : une migration en
                # échec n'est pas notée et sera retentée au prochain démarrage.
                # La version est sûre à insérer telle quelle (format contrôlé
                # par read_migrations).
                connection.executescript(
                    f"BEGIN;\n{migration.script}\n"
                    "INSERT INTO schema_migrations (version)"
                    f" VALUES ('{migration.version}');\nCOMMIT;"
                )

    def execute(self, query: str, params: Params | None = None) -> int:
        with self._connect() as connection:
            return connection.execute(query, _adapt(params)).rowcount

    def fetch_one(self, query: str, params: Params | None = None) -> Row | None:
        with self._connect() as connection:
            row = connection.execute(query, _adapt(params)).fetchone()
        return dict(row) if row is not None else None

    def fetch_all(self, query: str, params: Params | None = None) -> list[Row]:
        with self._connect() as connection:
            rows = connection.execute(query, _adapt(params)).fetchall()
        return [dict(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._database_path)
        try:
            # Lignes lisibles par nom de colonne (row["hour"]).
            connection.row_factory = sqlite3.Row
            # Désactivées par défaut et non persistantes : à activer à chaque
            # connexion.
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA ignore_check_constraints = OFF")
            with connection:  # commit si tout va bien, rollback sinon
                yield connection
        except sqlite3.IntegrityError as error:
            raise DatabaseConstraintError(str(error)) from error
        finally:
            connection.close()


def _adapt(params: Params | None) -> dict[str, Any]:
    """SQLite n'a pas de type date : les dates sont stockées en texte ISO 8601,
    en UTC et à largeur fixe pour que l'ordre du texte suive l'ordre des dates."""
    if params is None:
        return {}
    return {name: _adapt_value(value) for name, value in params.items()}


def _adapt_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Les dates doivent avoir un fuseau horaire.")
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    return value
