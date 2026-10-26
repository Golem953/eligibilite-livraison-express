# Politique de sécurité

## Versions maintenues

Seule la dernière version de la branche `main` reçoit des correctifs de sécurité.

| Version | Maintenue |
|---|---|
| `main` (0.1.x) | Oui |
| Autres branches et versions antérieures | Non |

## Signaler une vulnérabilité

**Ne publiez pas de vulnérabilité dans une issue, une pull request ou une discussion publique.**

Utilisez le signalement privé de GitHub :

1. Ouvrez l'onglet **Security** du dépôt, puis **Report a vulnerability** ([lien direct](https://github.com/Golem953/eligibilite-livraison-express/security/advisories/new)).
2. Décrivez :
   - la partie concernée (API, entraînement, chargement du modèle, configuration…) ;
   - les étapes pour reproduire le problème ;
   - l'impact possible ;
   - si possible, une piste de correction.

### Ce qui se passe ensuite

| Étape | Délai indicatif |
|---|---|
| Accusé de réception | 5 jours ouvrés |
| Première évaluation (confirmé ou non, gravité) | 10 jours ouvrés |
| Correctif ou mesure de contournement | selon la gravité |

Le correctif est développé sur une branche `hotfix/<version>` créée depuis `main`, puis fusionné dans `main` et `dev`, et publié sous un nouveau numéro de version (voir [CONTRIBUTING.md](CONTRIBUTING.md)). Une fois le correctif publié, la vulnérabilité peut être rendue publique, avec mention de la personne qui l'a signalée si elle le souhaite.

## Limites connues

Le projet est une version pédagogique, pas encore prévue pour être exposée sur Internet. Les points suivants sont connus et suivis dans [ADR.md](ADR.md). Inutile de les signaler :

- **L'API n'a pas d'authentification** (ADR-0007). Elle écoute uniquement sur `127.0.0.1` par défaut : ne la lancez pas avec `--host 0.0.0.0` sur un réseau partagé.
- **La validation des commandes est partielle** : les types sont vérifiés, mais pas les bornes ni les valeurs des catégories (ADR-0007).
- **Le modèle est chargé avec `joblib`**, qui repose sur pickle : charger un fichier `.joblib` exécute le code qu'il contient. Ne chargez jamais un modèle d'origine inconnue, et protégez en écriture le dossier de `MODEL_PATH` (ADR-0008).
- **MLflow tourne en local, sans authentification** (ADR-0008).

Un signalement qui montre qu'une de ces limites a un impact plus grave que prévu reste le bienvenu.

## Bonnes pratiques pour les contributeurs

- Aucun secret (mot de passe, clé d'API, jeton) dans le code, les commits ou les issues. Les secrets vont dans `.env`, exclu de git.
- Si un secret a été poussé par erreur, considérez-le comme compromis : changez-le immédiatement, puis prévenez les mainteneurs par le signalement privé ci-dessus.
- Les dépendances sont figées dans `requirements.txt`. Une mise à jour de sécurité d'une dépendance se fait dans une pull request dédiée.
