# MedData Bridge — Documentation complète

Date: 2025-11-30

But de ce document

- Fournir une vue complète et précise du programme MedData Bridge : architecture, composants, flux de données et contrats.

- Couvrir les trois domaines fonctionnels principaux implémentés :

  - FHIR (émission / import)

  - IHE PAM (HL7v2 ADT pour identité et mouvements)

  - HL7/MFN (structure des lieux) et l'équivalent FHIR

- Expliquer comment exécuter, valider et tester (HAPI validator, pytest) et proposer des recommandations CI.

## 1. Aperçu général

MedData Bridge est une plateforme d'interopérabilité médicale orientée FastAPI. Elle fournit :

- Un serveur HTTP (FastAPI) exposant : pages UI, API REST et endpoints d'import/export FHIR.

- Une couche de persistance basée sur SQLModel/SQLite (fichier `medbridge.db` par défaut).

- Un moteur de transport MLLP pour recevoir et émettre des messages HL7v2 (services MLLP) et une pipeline d'ingestion `transport_inbound` qui implémente le profil IHE PAM (ADTs).

- Un ensemble de services pour générer et valider des messages FHIR et HL7 (MFN), et pour convertir entre ces formats et le modèle métier.

Structure principale du repo

- `app/` : code applicatif principal (routers, services, modèles, convertisseurs).

- `tests/` : tests unitaires et artefacts de test.

- `Doc/` : documentations générées et manuelles (ici nous ajoutons `PROGRAM_DOCUMENTATION.md`).

- `scripts/` et `tools/` : utilitaires et scripts de validation/maintenance (peuvent être archivés en /tmp pour sécurité).

## 2. Composants clés et fichier(s) d'entrée

- Point d'entrée application

  - `app/app.py` : compose l'instance FastAPI, middlewares et inclusion des routeurs. Fournit `create_app()` et l'app prête à être lancée.

- Base de données et sessions

  - `app/db.py` : crée le moteur SQLModel (sqlite), fournit `get_session`, `session_factory`, gestion de séquences métier et hook `before_flush` qui normalise les dates et applique des règles de compatibilité ascendante.

- Modèles métier

  - `app/models.py`, `app/models_structure.py`, `app/models_identifiers.py`, `app/models_*` : modèles SQLModel décrivant Patient, Dossier, Venue, Mouvement, Entité Juridique / Géographique, Location tree, Identifiers, etc.

- Routes FHIR

  - `app/routers/fhir_export.py` : endpoints d'export FHIR (génération de bundles pour dossier/venue/mouvement).

  - `app/routers/fhir_import.py` : endpoints d'import (bundle/patient/location/encounter) qui utilisent `FHIRBundleImporter`.

- Convertisseurs et services FHIR

  - `app/converters/fhir_import_converter.py` : convertisseurs FHIR→modèles internes (Location, Patient, Encounter) et orchestrateur `FHIRBundleImporter.import_bundle()` — gère `resource_map` pour résoudre références bundle-locales.

  - `app/services/fhir.py`, `app/services/fhir_resources.py` : générateurs de Bundle/ressources FHIR (Patient, Encounter, EpisodeOfCare), logiques de mapping (dossier→Encounter class, extensions FRCore, etc.).

- IHE PAM / HL7 inbound

  - `app/services/transport_inbound.py` : pipeline d'ingestion des messages HL7v2 (ITI-30/ITI-31 / IHE PAM). Gère parsing MSH/PID/PV1/ZBE, validation via `pam_validation`, routage via `IHEMessageRouter`, enregistrement MessageLog et création/maj des entités métier (Patient, Dossier, Venue, Mouvement).

  - `app/services/mllp_manager.py` / `app/services/mllp.py` : gestion des connexions MLLP (serveur/client) — en charge du relié MLLP vers `transport_inbound.on_message_inbound`.

- HL7 MFN for structure

  - `app/services/mfn_structure.py` : génération et traitement des messages MFN M05 pour la structure (EntiteGeographique, Pole, Service, UF, UH, Chambre, Lit). Fournit `generate_mfn_message()` et `process_mfn_message()` qui sont utilisés pour importer/exporter la structure.

- Autres utilitaires

  - `app/services/pix_pdq_manager.py`, `app/services/pix_pdq*` : gestion des requêtes de résolution d'identifiants (PIX/PDQ) si présentes.

  - `app/validators/*` : validators contextuels (PAMValidator, MFNValidator) pour aider en CLI et tests.

## 3. Fluxs et contrats (par domaine)

