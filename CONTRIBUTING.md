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

Le projet suit un modèle dérivé de [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/). La CI/CD ne déploie sur aucun serveur : elle publie seulement l'image sur GitHub Container Registry.

| Branche | Rôle | Publie | Protégée |
|---|---|---|---|
| `feat/…`, `fix/…`, `chore/…` | travail | — | non |
| `dev` | intégration | — | oui (ruleset) |
| `release/x.y.z` | `dev` figé à l'instant du bouton | — | non (supprimée après la publication) |
| `hotfix/x.y.z` | correctif urgent, parti de `main` | — | non (supprimée après la publication) |
| `main` | production | image `x.y.z` sur ghcr.io, tag `vx.y.z` et release GitHub, à chaque merge | oui (ruleset) |

Un seul sens : `dev` → `release/x.y.z` → `main`. Jamais `main` → `dev`, sauf le report d'un hotfix.

```text
feat/xxx ──PR──▶ dev
                  │  ▲
                  │  └── PR fix/report-hotfix-x.y.z (ouverte toute seule après la publication)
      bouton « Release » (patch / minor / major)
                  ▼
           release/x.y.z ──PR──▶ main ──▶ image x.y.z sur ghcr.io
           (= dev, aucun commit)  ▲       puis tag vx.y.z + release GitHub
                                  │
           hotfix/x.y.z ───PR─────┘  (correctif urgent, parti de main)
```

### Le cycle

**Travail.** Une branche depuis `dev`, une PR vers `dev`, merge.

```powershell
git switch dev
git pull
git switch -c feat/mon-sujet
# ... commits ...
git push -u origin feat/mon-sujet     # puis pull request vers dev
```

**Release.** Onglet *Actions* → *Release* → *Run workflow*. Laissez *Use workflow from* sur `main` : ce menu dit seulement où GitHub lit le workflow. Choisissez le niveau :

