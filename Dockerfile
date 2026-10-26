# ---------- base : ce qui est commun à tout le monde ----------
FROM python:3.13-slim AS base

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

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]


# ---------- prod : le strict minimum ----------
FROM base AS prod

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["python", "-m", "app", "serve", "--host", "0.0.0.0"]