3.1 FHIR — émission (export)

- Entrée : un `Dossier` (ou Venue/Mouvement/Patient) du modèle interne.

- Sortie : `Bundle` FHIR (type `collection`) contenant ressources : Patient, Encounter, EpisodeOfCare (et éventuellement Location).

- Principes-métiers importants :

  - `fullUrl` stable format utilisé : `ResourceType/<id>` (ex. `Patient/pat-123`) pour faciliter la réconciliation côté import.

  - `Encounter.subject.reference` pointe vers `Patient/pat-<id>`.

  - EpisodeOfCare utilisé pour regrouper le dossier.

  - Les meta.profile FRCore sont ajoutés quand possible (e.g. Encounter meta profile `http://interop-sante.fr/fhir/StructureDefinition/fr-encounter`).

  - fichiers clés : `app/services/fhir.py`, `app/services/fhir_resources.py`.

3.2 FHIR — réception (import)

- Endpoint principal : POST `/api/fhir/import/bundle` (voir `app/routers/fhir_import.py`). Corps JSON attendu : `{ "bundle": <Bundle>, "ej_id": <int> }`.

- Orchestration : `FHIRBundleImporter.import_bundle(bundle)`

  - Passe en trois phases (Location → Patient → Encounter) — ceci permet multi-pass pour résoudre références.

  - Maintient `resource_map` : mapping bundle-local id / `ResourceType/id` → DB numeric id pour résoudre les références entre ressources du bundle.

  - Converters créent entités et enregistrent mapping : ex. `resource_map['pat-999'] = patient.id` et `resource_map['Patient/pat-999'] = patient.id`.

  - L'extracteur `_extract_id_from_reference()` gère : full URL / Type/id / bare id / leading '#' / numeric id.

  - Erreurs collectées dans `results['errors']` et retournées au client (status `partial` si erreurs non bloquantes).

3.3 IHE PAM — inbound HL7v2 (identité et mouvements)

- Point d'entrée : MLLP listener appelle `on_message_inbound()` / `transport_inbound` pipeline.

