FROM python:3.14.8-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # config/ à la racine, domain/ et infrastructure/ dans src/.
    PYTHONPATH=/app:/app/src

# Dépendances installées avant le code : cette couche reste en cache tant que
# requirements.txt ne change pas.
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

# git n'est pas installé : MLflow (GitPython) n'affiche pas d'avertissement à chaque run.
ENV GIT_PYTHON_REFRESH=quiet

# L'application tourne avec un utilisateur sans droits d'administration.
RUN useradd --create-home user
WORKDIR /app
# Dossier de la base SQLite (dev), créé au nom de l'utilisateur.
RUN mkdir data && chown user:user data
USER user

COPY config config
COPY src src
# Outils disponibles aussi dans le conteneur : docker compose exec api python tools/train.py
COPY tools tools

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "infrastructure.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
