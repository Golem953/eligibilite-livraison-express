# ---------- base : ce qui est commun à tout le monde ----------
# Version exacte et empreinte figées : deux builds donnent la même image. Pour profiter
# des correctifs de sécurité, mettre à jour les deux ensemble (docker buildx imagetools
# inspect python:3.13.<x>-slim donne l'empreinte).
FROM python:3.13.18-slim@sha256:76baad6037690d6e8c4397fbcaef17bca6f19eecef822b708fe8fa3417d30bb5 AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src/app app


# ---------- dev : tout, pour travailler sur son poste ----------
FROM base AS dev

# pytest, ruff
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt

# Tout le dépôt : docs, tests (hors fichiers exclus par .dockerignore)
COPY . .

CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]


# ---------- test : environnement de validation des releases ----------
# Strictement identique à prod : une branche release/<version> y est déployée et
# vérifiée avant d'être fusionnée dans main et mise en production.
FROM base AS test

# pip ne sert plus une fois les dépendances installées, et embarque ses propres
# copies vulnérables d'urllib3 et msgpack. appuser : UID fixe (le compose s'en sert),
# sans dossier personnel ni shell de connexion.
RUN pip uninstall --yes --root-user-action=ignore pip \
    && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]


# ---------- prod : le strict minimum ----------
FROM base AS prod

# pip ne sert plus une fois les dépendances installées, et embarque ses propres
# copies vulnérables d'urllib3 et msgpack. appuser : UID fixe (le compose s'en sert),
# sans dossier personnel ni shell de connexion.
RUN pip uninstall --yes --root-user-action=ignore pip \
    && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]
