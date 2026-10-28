# Contribuer à livraison-express-lite

Merci de votre intérêt pour le projet. Ce guide décrit comment proposer une modification.

En participant, vous vous engagez à respecter le [code de conduite](CODE_OF_CONDUCT.md).

## Avant de commencer

- **Une vulnérabilité ?** Ne la publiez pas dans une issue : suivez [SECURITY.md](SECURITY.md).
- **Un bug ou une idée ?** Ouvrez une issue qui décrit le problème, comment le reproduire et le comportement attendu.
- **Une décision d'architecture ?** Changer de stockage, ajouter un service, modifier la sécurité… Lisez d'abord [ADR.md](ADR.md). Une nouvelle décision, ou la remise en cause d'une décision existante, s'accompagne d'un ADR.

## Préparer son environnement

Suivez la section « Installation » du [README](README.md) : `requirements-dev.txt` installe aussi pytest, ruff et le MLflow complet.

**Ajouter ou mettre à jour une dépendance :**

- outil de développement (test, lint…) : ajoutez-le à `requirements-dev.txt`, avec sa version ;
- dépendance de l'application : ajoutez-la à la liste des dépendances directes en tête de `requirements.txt`, puis régénérez le fichier avec la commande indiquée au même endroit. Il est généré dans l'image de base Linux, pour que les versions figées soient exactement celles installées dans les images Docker.

## Branches (Git Flow)

Le projet suit le modèle [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/). Deux branches sont permanentes, les autres sont créées pour un besoin précis puis supprimées une fois fusionnées.

| Branche | Durée de vie | Rôle | Créée depuis | Fusionnée dans |
|---|---|---|---|---|
| `main` | permanente | Code en production. Chaque commit de `main` est une version publiée, marquée par un tag | — | — |
| `dev` | permanente | Intégration : contient les fonctionnalités terminées de la prochaine version | `main` | — |
| `feat/<sujet>` | temporaire | Une fonctionnalité ou un chantier | `dev` | `dev` |
| `release/<version>` | temporaire | Préparation d'une version : numéro de version, documentation, derniers correctifs. Aucune nouvelle fonctionnalité | `dev` | `main` **et** `dev` |
| `hotfix/<version>` | temporaire | Correctif urgent sur la production | `main` | `main` **et** `dev` |

Règles :

- **On ne pousse jamais directement sur `main` ni sur `dev`** : tout passe par une pull request.
- **Les branches temporaires se nomment toujours avec un préfixe et un `/`** : `feat/repository-postgresql`, `release/0.2.0`, `hotfix/0.1.1`. Ne créez jamais de branche nommée `feat`, `release` ou `hotfix` tout court : Git refuserait ensuite toute branche `hotfix/…`.
- **Les noms sont en minuscules**, avec des tirets ou des underscores.

### Développer une fonctionnalité

```powershell
git switch dev
git pull
git switch -c feat/mon-sujet
# ... commits ...
git push -u origin feat/mon-sujet     # puis pull request vers dev
```

### Publier une version

```powershell
git switch dev
git pull
git switch -c release/0.2.0
# version = "0.2.0" dans pyproject.toml, documentation, derniers correctifs
git push -u origin release/0.2.0      # puis pull request vers main
```

Une fois la pull request fusionnée dans `main`, la CD (voir « CI/CD » ci-dessous) publie l'image `0.2.0` et pose le tag Git `v0.2.0`. Il n'y a rien à faire à la main.

Fusionnez ensuite `release/0.2.0` dans `dev` (pull request), pour que les derniers correctifs y soient aussi, puis supprimez la branche.

### Corriger la production en urgence

```powershell
git switch main
git pull
git switch -c hotfix/0.1.1
# correctif + version dans pyproject.toml
git push -u origin hotfix/0.1.1       # puis pull request vers main
```

