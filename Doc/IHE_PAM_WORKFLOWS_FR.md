# Documentation des workflows IHE PAM (Profil France)

Version : 2025-11-30

## Objectif

Ce document détaille les workflows applicatifs IHE PAM tels qu’implémentés dans MedData_Bridge, en conformité avec les spécifications IHE France. Il s’adresse aux experts de l’interopérabilité, aux développeurs et aux intégrateurs qui doivent valider ou étendre les enchaînements de mouvements hospitaliers.

## Sommaire

1. Principes généraux des workflows PAM

2. Scénarios typiques et transitions

3. Règles de validation des enchaînements

4. Cas d’erreur et diagnostics

5. Outils de validation et jeux de test
6. Annexes (diagrammes, exemples)

## 1. Principes généraux des workflows PAM

- Un workflow PAM est une suite ordonnée d’événements HL7 (triggers ADT) pour un patient donné (PID-3).

- Les transitions doivent respecter la logique métier hospitalière et les contraintes IHE France (admission, transfert, sortie, annulation, fusion, etc.).

- Chaque événement modifie l’état du patient, du dossier, de la venue ou du mouvement.

- Les workflows sont validés par le pipeline : parsing, mapping, validation métier, journalisation.

## 2. Scénarios typiques et transitions

### 2.1. Admission classique

- A01 : Admission
- A02/A08 : Transfert ou modification
- A03 : Sortie
- A11/A13 : Annulation

### 2.2. Préadmission et changement de classe

- A04/A05/A06/A07 : Préadmission, changement de classe, etc.
- A03/A13 : Sortie ou annulation

### 2.3. Permission et retour

- A21/A22/A52/A53 : Permission, retour, annulation

### 2.4. Fusion d'identités

- A40 (PID/MRG) : Fusion de patients, ré-attribution des entités

### 2.5. Mise à jour partielle

- Z99 : Update partiel, tolérance sandbox

## 3. Règles de validation des enchaînements

- Admission (A01) doit précéder toute modification ou sortie.

- Sortie (A03) ne doit jamais précéder l’admission.

- Annulation (A11/A13) doit cibler un mouvement existant.

- Les transitions doivent respecter la cohérence temporelle (datetime ZBE-2, EVN-2).

- Les fusions (A40) doivent ré-attribuer tous les dossiers, venues, mouvements au survivant.

- Les permissions (A21/A22) doivent être rattachées à un séjour existant.

- Les mises à jour partielles (Z99) sont tolérées si le parent existe ou est virtuel.

## 4. Cas d’erreur et diagnostics

- A03 avant A01 : erreur de séquence, rejet ou fallback.

- Annulation sans cible : fallback sur dernier mouvement.

- Fusion avec identifiants manquants : log, rejet ou création de parent virtuel.

- Collision d’identifiants : log, rejet ou création de lien virtuel.

- Import incomplet : rollback transaction, log détaillé.

## 5. Outils de validation et jeux de test

- `scripts/validate_pam.py workflow path/to/messages_dir` : construit la timeline, détecte les anomalies de séquence, d’identifiants, de transitions.

- Jeux de données de test : `tests/artifacts/hospitalisation/`, `pam_archive_dst/`, `archives/tests/`.

- Rapports : `reports/pam_import_report.json`.

## 6. Annexes

- Diagrammes de workflow (admission → transfert → sortie → annulation).

- Exemples de séquences HL7 : ADT^A01, ADT^A02, ADT^A03, ADT^A11, ADT^A40, Z99.
- Références : `/Doc/SpecIHEPAM/Publication-IHE_FRANCE_PAM_National_Extension_v2.11.1.txt`, `/Doc/IHE_PAM_INTEGRATION_COMPLETE_FR.md`, code source.

## Conclusion

Document rédigé le 30/11/2025. Pour toute extension, se référer aux modules cités, aux conventions de factorisation et aux contraintes officielles IHE France.
