# Intégration IHE PAM (Profil France) — Documentation technique complète

Version : 2025-11-30


## Objectif

Ce document décrit de manière exhaustive l’intégration des messages IHE PAM (ADT, ZBE, MRG, etc.) dans MedData_Bridge, en conformité avec les spécifications IHE France (voir `/Doc/SpecIHEPAM/`). Il s’adresse aux experts de l’interopérabilité, développeurs et intégrateurs qui doivent maintenir, étendre ou valider le pipeline PAM.

## Sommaire

1. Segments HL7 lus et mapping

2. Gestion des identifiants et namespaces

3. Modèle relationnel et parentage

4. Algorithme de traitement et transactionnalité

5. Règles métier par trigger

6. Cas d’erreur et diagnostics

7. Tests de validation et régression

8. Annexes et utilitaires
# 

## 1. Segments HL7 lus et mapping

### Segments principaux traités

- **MSH** : En-tête du message. Tous les champs sont validés selon la spec IHE France : séparateur, encodage, type, trigger, version, control ID, processing ID.

- **EVN** : Événement. EVN-1 doit être cohérent avec MSH-9 (type/trigger).

- **PID** : Identité patient. Validation stricte de PID-3 (identifiants, format CX), PID-5 (nom), PID-7 (date naissance), PID-8 (genre), PID-11 (adresse), PID-13 (téléphones), PID-18 (account number), PID-32 (identity reliability code). Les champs sont mappés vers l’entité `Patient` et ses identifiants.

- **PV1** : Séjour. PV1-2 (patient class), PV1-3 (location), PV1-10 (hospital service), PV1-19 (visit number). Mapping vers `Venue` et rattachement au `Dossier`.

- **ZBE** : Extension France pour mouvements. ZBE-1 (identifiant mouvement), ZBE-2 (datetime), ZBE-4 (action), ZBE-6 (trigger original), ZBE-7/8 (UF médicale/soins), ZBE-9 (nature). Mapping vers `Mouvement` et gestion des annulations/updates.

- **MRG** : Fusion d’identités. MRG-1 (identifiants à fusionner), MRG-7 (nom précédent). Utilisé pour A40 (fusion patient).

- **NK1** : Contacts. Mapping vers `PatientContact` ou `VenueContact` selon la date/heure.

- **PD1** : Informations complémentaires patient (optionnel).

### Mapping code → modèle

- Chaque segment est parsé et validé dans `app/services/transport_inbound.py` et `app/infrastructure/hl7/parsing.py`.

- Les champs sont mappés vers les modèles SQLModel : `Patient`, `Dossier`, `Venue`, `Mouvement`, `Identifier`, `PatientContact`, `VenueContact`.

- Les identifiants CX/EI sont validés selon les contraintes IHE France (voir `/Doc/SpecIHEPAM/IHE_France_Constraints_on_HL7_data_types_for_ITI_V1.8.1.txt`).

- Les extensions ZBE/Z99 sont traitées selon les règles nationales (tolérance sandbox, stricte en production).

### Contraintes IHE France

- Usage et cardinalité de chaque champ sont respectés (R, RE, O, C, X) : voir tableaux des specs.

- Listes de valeurs restreintes pour certains champs (genre, classe patient, nature mouvement, etc.).

- Les champs interdits (X) sont ignorés ou rejetés.

- Les champs conditionnels (C) sont validés selon la logique métier (ex : ZBE obligatoire pour mouvements, MRG obligatoire pour fusion).
# 

## 2. Gestion des identifiants et namespaces

- **PID-3** : identifiant patient (CX), format : `ID^^^SYSTEM&OID&ISO^PI`. Validation de la structure, unicité, longueur EI-1 (≤16 caractères si profil strict).

- **PV1-19** : identifiant de séjour (CX), même validation.

- **ZBE-1** : identifiant mouvement (ID^AUTHORITY^OID^ISO), mapping direct vers `Mouvement.mouvement_seq`.

- **MRG-1** : identifiants à fusionner (CX répétés), utilisés pour rattacher les entités sources au survivant.

- Les namespaces (authority, OID) sont extraits et validés selon les specs.

- Les conventions de codage sont alignées sur `/Doc/SpecIHEPAM/IHE_France_Constraints_on_HL7_data_types_for_ITI_V1.8.1.txt`.
# 

