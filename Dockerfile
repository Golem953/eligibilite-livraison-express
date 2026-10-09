FROM python:3.14.8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances installées en root, avant le code : cette couche reste en cache
# tant que requirements.txt ne change pas.
COPY requirements.txt .
RUN pip install -r requirements.txt && rm requirements.txt

# L'application tourne avec un utilisateur sans droits d'administration.
RUN useradd -ms /bin/bash user
USER user
WORKDIR /home/user
# Dossier de la base SQLite, créé au nom de l'utilisateur pour que le volume
# monté dessus lui appartienne.
RUN mkdir data

COPY src .
# Migrations SQL appliquées par l'API au démarrage (create_schema).
COPY db/migrations db/migrations

EXPOSE 8000

ENTRYPOINT ["python", "main.py"]
