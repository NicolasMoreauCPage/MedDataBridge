# Comparaison des audits du dossier `app/` – MedData Bridge

Ce document synthétise les convergences et divergences entre :
- **docs/AUDIT_APP.md** (audit détaillé, structuré, priorisé)
- **docs/ANALYSE_CODE_APP.md** (analyse indépendante, centrée code)

---

## 1. Points de convergence

| Thème                        | Présent dans les deux | Détail |
|------------------------------|:---------------------:|--------|
| Modularité                   | ✅                    | Architecture claire, séparation des responsabilités |
| Multiplicité des modèles     | ✅                    | Trop de fichiers modèles, navigation difficile |
| Couplage fort/Imports        | ✅                    | Problèmes d’imports circulaires, dépendances entre modules |
| SQLite en production         | ✅                    | Limite la robustesse et la scalabilité |
| Authentification simpliste   | ✅                    | Base utilisateurs simulée, à sécuriser |
| Absence de rate limiting     | ✅                    | Aucun contrôle de débit sur les endpoints |
| Documentation perfectible    | ✅                    | Mélange de langues, doc incomplète |
| Gestion d’erreurs à renforcer| ✅                    | Exceptions/logs à structurer |
| Absence de cache             | ✅                    | Pas de cache Redis ou HTTP |

---

## 2. Points de divergence

| Thème/Angle                  | Audit structuré (A) | Analyse code (C) | Commentaire |
|------------------------------|:-------------------:|:----------------:|-------------|
| Priorisation des actions     | ✅                  | ❌               | L’audit propose des phases, l’analyse code liste sans prioriser |
| Sécurité des logs            | ✅                  | ❌               | L’audit insiste sur la conformité RGPD/HIPAA, l’analyse code non |
| Cycle de vie asynchrone      | ❌                  | ✅               | L’analyse code valorise la gestion asynchrone (démarrage/arrêt) |
| Base de tests                | ✅                  | ✅               | Les deux notent la présence de tests, seul l’audit détaille la couverture |
| CI/CD                        | ✅                  | ❌               | L’audit mentionne l’absence de pipeline CI/CD |
| Monitoring                   | ✅                  | ❌               | L’audit propose Prometheus/ELK, l’analyse code ne l’aborde pas |
| Suggestions d’archi détaillées| ✅                 | ❌               | L’audit propose des regroupements précis (modules, registry, etc.) |
| Internationalisation         | ✅                  | ✅               | Les deux notent le mélange de langues |
| Exemples concrets            | ✅                  | ❌               | L’audit illustre par des extraits de code |
| Logique métier dans templates| ✅                  | ❌               | L’audit cible ce point, l’analyse code non |

---

## 3. Synthèse

- **L’audit structuré** (A) est plus exhaustif, priorise les actions, donne des exemples et cible la conformité sécurité/production.
- **L’analyse code** (C) est plus factuelle, centrée sur la structure et l’organisation, sans priorisation ni focus sécurité/ops.

## 4. Recommandation

- Utiliser l’audit structuré comme feuille de route principale.
- Garder l’analyse code comme check-list de structure et d’organisation.
- Réaliser un suivi des actions selon la priorisation de l’audit, en vérifiant que les points de l’analyse code sont bien couverts.

---

*Comparaison réalisée le 26 décembre 2025.*