## 3. Modèle relationnel et parentage

- **Patient** → **Dossier** → **Venue** → **Mouvement**

- Parentage résolu par identifiant (PID-3, PV1-19, ZBE-1).

- Annulation, fusion, update : rattachement dynamique selon le trigger et la présence des segments.

- Contacts (NK1) rattachés au patient ou à la venue selon la date/heure (voir parsing NK1).

- Les entités sont créées ou mises à jour dans une transaction SQLModel, rollback en cas d’erreur.
# 

## 4. Algorithme de traitement et transactionnalité

- Pipeline principal : `on_message_inbound_async` (validation, parsing, routage, journalisation, gestion transactionnelle).

- Validation structurelle (MSH, type, trigger, segments obligatoires, usage/cardinalité).

- Parsing des segments, mapping vers modèles, validation métier (règles IHE France).

- Routage métier via `IHEMessageRouter` selon le trigger (A01, A03, A11, A12, A13, A40, Z99, etc.).

- Gestion des annulations, fusions, mises à jour partielles (Z99), fallback sur dernier mouvement si identifiant manquant.

- Log détaillé de chaque étape, création de parents virtuels si nécessaire.
# 

## 5. Règles métier par trigger

- **A01/A04/A05/A06/A07** : admission, pré-admission, changement de classe. Création ou mise à jour de Patient/Dossier/Venue/Mouvement.

- **A02/A12** : transfert, annulation de transfert. Mise à jour du Mouvement, rattachement dynamique.

- **A03/A13** : sortie, annulation de sortie. Mise à jour du Mouvement, statut venue/dossier.

- **A11/A23/A38** : annulation admission/enregistrement/préadmission. Fallback sur dernier mouvement si ZBE-1 absent.

- **A21/A22/A52/A53** : permission, retour, annulation. Gestion des mouvements temporaires.

- **A40** : fusion d’identités (PID/MRG). Ré-attribution des dossiers, venues, mouvements, identifiants au survivant, archivage du patient source.

- **Z99** : mises à jour partielles, tolérance sandbox, création de parents virtuels si entité manquante.

- Validation stricte des transitions (ordre logique, cohérence temporelle, voir `validate_transition`).
# 

## 6. Cas d’erreur et diagnostics

- **Identifiant manquant** : log, rejet, fallback sur dernier mouvement ou création de parent virtuel.

- **Parent manquant** : report à la pass suivante, création de parent virtuel.

- **Import incomplet** : log d’avertissement, rollback transaction.

- **Collision ou incohérence** : log, création de lien virtuel, rejet si non résoluble.

- **Annulation sans mouvement cible** : fallback sur dernier mouvement du patient/dossier/venue.

- **Erreur de validation IHE France** : log détaillé, rejet ou warning selon configuration.
# 

## 7. Tests de validation et régression

- Validation roundtrip admission → transfert → sortie → annulation, avec contrôle des transitions et des identifiants.

- Vérification de la cohérence des identifiants et des relations parent/enfant.

- Utilisation de jeux de données de test pour tous les cas d’erreur et de fallback.

- Scripts : `scripts/validate_pam.py` (message/workflow), rapports dans `reports/pam_import_report.json`.

- Tests unitaires et d’intégration dans `archives/tests/` et `pam_archive_dst/`.
# 

## 8. Annexes et utilitaires

- **Listes de valeurs officielles** : genre, classe patient, nature mouvement, status, triggers, etc. (voir `/Doc/SpecIHEPAM/Publication-IHE_FRANCE_PAM_National_Extension_v2.11.1.txt`).

- **Exemples de messages PAM** : ADT^A01, ADT^A03, ADT^A11, ADT^A40, Z99, etc. (voir jeux de données de test).

- **Utilitaires de parsing et génération** : `app/services/pam.py`, `adapters/hl7_pam_fr.py`, `app/infrastructure/hl7/parsing.py`.

- **Patterns d’écriture atomique** : recommandés pour éviter les corruptions lors de l’import/export.

- **Références** : specs IHE France, code source, scripts de validation, rapports d’import.


Document rédigé le 30/11/2025. Pour toute extension, se référer aux modules cités, aux conventions de factorisation et aux contraintes officielles IHE France.
