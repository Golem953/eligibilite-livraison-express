"""Point d'entrée de l'API (ENTRYPOINT du Dockerfile)."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("infrastructure.adapter.http.app:app", host="0.0.0.0", port=8000)