- Validation : `pam_validation.validate_pam()` applique règles PAM FR (segments PID minimal, PV1, ZBE extension parsing, typage d'événement ADT - A01/A03/A08 etc.).

- Routing : `IHEMessageRouter` mappe événements vers handlers métier (`process_admission`, `process_discharge`, `process_update`, `process_cancel`).

- Actions :

  - Création / mise à jour de `Patient` si nouvel identifiant (PID identifiers) — mapping à champs Patient (nom, DOB, sex, addresses, identifiants).

  - Création / gestion de `Dossier` et `Venue` / `Mouvement` en fonction des segments PV1/ZBE et valeur d'événement.

  - Support des annulations (A12/A13) et des updates (A08) selon règles `strict_pam_fr` par EJ.

- Persistance : via `session_factory()` / transactions ; `before_flush` normalise les dates / assigne `dossier_seq` quand absent.

3.4 HL7 MFN — Structure (locations)

- Génération : `generate_mfn_message(session, eg_identifier)` produit MFN M05 snapshot ou partial pour une entité géographique.

- Contenu : segments MFE (MAD), LOC, LCH (meta champs), LRL (relations localisations) pour EG, Pôle, Service, UF, UH, Chambre, Lit.

- Import : `process_mfn_message()` (dans même module) accepte MFN pour mettre à jour structure.

## 4. Mappages et règles importantes

- Patient identifiers

  - Plusieurs systèmes supportés : IPP (URN OID internal), NIR/INS, local patient ID.

  - Lors de l'export, on ajoute les identifiants standards (URN OID), et si disponibles le NIR/ssn.

- Dossier → Encounter mapping

  - Dossier.dossier_type → Encounter.class.code (IMP/AMB/EMER) via mapping simple.

  - Venue ↔ Encounter : venues entraînent creation d'Encounter resources; mouvements peuvent être exposés en `Encounter.location`.

- Resource mapping lors d'import

  - L'importeur FHIR maintient `resource_map` et enregistre both bare id and `Type/id` keys pour faciliter la résolution.

  - `_extract_id_from_reference` a été renforcé pour accepter formes : `Patient/pat-1`, `pat-1`, full URL, `#pat-1`, et nombres numériques.

## 5. Validation et tests

- Validation FHIR (autoritaire): HAPI FHIR CLI (jar) + IG pack `hl7.fhir.fr.core-package.tgz`.

  - Commande locale (exemple) :

  ```bash
  java -jar .tools/hapi-validator/hapi-fhir-cli-6.1.0.jar validate -n /tmp/bundle.json --igpack .tools/igpacks/hl7.fhir.fr.core-package.tgz -v r4 -r
  ```

- Tests unitaires

  - `pytest` exécute l'ensemble des tests. La suite couvre exports, imports, mappers et generateurs MFN.

  - Exemples de tests ajoutés : `tests/test_fhir_import.py` (extractor + roundtrip bundle import).

## 6. How to run locally (dev)

Prérequis

- Python 3.10+ dans .venv, dépendances listées dans `requirements.txt` ou `pyproject.toml`.

- Java si tu veux exécuter HAPI validator localement.

Start app (development)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FILE_POLL_INTERVAL=60
export SESSION_SECRET_KEY=change-me
uvicorn app.app:app --reload
```

Tests

```bash
pytest -q
```

Running message ingestion (MLLP)

- Configure `app.services.mllp_manager` via env vars (see `.env.example`) and start app; le manager démarre lors du lifespan si `TESTING` n'est pas activé.

## 7. CI recommendations

- Run `pytest` on every PR (already present in repo CI). Add these steps:

  1. `pytest -q` (unit tests + integration fast ones)

  2. Optional: run HAPI validator on representative generated bundles: requires installing Java and having IG pack available (publish pack as repository artifact or cache). A suggested workflow:

     - Generate sample bundle via script (or use stored `tests/artifacts/` bundles).

     - Run HAPI CLI validate with `--igpack`.

  3. Run a small roundtrip test: generate bundle → validate with HAPI (optional) → POST to import endpoint using TestClient, assert no errors.

CI stub example for HAPI (GitHub Actions)

1. Job setup with Java runtime (adoptopenjdk) + Python.

2. Restore IG pack from repo .tools/igpacks or download from a secure location (note: IG packs are large — consider caching externally).

## 8. Operation, logs and debugging

- Logs

  - File log at `meddata.log` (configurable via `MEDDATA_LOG_FILE`).

  - Uvicorn/worker logs capture request traces; MLLP detailed logs activables via `MLLP_TRACE`.

- Debugging tips

  - Use the debug bundle `tmp/fhir_bundle_for_import_debug.json` to reproduce import issues.

  - For FHIR import problems, verify `resource_map` contents (importer prints were used during debugging). Ensure `fullUrl` stable format when emitting bundles.

  - For IHE PAM: inspect `pam_archive` and `pam_archive_dst` directories sample files.

## 9. Security & privacy notes

- RGPD: les champs sensibles (race/religion) marqués comme legacy ne doivent pas être collectés.

- Les identifiants nationaux (NIR) et les données personnelles doivent être traités selon la politique locale (masquage, accès restreint).

## 10. Fichiers et fonctions clés (référence rapide)

- `app/app.py` : composition FastAPI, middlewares, route registration, lifespan.

- `app/db.py` : engine, sessions, sequences, before_flush adaptateur.

- `app/models.py` & `app/models_structure.py` : définitions des entités Patient/Dossier/Venue/Mouvement + structure (EG/Pole/Service/UF/UH/Chambre/Lit).

- `app/services/transport_inbound.py` : pipeline IHE PAM inbound, validation, routing.

- `app/services/mllp_manager.py` : manager MLLP (serveur/client) et reloads.

- `app/services/mfn_structure.py` : MFN generation & processing (structure export/import).

- `app/services/fhir.py`, `app/services/fhir_resources.py` : FHIR bundle/resource generation.

- `app/converters/fhir_import_converter.py` : FHIR → internal models, `FHIRBundleImporter`.

- `app/routers/fhir_import.py` : FHIR import API endpoints.

## 11. Actions recommandées / next steps

1. Ajouter un job CI qui exécute HAPI validator (optionnel mais recommandé) sur bundles représentatifs. Fournir l'IG pack comme artefact ou via un URL privé.

2. Élargir les tests roundtrip (générer bundle via code → HAPI validate → import via TestClient) pour couvrir plus de scénarios (refs entre resources, multientities, Locations).

3. Améliorer la résolution Location→Venue lors de l'import FHIR (actuellement simplifiée : première venue ou création par défaut).

4. Documenter les conventions d'identifiant (PL-6, EI formatting) si nécessaire pour les partenaires intégrateurs.
# 

Fichier créé automatiquement par un assistant de développement. Pour questions ou demandes d'approfondissement (diagrammes, séquences, ERD), dis-moi quelle section tu veux détailler et je génère ça.
