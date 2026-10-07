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

SCHEMA_PATH = Path(__file__).parent / "schema" / "postgres.sql"

# `:nom` mais pas `::type` (cast PostgreSQL) ni `a:b`.
_NAMED_PARAMETER = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


class PostgresConnector(DatabaseConnectorInterface):
    """Connecteur PostgreSQL (CI et prod)."""

    def __init__(self, url: str) -> None:
        self._url = url

    def create_schema(self) -> None:
        script = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._connect() as connection:
            # Sans paramètre, psycopg accepte plusieurs instructions d'un coup.
            connection.execute(script)

    def execute(self, query: str, params: Params | None = None) -> int:
        with self._connect() as connection:
            return connection.execute(*_to_psycopg(query, params)).rowcount

    def fetch_one(self, query: str, params: Params | None = None) -> Row | None:
        with self._connect() as connection:
            return connection.execute(*_to_psycopg(query, params)).fetchone()

    def fetch_all(self, query: str, params: Params | None = None) -> list[Row]:
        with self._connect() as connection:
            return connection.execute(*_to_psycopg(query, params)).fetchall()

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection[Row]]:
        try:
            # Le bloc `with` fait commit si tout va bien, rollback sinon, puis
            # ferme la connexion.
            with psycopg.connect(self._url, row_factory=dict_row) as connection:
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
