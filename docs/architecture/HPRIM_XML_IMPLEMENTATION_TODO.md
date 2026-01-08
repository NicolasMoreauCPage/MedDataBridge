# Plan de Développement HPRIM XML - Todo List Détaillé

## Vue d'Ensemble
Implémentation complète du système de cotation des actes médicaux HPRIM XML 2.4 dans MedData Bridge.

## Phase 1: Infrastructure et Modèles de Base (1-2 semaines)

### 1.1 Configuration et Dépendances
- [ ] Ajouter dépendances XML (lxml, xmlschema) dans pyproject.toml
- [ ] Configurer validation XSD dans settings
- [ ] Créer répertoire `app/services/hprim/` pour les services
- [ ] Installer schémas XSD dans `app/static/schemas/hprim/`

### 1.2 Modèles de Données Python
- [ ] Créer `app/models/hprim_models.py`:
  - [ ] `HprimMessage` (base message)
  - [ ] `HprimActeCCAM` (acte CCAM complet)
  - [ ] `HprimActeNGAP` (acte NGAP)
  - [ ] `HprimActeLPP` (acte LPP)
  - [ ] `HprimActeUCD` (acte UCD)
  - [ ] `HprimPatient` (patient light)
  - [ ] `HprimProfessionnel` (médecin avec RPPS)
  - [ ] `HprimEnteteMessage` (header)
  - [ ] `HprimAcquittement` (acknowledgment)

### 1.3 Service de Validation
- [ ] Créer `app/services/hprim/hprim_validator.py`:
  - [ ] Validation XSD complète
  - [ ] Validation formats (RPPS, FINESS, codes)
  - [ ] Validation nomenclatures
  - [ ] Gestion erreurs détaillées

### 1.4 Service XML Base
- [ ] Créer `app/services/hprim/hprim_xml.py`:
  - [ ] Générateur XML from dataclasses
  - [ ] Parseur XML to dataclasses
  - [ ] Gestion namespace HPRIM
  - [ ] Gestion encodage ISO-8859-1

## Phase 2: Actes CCAM - Cœur du Système (2-3 semaines)

### 2.1 Service CCAM
- [ ] Créer `app/services/hprim/hprim_ccam.py`:
  - [ ] Validation code CCAM (format AAAA999)
  - [ ] Gestion modificateurs (A-Z, 0-9)
  - [ ] Calcul quantités et montants
  - [ ] Gestion extensions PMSI

### 2.2 API Endpoints CCAM
- [ ] Créer `app/api/hprim_ccam.py`:
  - [ ] `POST /api/hprim/actes/ccam/emission` - Émettre acte CCAM
  - [ ] `POST /api/hprim/actes/ccam/reception` - Recevoir acte CCAM
  - [ ] `GET /api/hprim/actes/ccam/{id}` - Consulter acte
  - [ ] `PUT /api/hprim/actes/ccam/{id}` - Modifier acte
  - [ ] `DELETE /api/hprim/actes/ccam/{id}` - Supprimer acte

### 2.3 Base de Données CCAM
- [ ] Créer migrations pour tables actes:
  - [ ] `hprim_actes_ccam` (code, activité, phase, exécutant, etc.)
  - [ ] `hprim_modificateurs` (liaison actes/modificateurs)
  - [ ] `hprim_montants` (valorisation)
  - [ ] Index sur codes et dates

### 2.4 Intégration Dossiers
- [ ] Lier actes CCAM aux dossiers patients
- [ ] Historique actes par dossier
- [ ] Recherche actes par patient/dossier

## Phase 3: Actes NGAP et Extensions (1-2 semaines)

### 3.1 Service NGAP
- [ ] Créer `app/services/hprim/hprim_ngap.py`:
  - [ ] Validation lettre clé (A-Z)
  - [ ] Gestion coefficients
  - [ ] Calcul dénombrement

### 3.2 API NGAP
- [ ] `POST /api/hprim/actes/ngap/emission`
- [ ] `POST /api/hprim/actes/ngap/reception`
- [ ] Endpoints consultation/modification

### 3.3 Base de Données NGAP
- [ ] Table `hprim_actes_ngap`
- [ ] Gestion coefficients et prestations

### 3.4 Actes LPP et UCD
- [ ] Service LPP (`hprim_lpp.py`)
- [ ] Service UCD (`hprim_ucd.py`)
- [ ] APIs correspondantes
- [ ] Tables base de données

