# PostgreSQL, MongoDB et simulateur ERP

Le simulateur ERP est séparé de l'application `livraison_express_lite` :
`src/erp_simulator` joue le rôle d'un système externe qui alimente les bases.

Le code est organisé par responsabilité : `config.py` lit l'environnement,
`generator.py` produit les commandes, `storage.py` contient les adaptateurs de
bases et `simulator.py` orchestre le scénario via des contrats `Protocol`.

Par défaut, PostgreSQL reçoit des commandes historiques réparties entre le
1er janvier 2015 et hier. MongoDB reçoit les mêmes commandes historiques que
PostgreSQL pour la période 2023 -> hier. Les deux bases reçoivent ensuite les
mêmes commandes courantes à partir d'aujourd'hui.
Le scénario est simulé : le premier lot live porte la date du jour de départ,
le deuxième lot porte la date du lendemain, puis le jour suivant, sans attendre
le calendrier réel. Les dates futures sont donc volontaires dans ce jeu de test.

Toutes les commandes utilisent le même identifiant séquentiel dans les deux bases,
par exemple `ERP-00011001`. L'identifiant ne contient pas la date et reste unique
entre l'ancien historique, l'historique partagé et le flux live.

L'historique reproduit aussi les migrations : `weekend` vaut `NULL` avant le
1er juillet 2015, et `preparation_time_min` vaut `NULL` avant le 1er juillet
2017. Les commandes à partir d'aujourd'hui possèdent toutes les colonnes
renseignées.

Les logs indiquent les connexions, le lot en cours, le nombre de lignes PostgreSQL
effectivement insérées et le résultat de l'upsert MongoDB. Pour les suivre :

```bash
docker compose -f docker-compose.erp.yml logs -f erp-simulator
```

Le niveau de log est configurable avec `LOG_LEVEL=DEBUG`, `INFO`, `WARNING` ou
`ERROR`.

Ce dossier propose deux implémentations du contrat `OrderRepository` :

- `infrastructure/implementation/postgres_order_repository.py` avec `PostgresOrderRepository` ;
- `infrastructure/implementation/mongo_order_repository.py` avec `MongoOrderRepository`.

## Démarrer les bases et le simulateur ERP

Depuis la racine `correction` :

```bash
docker compose -f docker-compose.erp.yml up --build
```

Le simulateur publie un lot de commandes toutes les cinq secondes dans les deux
bases. Les réglages sont modifiables sans changer le code :

```bash
BATCH_SIZE=20 INTERVAL_SECONDS=10 docker compose -f docker-compose.erp.yml up --build
```

Le volume est configurable. Mettre une valeur à `0` rend le flux correspondant
illimité ; une valeur positive le borne :

```bash
POSTGRES_HISTORY_ORDERS=100 RECENT_HISTORY_ORDERS=50 LIVE_ORDER_LIMIT=200 \
  docker compose -f docker-compose.erp.yml up --build
```

`POSTGRES_HISTORY_ORDERS` contrôle l'ancien historique PostgreSQL (2015-2022),
et `RECENT_HISTORY_ORDERS` contrôle le jeu partagé 2023 -> hier écrit dans les
deux bases. Pour désactiver complètement un historique, utiliser
`POSTGRES_HISTORY_ORDERS=0` ou `RECENT_HISTORY_ORDERS=0`.

Arrêter les conteneurs sans perdre les données :

```bash
docker compose -f docker-compose.erp.yml down
```

Réinitialiser les données (action volontairement destructive) :

```bash
docker compose -f docker-compose.erp.yml down -v
```

## Utiliser les repositories depuis Python

Installer les dépendances complémentaires :

```bash
pip install -r requirements-databases.txt
```