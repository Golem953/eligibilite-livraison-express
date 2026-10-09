"""Point d'entrée de l'API (ENTRYPOINT du Dockerfile)."""

import uvicorn

if __name__ == "__main__":
    # 0.0.0.0 : écoute sur toutes les interfaces, sinon le port publié par
    # docker compose n'atteint pas l'API depuis l'extérieur du conteneur.
    uvicorn.run("infrastructure.adapter.http.app:app", host="0.0.0.0", port=8000)
