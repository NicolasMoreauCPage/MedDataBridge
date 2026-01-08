# Plan d’action priorisé – MedData Bridge (branche : plan-action-audit-2025)

Ce plan d’action est issu de la synthèse des audits et sera mis à jour au fil de l’avancement sur cette branche dédiée.

---


- [x] Améliorer la configuration et la robustesse de SQLite (optimisation WAL, index, gestion des accès concurrents)
- [ ] Optimiser la gestion des sessions DB et le pooling
- [ ] Mettre en place un cache Redis pour les données fréquentes
- [ ] Refactorer la logique métier hors des templates

## Phase 2 – Maintenabilité
- [ ] Regrouper les modèles par domaine métier
- [ ] Résoudre les imports circulaires
- [ ] Standardiser la langue du code (anglais recommandé) et renforcer la documentation
- [x] Centraliser la configuration et valider au démarrage

## Phase 3 – CI/CD et qualité
- [ ] Mettre en place une CI/CD complète (tests, déploiement, couverture)
- [ ] Ajouter du monitoring (Prometheus, logs structurés, alertes)
- [ ] Réaliser des tests de charge et de robustesse

## Phase 4 – Sécurité (optionnel, à traiter si besoin)
- [ ] Remplacer l’authentification simulée par une vraie gestion des utilisateurs (SQL, OAuth2)
- [ ] Sécuriser la gestion des secrets (vault, rotation, variables d’environnement obligatoires)
- [ ] Implémenter un rate limiting global
- [ ] Filtrer et structurer les logs (conformité RGPD/HIPAA)

---

## Suivi
- Ce fichier sera mis à jour à chaque étape franchie sur la branche `plan-action-audit-2025`.
- Les tâches sont à cocher au fur et à mesure de leur réalisation.

---

*Dernière mise à jour : 26 décembre 2025.*