Après la fusion dans `main`, la CD publie l'image et pose le tag `v0.1.1`, comme pour une version. Fusionnez ensuite `hotfix/0.1.1` dans `dev`, puis supprimez la branche.

### Numéros de version

Les versions suivent le [versionnage sémantique](https://semver.org/lang/fr/) `MAJEUR.MINEUR.CORRECTIF` :

- **correctif** (`0.1.0` → `0.1.1`) : correction sans changement de comportement attendu, typiquement un hotfix ;
- **mineur** (`0.1.1` → `0.2.0`) : nouvelle fonctionnalité compatible avec l'existant ;
- **majeur** (`0.2.0` → `1.0.0`) : changement incompatible, par exemple une modification du contrat de l'API ou des variables du modèle.

La version est dans `pyproject.toml` (`version`), et le tag Git correspondant est `v<version>`. Elle doit être augmentée dans la branche `release/` ou `hotfix/` : si le tag existe déjà, la CD refuse de publier.

## CI/CD

Deux workflows GitHub Actions, dans `.github/workflows/` :

| Workflow | Déclenchement | Étapes |
|---|---|---|
| `ci.yml` (CI) | push sur `dev`, `release/*` et `hotfix/*` ; pull request vers `dev` ou `main` | Ruff, pytest, build de l'image `prod` (sans publication) |
| `cd.yml` (CD) | push sur `main`, c'est-à-dire la fusion d'une `release/` ou d'un `hotfix/` | La CI complète, puis publication de l'image sur GitHub Container Registry et tag Git `v<version>` |

La CD ne déploie rien : elle publie seulement l'image `ghcr.io/golem953/eligibilite-livraison-express`, avec quatre étiquettes :

| Étiquette | Exemple | Usage |
|---|---|---|
| `<version>` | `0.1.1` | Version exacte, à utiliser pour déployer |
| `<majeur>.<mineur>` | `0.1` | Dernier correctif de la version mineure |
| `latest` | `latest` | Dernière version publiée |
| `sha-<commit>` | `sha-3f2a9c1` | Commit exact qui a produit l'image |

```powershell
docker pull ghcr.io/golem953/eligibilite-livraison-express:0.1.1
```

Au premier envoi, le paquet est privé sur GitHub : pour le rendre public, *Packages → eligibilite-livraison-express → Package settings → Change visibility*.

## Images Docker

Le `Dockerfile` contient une étape par environnement, et chaque branche Git Flow a la sienne. Pour travailler et valider une release, les images se construisent avec Docker Compose ; l'image de production, elle, est publiée par la CD (voir « CI/CD »).

Chaque environnement a son fichier de configuration `.env.<environnement>`, passé à Compose avec `--env-file`. La variable `APP_ENV` de ce fichier choisit l'étape du `Dockerfile` et le nom de l'image ; sans elle, c'est `dev`.

| Moment | Branche | Fichier | `APP_ENV` | Image | Contenu |
|---|---|---|---|---|---|
| Développement sur son poste | `feat/*`, `dev` | `.env.dev` | `dev` | `livraison-express:dev` | Tout le dépôt, avec pytest et ruff |
| Pull request de `dev` vers une release, ou correctif urgent | `release/<version>`, `hotfix/<version>` | `.env.test` | `test` | `livraison-express:test` | Identique à la prod : sert à valider la release |
| Fusion dans `main` | `main` | `.env.prod` | `prod` | `livraison-express:prod` | Dépendances d'exécution et code uniquement |

### En développement

```powershell
docker compose --env-file .env.dev up -d --build
docker compose --env-file .env.dev run --rm train
docker compose --env-file .env.dev restart api
```

### Pour valider une release

Sur la branche `release/<version>` (ou `hotfix/<version>`), avec un fichier `.env.test` qui contient `APP_ENV=test` :

```powershell
docker compose --env-file .env.test up -d --build
docker compose --env-file .env.test run --rm train
docker compose --env-file .env.test restart api
```

La release n'est fusionnée dans `main` que si l'application fonctionne avec cette image.

### Pour la production

Sur `main`, après la fusion et le tag, avec un fichier `.env.prod` qui contient `APP_ENV=prod` :

```powershell
docker compose --env-file .env.prod up -d --build
```

Les étapes `test` et `prod` étant identiques, l'image validée en release est exactement celle qui part en production.

### Règles pour les fichiers `.env.<environnement>`

- Créez `.env.test` et `.env.prod` sur le modèle de `.env.dev`, sur la machine qui en a besoin.
- Ne laissez aucune clé vide : l'application refuse une valeur vide pour un nombre.
- Ces fichiers sont lus par Compose, pas par l'application. Ne mettez pas `APP_ENV` dans le fichier `.env` lu par l'application : elle refuse les clés qu'elle ne connaît pas.
- Les fichiers `.env.*` sont exclus de git (sauf `.env.example`), car ceux de test et de prod contiendront des secrets.

## Commits

Les messages suivent la convention [Conventional Commits](https://www.conventionalcommits.org/fr/) :

```text
<type>: <résumé à l'impératif, en minuscules>

<corps facultatif : pourquoi ce changement, ce qu'il implique>
```

| Type | Usage |
|---|---|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement (README, ADR…) |
| `refactor` | Changement de code sans changement de comportement |
| `test` | Ajout ou modification de tests |
| `chore` | Dépendances, configuration, outillage |

Exemple : `fix: refuse une commande sans order_id dans InMemoryOrderRepository`.

Un commit = un changement cohérent. Ne mélangez pas une correction et un reformatage de fichier.

## Règles de code

- **Python 3.13**, style vérifié par Ruff (`ruff check .` doit passer). La configuration est dans `pyproject.toml` : lignes de 100 caractères maximum, imports triés.
- **Respecter les couches** décrites dans [ARCHITECTURE-livraison-express-lite.md](ARCHITECTURE-livraison-express-lite.md) :
  - `domain/` ne dépend ni de FastAPI, ni de pandas, ni de MLflow ;
  - les classes concrètes (repositories, modèle) ne sont choisies que dans `core/core.py` ;
  - l'API n'importe pas le code d'entraînement.
- **Les variables du modèle sont un contrat** : toute modification passe par `FEATURE_COLUMNS` dans `core/learning/order_feature.py`, et concerne à la fois l'entraînement et la prédiction.
- **Aucun secret dans le code ni dans le dépôt.** La configuration passe par `config.py` et `.env`. Toute nouvelle variable est documentée dans `.env.example`.
- **Ne pas modifier le notebook** `notebooks/project_test_v1_final_final2.ipynb` : c'est la trace de l'exploration d'origine.
- **Ne pas versionner** les artefacts du modèle (`*.joblib`, `notebooks/artifacts/`) ni les runs MLflow (`mlruns/`).

## Tests

Les tests [pytest](https://docs.pytest.org/) sont dans `tests/`. Ils importent le package sous le nom `app`, comme dans les images Docker (`pythonpath = ["src"]` dans `pyproject.toml`). Toute nouvelle fonctionnalité ou correction doit être accompagnée de tests.

Avant d'ouvrir une pull request, lancez ce que la CI vérifiera :

```powershell
ruff check .
pytest
```

## Pull requests

1. Partez d'une branche à jour, selon le type de travail (voir « Branches » ci-dessus) : `dev` pour une fonctionnalité ou une version, `main` pour un correctif urgent.
2. Gardez la pull request petite et centrée sur un seul sujet.
3. Décrivez **ce qui change**, **pourquoi**, et **comment le vérifier**. Liez l'issue ou l'ADR concerné.
4. Mettez à jour la documentation touchée : README, `.env.example`, ADR.
5. Au moins une relecture approuvée est nécessaire avant la fusion.
6. Supprimez la branche une fois fusionnée.
