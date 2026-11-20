# Image Airflow de l'orchestrateur (ADR-0010) : l'image officielle, plus pymongo pour
# compter les nouvelles commandes labellisées de l'ERP. Le provider Docker, qui lance
# l'image de l'application, est déjà inclus.
FROM apache/airflow:3.3.2-python3.13@sha256:e9982ad3f49a60418622e1baf80c34b0daf3fa5091a336cb5ee61f0cdd189371

# Airflow est réinstallé dans sa version exacte pour que pip ne le mette pas à jour.
RUN pip install --no-cache-dir "apache-airflow==3.3.2" "pymongo==4.15.3"
