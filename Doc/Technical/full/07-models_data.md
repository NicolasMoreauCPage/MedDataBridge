# Modèles de données (SQLModel)

Fichiers principaux
- `app/models.py`, `app/models_identifiers.py`, `app/models_endpoints.py`, `app/models_structure.py`, `app/models_workflows.py`.

Entités clés
- Patient : identité, noms, adresses, identifiants externes.
- Dossier : regroupe venues/visites et mouvements.
- Venue / Mouvement : instance d'une interaction (admission, transfert, sortie), liée à ZBE.
- MessageLog : journal de tous les messages in/out (raw, metadata, validation result).
- IdentifierNamespace / Identifier : gestion des espaces de nommage d'identifiants.

Contraintes et indexes
- Identifiants uniques par namespace ; index sur patient_id, visit_id pour recherches rapides.
- MessageLog contient horodatage, code événement, niveau validation — utile pour requêtes d'audit.

Migrations
- Alembic (répertoire `alembic/`) gère les migrations; scripts d'initialisation présents (`init_db.py`).
