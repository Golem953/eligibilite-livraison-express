import re
from dataclasses import dataclass
from pathlib import Path

# 0001_create_orders.sql → version « 0001_create_orders ». Le format est imposé
# car la version est écrite telle quelle dans la table schema_migrations.
_MIGRATION_NAME = re.compile(r"^\d{4}_[a-z0-9_]+$")


@dataclass(frozen=True)
class Migration:
    version: str
    script: str


def read_migrations(migrations_dir: Path) -> list[Migration]:
    """Migrations du dossier, dans l'ordre de leur nom (0001_…, 0002_…).

    Chacune n'est appliquée qu'une fois : le connecteur note les versions
    appliquées dans la table schema_migrations. Sur une base vide (volume ou
    fichier supprimé), elles sont donc toutes rejouées.
    """
    paths = sorted(migrations_dir.glob("*.sql"))
    if not paths:
        raise FileNotFoundError(f"Aucune migration dans {migrations_dir}.")
    migrations = []
    for path in paths:
        if not _MIGRATION_NAME.match(path.stem):
            raise ValueError(
                f"Nom de migration invalide : {path.name} (attendu : 0001_nom.sql)."
            )
        migrations.append(Migration(path.stem, path.read_text(encoding="utf-8")))
    return migrations
