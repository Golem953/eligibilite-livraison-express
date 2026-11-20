## Ce qui change

<!-- En quelques lignes : le comportement avant, le comportement après. -->

## Pourquoi

<!-- Le besoin ou le problème. Liez l'issue (Closes #12) ou l'ADR concerné (ADR-0005). -->

## Comment le vérifier

<!-- Les commandes à lancer et le résultat attendu. -->

## Vérifications

- [ ] La branche cible est la bonne : `dev` pour une fonctionnalité, `main` uniquement depuis `release/x.y.z` ou `hotfix/x.y.z` (voir CONTRIBUTING.md)
- [ ] `ruff check .` et `pytest` passent
- [ ] Les tests couvrent le nouveau comportement
- [ ] La documentation touchée est à jour : README, `.env.example` et les `.env.*.example`, ADR
- [ ] Aucun secret, aucun artefact de modèle (`*.joblib`, `mlruns/`) dans la PR
- [ ] Une décision d'architecture nouvelle ou remise en cause s'accompagne d'un ADR