## Phase 4: Système d'Acquittements (1 semaine)

### 4.1 Service Acquittements
- [ ] Créer `app/services/hprim/hprim_ack.py`:
  - [ ] Génération acquittements automatiques
  - [ ] Validation acquittements reçus
  - [ ] Gestion timeouts et retry

### 4.2 API Acquittements
- [ ] `POST /api/hprim/acquittements` - Envoyer acquittement
- [ ] `GET /api/hprim/acquittements/{msg_id}` - Status acquittement

### 4.3 Base de Données
- [ ] Table `hprim_acquittements`
- [ ] Suivi status messages
- [ ] Logs échanges

## Phase 5: Transport et Communication (1 semaine)

### 5.1 Service Transport
- [ ] Créer `app/services/hprim/hprim_transport.py`:
  - [ ] Client HTTP pour émission
  - [ ] Serveur HTTP pour réception
  - [ ] Gestion authentification
  - [ ] Chiffrement TLS

### 5.2 Configuration Transport
- [ ] URLs endpoints partenaires
- [ ] Certificats et clés
- [ ] Timeouts et retry policy

### 5.3 Monitoring
- [ ] Logs échanges détaillés
- [ ] Métriques performance
- [ ] Alertes erreurs

## Phase 6: Interface Utilisateur (2-3 semaines)

### 6.1 Interface Cotation
- [ ] Page cotation actes dans dossier patient
- [ ] Recherche actes CCAM/NGAP
- [ ] Saisie modificateurs et quantités
- [ ] Validation temps réel

### 6.2 Composants UI
- [ ] `ActeSelector` - Sélecteur d'actes
- [ ] `ModificateurEditor` - Éditeur modificateurs
- [ ] `MontantCalculator` - Calculateur automatique
- [ ] `ActeHistory` - Historique par patient

### 6.3 Intégration Frontend
- [ ] API calls vers endpoints HPRIM
- [ ] Gestion états (envoi, acquittement, erreur)
- [ ] Notifications utilisateur

## Phase 7: Tests et Validation (1-2 semaines)

### 7.1 Tests Unitaires
- [ ] Tests validation XSD
- [ ] Tests génération/parsing XML
- [ ] Tests calculs montants
- [ ] Tests formats (RPPS, etc.)

### 7.2 Tests d'Intégration
- [ ] Tests end-to-end émission/réception
- [ ] Tests avec partenaires (si possible)
- [ ] Tests charge et performance

### 7.3 Tests de Conformité
- [ ] Validation contre schémas officiels
- [ ] Tests cas limites
- [ ] Tests sécurité

## Phase 8: Déploiement et Production (1 semaine)

### 8.1 Configuration Production
- [ ] Variables environnement
- [ ] Certificats production
- [ ] URLs partenaires production

### 8.2 Monitoring Production
- [ ] Dashboards métriques
- [ ] Alertes production
- [ ] Logs centralisés

### 8.3 Documentation
- [ ] Guide utilisateur
- [ ] Documentation technique
- [ ] Procédures opérationnelles

## Risques et Dépendances

### Risques Identifiés
- **Complexité XSD**: Schémas très détaillés, validation stricte
- **Encodage**: ISO-8859-1 peut causer des problèmes
- **Partenaires**: Dépend de la disponibilité des systèmes externes
- **Réglementation**: Évolution possible des normes HPRIM

### Dépendances Externes
- Schémas XSD HPRIM (fournis)
- Spécifications détaillées (analysées)
- Accès systèmes partenaires pour tests
- Équipe métier pour validation fonctionnelle

## Métriques de Succès

### Fonctionnelles
- [ ] 100% actes CCAM gérés
- [ ] Acquittements automatiques
- [ ] Intégration dossiers complète
- [ ] Interface utilisateur fluide

### Techniques
- [ ] Validation XSD 100% conforme
- [ ] Temps réponse < 2s
- [ ] Taux erreur < 0.1%
- [ ] Tests couverture > 90%

### Métier
- [ ] Conformité HPRIM complète
- [ ] Traçabilité échanges
- [ ] Sécurité données médicales
- [ ] Performance production

---

**Durée estimée totale**: 10-14 semaines
**Équipe**: 2-3 développeurs full-stack
**Priorité**: Haute (conformité réglementaire)</content>
<parameter name="filePath">/home/nico/Travail/Fhir_MedBridgeData/MedData_Bridge/HPRIM_XML_IMPLEMENTATION_TODO.md