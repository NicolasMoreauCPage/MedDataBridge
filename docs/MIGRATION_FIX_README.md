# MedDataBridge - Correction Migration IHE PAM
# Fichier à remplacer en production

## Problème
Erreur `NameError: name 'now' is not defined` lors de l'exécution de la migration Alembic.

## Solution
Remplacer le fichier `alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py` en production
par la version corrigée ci-dessous.

## Instructions
1. Sauvegarder l'ancien fichier :
   cp alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py alembic/versions/bdebea0e6af4_add_ihe_pam_scenarios_data.py.backup

2. Remplacer par le contenu corrigé (fourni ci-dessous)

3. Réexécuter la migration :
   alembic upgrade head

---

# CONTENU DU FICHIER CORRIGÉ
# (À copier-coller dans le fichier de migration en production)