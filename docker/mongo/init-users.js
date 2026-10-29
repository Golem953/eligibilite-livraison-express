// Comptes MongoDB de l'environnement de test, un par usage (ADR-0008, ADR-0009).
// Exécuté une seule fois, à la création du volume, par l'image officielle mongo.
//
//   training_reader : lecture seule, utilisé par l'entraînement ;
//   etl_writer      : lecture et écriture, utilisé par l'ETL simulé.
//
// Le compte administrateur (MONGO_INITDB_ROOT_USERNAME) ne sert qu'à l'administration.

const database = db.getSiblingDB("livraison_express");

database.createUser({
  user: "training_reader",
  pwd: process.env.MONGO_TRAINING_PASSWORD,
  roles: [{ role: "read", db: "livraison_express" }],
});

database.createUser({
  user: "etl_writer",
  pwd: process.env.MONGO_ETL_PASSWORD,
  roles: [{ role: "readWrite", db: "livraison_express" }],
});
