# Quick wins – Robustesse & Maintenabilité (plan-action-audit-2025)

Voici une sélection de quick wins à forte valeur ajoutée, réalisables sans refonte majeure :

---

## 1. Optimiser SQLite (WAL, index, accès concurrents) ✅ TERMINÉ
- Vérification que le mode WAL est bien activé au démarrage
- Ajout d'index critiques (patients, dossiers, venues, mouvements, messages)
- Optimisations PRAGMA avancées (cache, mmap, synchronous)
- Documentation de la configuration recommandée

## 2. Centraliser la configuration ✅ TERMINÉ
- Création d'un fichier unique `config/settings.py` avec Pydantic
- Validation de configuration au démarrage avec avertissements
- Migration des accès aux variables d'environnement vers la config centralisée
- Affichage propre de la configuration chargée

## 3. Améliorer la gestion des erreurs
- [ ] Ajouter un middleware global pour capturer et logger proprement toutes les exceptions
- [ ] Standardiser les messages d’erreur API (format JSON, code, message)

## 4. Nettoyer les imports inutilisés
- [ ] Passer un outil d’analyse (ex: `autoflake`, `vulture`) sur le dossier `app/`
- [ ] Supprimer les imports morts pour alléger le code et accélérer l’analyse statique

## 5. Renforcer la documentation technique
- [ ] Ajouter ou compléter un README technique sur l’architecture et la configuration
- [ ] Générer et publier la documentation OpenAPI complète

---

*Ces actions peuvent être réalisées indépendamment et apportent un gain immédiat de qualité et de maintenabilité.*
