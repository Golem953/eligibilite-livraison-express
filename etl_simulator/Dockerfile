# ETL simulé (ADR-0010) : génère des commandes labellisées en dev et en test (MODE=generate),
# ou labellise celles de l'ERP simulé (MODE=label). Il joue un système externe : cette
# image ne fait pas partie de docker-compose.prod.yml.
FROM python:3.13.18-slim@sha256:76baad6037690d6e8c4397fbcaef17bca6f19eecef822b708fe8fa3417d30bb5

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && pip uninstall --yes --root-user-action=ignore pip \
    && useradd --uid 1000 --no-create-home --shell /usr/sbin/nologin etluser

COPY etl_simulator.py .
USER etluser

CMD ["python", "etl_simulator.py"]
