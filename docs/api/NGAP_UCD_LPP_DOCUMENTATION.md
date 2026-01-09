# Documentation NGAP/UCD/LPP Management System

## Vue d'ensemble

Le système de gestion des actes NGAP (Nomenclature Générale des Actes Professionnels), UCD (Unités Commune de Dispensation) et LPP (Liste des Produits et Prestations) a été implémenté pour permettre la facturation médicale française dans MedData Bridge.

## Architecture

### Modèles de données

#### NGAPAct
- **lettre_cle**: Lettre-clé NGAP (A-Z)
- **coefficient**: Coefficient multiplicatif (positif)
- **execute_date**: Date d'exécution
- **montant**: Montant facturé
- **prestataire_id**: Référence au médecin responsable
- **valide**: Statut de validation
- **facture**: Statut de facturation

#### UCDAct
- **code_ucd**: Code UCD
- **quantite**: Quantité dispensée
- **execute_date**: Date d'exécution
- **montant**: Montant facturé

#### LPPAct
- **code_lpp**: Code LPP
- **coefficient**: Coefficient
- **execute_date**: Date d'exécution
- **montant**: Montant facturé

#### Contract
- **dossier_id**: Référence au dossier patient
- **contract_type**: Type de contrat (NGAP/UCD/LPP)
- **status**: Statut du contrat (actif/inactif)

### APIs REST

#### NGAP API (`/api/ngap/`)
- `POST /`: Créer un acte NGAP
- `GET /dossier/{dossier_id}`: Lister les actes d'un dossier
- `PUT /{act_id}`: Modifier un acte
- `DELETE /{act_id}`: Supprimer un acte
- `POST /{act_id}/validate`: Valider un acte

#### UCD API (`/api/ucd/`)
- Structure similaire à NGAP API

#### LPP API (`/api/lpp/`)
- Structure similaire à NGAP API

#### Contracts API (`/api/contracts/`)
- `POST /`: Créer un contrat
- `GET /dossier/{dossier_id}`: Contrats d'un dossier
- `PUT /{contract_id}`: Modifier un contrat
- `DELETE /{contract_id}`: Supprimer un contrat

### Interfaces Web

#### Pages NGAP
- `/ngap/dashboard`: Vue d'ensemble des actes
- `/ngap/dossier/{dossier_id}`: Actes d'un dossier spécifique
- `/ngap/create`: Formulaire de création d'acte

#### Pages UCD
- Structure similaire aux pages NGAP

#### Pages LPP
- Structure similaire aux pages NGAP

#### Pages Contrats
- `/contracts/dashboard`: Gestion des contrats
- `/contracts/create`: Création de contrat

## Validation et Règles métier

### Validation NGAP
- Lettre-clé: exactement 1 caractère alphabétique
- Coefficient: valeur positive
- Date d'exécution: obligatoire
- Dossier existant: vérification FK

### Validation UCD
- Code UCD: format spécifique
- Quantité: positive
- Date d'exécution: obligatoire

### Validation LPP
- Code LPP: format spécifique
- Coefficient: positif
- Date d'exécution: obligatoire

### Contraintes Contractuelles
- Un contrat par type et par dossier
- Statut actif/inactif
- Association dossier obligatoire

## Sécurité et Contrôles

### Autorisations
- Vérification des droits d'accès par dossier
- Validation des données utilisateur
- Logs d'audit pour modifications

### Validation des données
- Contrôles de format
- Vérifications de cohérence
- Gestion des erreurs avec messages explicites

## Intégration FHIR/HPRIM

### Export HPRIM
- Génération XML HPRIM pour facturation
- Mapping vers standards français
- Validation des exports

### Intégration FHIR
- Ressources ChargeItem pour actes
- Coverage pour contrats
- Account pour facturation

## Tests et Qualité

### Tests unitaires
- Validation des services métier
- Tests des APIs REST
- Couverture des cas d'erreur

### Tests d'intégration
- Workflows complets
- Validation des UIs
- Tests de performance

## Déploiement et Maintenance

### Migration DB
- Scripts Alembic pour évolution schéma
- Migration des données existantes
- Rollback sécurisé

### Monitoring
- Métriques de performance
- Logs d'erreur détaillés
- Alertes sur anomalies

## Utilisation

### Création d'un acte NGAP
1. Sélectionner un dossier patient
2. Remplir le formulaire avec lettre-clé, coefficient, date
3. Valider et sauvegarder
4. L'acte apparaît dans la liste du dossier

### Gestion des contrats
1. Créer un contrat lié à un dossier
2. Définir le type (NGAP/UCD/LPP)
3. Activer/désactiver selon besoins

### Facturation
1. Valider les actes
2. Générer l'export HPRIM
3. Transmettre au système de facturation

Cette implémentation fournit une base solide pour la gestion complète des actes médicaux français avec une interface moderne et des contrôles métier appropriés.