- `patch` : correctifs ;
- `minor` : nouveautés compatibles ;
- `major` : rupture (contrat de l'API, variables du modèle…).

Le workflow (`release.yml`) calcule la version à partir du dernier tag `vx.y.z`, crée `release/x.y.z` pile sur la tête de `dev`, sans aucun commit, et ouvre la PR vers `main` avec la liste des PR apportées. `main` ne bouge pas.

**Publication.** Mergez la PR `release/x.y.z` → `main` avec **Create a merge commit**. La CD publie l'image `x.y.z` sur ghcr.io, crée le tag `vx.y.z` et la release GitHub, puis supprime la branche de release. C'est fini : rien ne revient dans `dev`, car la release n'y a rien ajouté.

### Hotfix (correctif urgent)

Pour corriger la production sans embarquer ce qui attend dans `dev`.

1. **Version** : le dernier tag `vX.Y.Z`, correctif + 1.

   ```bash
   git ls-remote --tags --refs origin 'v*' | sed 's#.*refs/tags/##' | sort -V | tail -1
   ```

2. **Branche depuis `main`** (l'état de la production), au format exact `hotfix/x.y.z`. Un nom libre (`hotfix/correctif`) est refusé par le contrôle d'origine, car la CD ne saurait pas en lire la version.

   ```powershell
   git fetch origin
   git switch -c hotfix/0.2.1 origin/main
   ```

3. **Correctif, commit, push**, puis PR `hotfix/x.y.z` → `main` : mêmes contrôles qu'une release, merge en **Create a merge commit**. Image `x.y.z`, tag `vx.y.z`, release GitHub, branche supprimée : comme une release.

4. **Report dans `dev` : automatique.** Après la publication, la CD crée `fix/report-hotfix-x.y.z` sur le commit publié (= tag `vx.y.z`) et ouvre la PR vers `dev`, où la CI se lance. Il reste à la merger en **Create a merge commit**. En cas de conflit :

   ```powershell
   git fetch origin
   git switch fix/report-hotfix-0.2.1
   git merge origin/dev
   # résoudre, puis :
   git commit
   git push
   ```

   C'est la seule entrée de `main` dans `dev`, et elle passe par une PR. Pas de cherry-pick, ni de squash de cette PR : `dev` aurait la même modification sans l'historique du hotfix, et la release suivante entrerait en conflit sans endroit autorisé pour le résoudre (aucun commit sur `release/*`).

**Ordre imposé : hotfix → report → release.** Le bouton *Release* refuse de partir tant qu'une PR de hotfix vers `main` ou une PR de report vers `dev` est ouverte.

### Règles

- **Aucun push direct sur `dev` ou `main`** : tout passe par une PR.
- **Aucun fichier de version.** La version vient des tags : le bouton prend le dernier `vx.y.z` et calcule la suivante. Sur `main`, la CD lit la version dans le nom de la branche de la PR mergée (`release/x.y.z` ou `hotfix/x.y.z`). Le champ `version` de `pyproject.toml` n'est pas utilisé pour les releases.
- **Toute publication passe par une release ou un hotfix.** Un commit de `main` qui ne vient ni d'une PR `release/x.y.z` ni d'une PR `hotfix/x.y.z` est refusé par la CD, et une version déjà taguée ne se republie jamais.
- **`main` n'accepte que les PR depuis `release/x.y.z` et `hotfix/x.y.z`.** Le contrôle obligatoire « Origine de la PR vers main » (`origine.yml`) échoue pour toute autre branche source, pour une branche de fork du même nom et pour une version déjà taguée. Le format est exact : `release/1.2` ou `hotfix/correctif` sont refusés dès la PR. La PR peut s'ouvrir, mais le bouton *Merge* reste bloqué. GitHub ne sait pas filtrer nativement la branche source d'une PR : c'est ce contrôle, rendu obligatoire par le ruleset de `main`, qui l'impose.
- **Ne jamais committer sur une branche `release/*`.** Elle doit rester égale à `dev`. Un correctif se fait dans `dev` (PR), puis par une nouvelle release. Pour remplacer une release pas encore mergée : fermez sa PR, supprimez la branche et relancez le bouton.
- **Merger les PR de release, de hotfix et de report en « Create a merge commit »**, jamais en squash ni en rebase : ces deux modes réécrivent les commits, `main` contiendrait des commits que `dev` n'a pas, et les releases suivantes finiraient en conflit.
- **Une seule release à la fois** : le bouton refuse s'il y a déjà une PR de release ou de hotfix ouverte.
- **Noms de branches** en minuscules, toujours avec un préfixe et un `/` (`feat/repository-postgresql`). Ne créez jamais de branche nommée `feat`, `release` ou `hotfix` tout court : Git refuserait ensuite toute branche `hotfix/…`.

### Mise en place (une seule fois, par un administrateur du dépôt)

- **Jeton du bouton Release** : un *fine-grained personal access token* limité à ce dépôt, avec les permissions *Contents* et *Pull requests* en lecture/écriture, enregistré dans le secret `RELEASE_TOKEN` (*Settings → Secrets and variables → Actions*). Une branche ou une PR créée avec le `GITHUB_TOKEN` ne déclenche aucun workflow : sans ce jeton, la CI et le contrôle d'origine ne tourneraient pas sur la PR de release ni sur la PR de report.
- **Rulesets** (*Settings → Rules → Rulesets*) :
  - `dev` et `main` : pull request obligatoire, pas de push direct ni de suppression ;
  - `main` : contrôles obligatoires « Origine de la PR vers main », « Lint (Ruff) », « Tests (pytest) » et « Build de l'image prod », et méthode de merge autorisée : *merge* uniquement.
- **Première release** : GitHub n'affiche le bouton qu'une fois `release.yml` présent sur `main`. La première se fait donc à la main : `release/x.y.z` créée sur la tête de `dev`, PR vers `main`, merge. Elle porte une version strictement supérieure au dernier tag (ici `v0.2.0`, donc `release/0.3.0`).
- **Première PR ouverte par le jeton** : si GitHub met ses contrôles en attente (« Action required »), cliquez une fois sur *Approve and run*.

## CI/CD

Quatre workflows GitHub Actions, dans `.github/workflows/` :

| Workflow | Déclenchement | Étapes |
|---|---|---|
| `ci.yml` (CI) | push sur `dev`, `release/*` et `hotfix/*` ; pull request vers `dev` ou `main` | Ruff, pytest. Build de l'image `prod` (sans publication) **uniquement sur `release/*` et `hotfix/*`** : aucune image n'est construite avant la release |
| `origine.yml` | pull request vers `main` | Refuse toute branche source autre que `release/x.y.z` ou `hotfix/x.y.z`, ou une version déjà taguée |
| `release.yml` (bouton) | *Actions → Release → Run workflow* | Calcule la version depuis le dernier tag, crée `release/x.y.z` sur `dev` et ouvre la PR vers `main` |
| `cd.yml` (CD) | push sur `main`, c'est-à-dire le merge d'une `release/` ou d'un `hotfix/` | Version lue dans le nom de la branche, CI complète, publication de l'image sur ghcr.io, tag `vx.y.z`, release GitHub, suppression de la branche ; après un hotfix, PR de report vers `dev` |

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

Chaque environnement a son fichier Compose et son fichier de variables `.env.<environnement>`, passé à Compose avec `--env-file`.

| Moment | Branche | Compose | Variables | Image | Base MongoDB (ADR-0009) |
|---|---|---|---|---|---|
| Développement sur son poste | `feat/*`, `dev` | `docker-compose.yml` | `.env.dev` | `livraison-express:dev`, construite : tout le dépôt, avec pytest et ruff | Aucune par défaut (`memory://`) ; MongoDB et ETL simulés avec le profil `etl` |
| Pull request de `dev` vers une release, ou correctif urgent | `release/<version>`, `hotfix/<version>` | `docker-compose.test.yml` | `.env.test` | `livraison-express:test`, construite : identique à la prod | MongoDB de test, avec authentification, alimenté par l'ETL simulé |
| Fusion dans `main` | `main` | `docker-compose.prod.yml` | `.env.prod` | `ghcr.io/golem953/eligibilite-livraison-express:<version>`, publiée par la CD | MongoDB de l'ERP, service externe joint par son adresse, lu en lecture seule |

### En développement

```powershell
docker compose --env-file .env.dev up -d --build
docker compose --env-file .env.dev run --rm train
docker compose --env-file .env.dev restart api
```

### Pour valider une release

Sur la branche `release/<version>` (ou `hotfix/<version>`), avec un fichier `.env.test` copié depuis `.env.test.example` et ses mots de passe remplis :

```powershell
docker compose -f docker-compose.test.yml --env-file .env.test up -d --build
docker compose -f docker-compose.test.yml --env-file .env.test run --rm train
docker compose -f docker-compose.test.yml --env-file .env.test restart api
```

L'ETL simulé alimente le MongoDB de test au format de l'ERP. L'entraînement le lit avec le compte `training_reader`, en lecture seule, comme en prod. Les comptes sont créés par `docker/mongo/init-users.js` à la création du volume. La release n'est fusionnée dans `main` que si l'application fonctionne avec cette image.

### Pour la production

Sur `main`, après la fusion et le tag, avec un fichier `.env.prod` copié depuis `.env.prod.example`. Rien n'est construit : `APP_VERSION` choisit l'image publiée par la CD.

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm train
docker compose -f docker-compose.prod.yml --env-file .env.prod restart api
```

Le MongoDB de l'ERP est un service externe, sur une autre machine : `train` le joint par l'adresse de `TRAINING_SOURCE_URL`, sans réseau Docker partagé. L'API ne s'y connecte jamais.

Faute de serveur, l'ERP est simulé par le dossier `erp_prod_test`, **hors de ce dépôt**, à côté du projet. Il se lance dans ses propres conteneurs et publie MongoDB sur un port de sa machine. Le port 27117 évite un éventuel MongoDB déjà installé sur le poste (service Windows sur 27017) :

```powershell
cd ..\erp_prod_test
$env:MONGO_PORT = "27117"; docker compose -f docker-compose.erp.yml up -d --build
```

Sur le même poste, `TRAINING_SOURCE_URL=mongodb://host.docker.internal:27117/livraison_express`. Sur un autre poste, remplacer `host.docker.internal` par l'adresse IP de la machine de l'ERP.

Les étapes `test` et `prod` étant identiques, l'image validée en release est exactement celle qui part en production.

### Réentraînement automatique (Airflow)

Sur la machine de prod, à côté de `docker-compose.prod.yml`, avec un fichier `.env.airflow` copié depuis `.env.airflow.example` et ses secrets remplis :

```powershell
docker compose -f docker-compose.airflow.yml --env-file .env.airflow up -d --build
```

Le DAG `retrain_express_model` (`airflow/dags/`) tourne chaque nuit à 2 h. Il ne réentraîne que si au moins `RETRAIN_MIN_NEW_ORDERS` nouvelles commandes labellisées sont arrivées dans le MongoDB de l'ERP, avec l'image de prod (`APP_VERSION`). `train` ne remplace le modèle en service que si le nouveau est meilleur sur le même jeu de test, et Airflow ne redémarre l'API que dans ce cas (ADR-0010).

- Interface : <http://127.0.0.1:8080>, compte `admin` et mot de passe `AIRFLOW_ADMIN_PASSWORD`. Depuis un poste, par tunnel SSH.
- Lancer un entraînement sans attendre la nuit : bouton *Trigger* du DAG, ou `docker compose -f docker-compose.airflow.yml --env-file .env.airflow exec airflow-scheduler airflow dags trigger retrain_express_model`.
- Forcer un entraînement sous le seuil : remettre la variable Airflow `retrain_last_labeled_orders` à `0`, puis déclencher le DAG.
- Pour une nouvelle version de l'application, mettre à jour `APP_VERSION` dans `.env.prod` **et** dans `.env.airflow`.

### Règles pour les fichiers `.env.<environnement>`

- Créez `.env.test`, `.env.prod` et `.env.airflow` à partir de leurs modèles `.env.*.example`, sur la machine qui en a besoin.
- Ne laissez aucune clé vide : l'application refuse une valeur vide pour un nombre.
- Ces fichiers sont lus par Compose, pas par l'application. Ne mettez pas `APP_ENV` dans le fichier `.env` lu par l'application : elle refuse les clés qu'elle ne connaît pas.
- Les fichiers `.env.*` sont exclus de git (sauf `.env.example` et les modèles `.env.*.example`), car ceux de test et de prod contiennent des secrets.

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
  - l'API n'importe pas le code d'entraînement ;
  - les classes reçoivent leur configuration et leurs dépendances en paramètre : seuls les points d'entrée créent `Settings`.
- **Organisation des fichiers** :
  - une classe par fichier, nommé d'après la classe (`OrderEntity` → `order_entity.py`) ;
  - les interfaces (classes abstraites `ABC`) vont dans `domain/interface/`, et leur nom se termine par `Interface` (`OrderRepositoryInterface` → `order_repository_interface.py`) ;
  - les implémentations de repositories vont dans `infrastructure/repository/`, les autres implémentations techniques dans `infrastructure/implementation/` ;
  - une interface ne déclare que les méthodes que ses utilisateurs appellent.
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

1. Partez d'une branche à jour, selon le type de travail (voir « Branches » ci-dessus) : `dev` pour une fonctionnalité, `main` pour un hotfix. Les releases ne se créent pas à la main : elles passent par le bouton *Release*.
2. Gardez la pull request petite et centrée sur un seul sujet.
3. Décrivez **ce qui change**, **pourquoi**, et **comment le vérifier**. Liez l'issue ou l'ADR concerné.
4. Mettez à jour la documentation touchée : README, `.env.example`, ADR.
5. Au moins une relecture approuvée est nécessaire avant la fusion.
6. Supprimez la branche une fois fusionnée.
