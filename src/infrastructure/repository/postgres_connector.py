import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from infrastructure.interface.database_connector_interface import (
    DatabaseConnectorInterface,
    DatabaseConstraintError,
    Params,
    Row,
)
from infrastructure.repository.migrations import read_migrations

# Versions déjà appliquées.
_CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    VARCHAR(100) PRIMARY KEY CHECK (length(version) >= 1),
    applied_at TIMESTAMPTZ  NOT NULL DEFAULT now()
)
"""

# `:nom` mais pas `::type` (cast PostgreSQL) ni `a:b`.
_NAMED_PARAMETER = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


class PostgresConnector(DatabaseConnectorInterface):
    """Connecteur PostgreSQL (CI et prod)."""

    def __init__(self, url: str, migrations_dir: Path) -> None:
        self._url = url
        self._migrations_dir = migrations_dir

    def create_schema(self) -> None:
        """Applique les migrations pas encore notées dans schema_migrations."""
        with self._connect() as connection:
            connection.execute(_CREATE_MIGRATIONS_TABLE)
            connection.commit()
            applied = {
                row[0]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for migration in read_migrations(self._migrations_dir):
                if migration.version in applied:
                    continue
                # Script et trace dans la même transaction : une migration en
                # échec n'est pas notée et sera retentée au prochain démarrage.
                with connection.transaction():
                    # Sans paramètre, psycopg accepte plusieurs instructions.
                    connection.execute(migration.script)
                    connection.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (migration.version,),
                    )

    def execute(self, query: str, params: Params | None = None) -> int:
        with self._connect() as connection:
            return connection.execute(*_to_psycopg(query, params)).rowcount

    def fetch_one(self, query: str, params: Params | None = None) -> Row | None:
        with self._connect() as connection:
            cursor = connection.cursor(row_factory=dict_row)
            return cursor.execute(*_to_psycopg(query, params)).fetchone()

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        try:
            # Le bloc `with` fait commit si tout va bien, rollback sinon, puis
            # ferme la connexion.
            with psycopg.connect(self._url) as connection:
                yield connection
        except (psycopg.IntegrityError, psycopg.DataError) as error:
            raise DatabaseConstraintError(str(error)) from error


def _to_psycopg(query: str, params: Params | None) -> tuple[str, Params | None]:
    """Traduit la convention commune `:nom` vers le format de psycopg
    `%(nom)s`."""
    if params is None:
        return query, None
    escaped = query.replace("%", "%%")
    return _NAMED_PARAMETER.sub(r"%(\1)s", escaped), params
