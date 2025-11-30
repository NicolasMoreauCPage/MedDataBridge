# Documentation technique de l'intégration IHE PAM (Profil France)

## 1. Architecture générale

L'intégration IHE PAM repose sur un pipeline de traitement des messages HL7v2 (principalement ADT) conforme au profil IHE PAM France. Le code est structuré autour des modules suivants :

- `app/services/transport_inbound.py` : pipeline principal, validation, parsing, routage, journalisation, gestion transactionnelle.
- `app/services/pam_validation.py` : validation des messages selon les règles IHE PAM, HL7 v2.5 et extensions locales.
- `app/services/message_router.py` : routage métier des triggers ADT vers les handlers appropriés.
- `app/services/pam.py` : logique métier pour chaque type de mouvement (admission, transfert, sortie, etc.), gestion des entités Patient/Dossier/Venue/Mouvement.
- `app/services/patient_merge.py` : gestion des fusions d'identités (A40).
- `adapters/hl7_pam_fr.py` : génération de messages HL7 PAM conformes au profil France.

## 2. Pipeline de traitement

### 2.1. Entrée des messages
- Les messages HL7v2 sont reçus via MLLP et transmis à `on_message_inbound_async`.
- Validation structurelle (MSH, type, trigger, segments obligatoires) : rejet immédiat si non conforme.
- Journalisation dans `MessageLog` (payload, type, statut, acquittement).

### 2.2. Parsing des segments
- Utilisation de parseurs robustes pour : PID, PV1, ZBE, MRG, NK1, PD1.
- Extraction des identifiants, noms, dates, lieux, contacts, etc.
- Support des répétitions (~) et des extensions locales (ZBE, Z99).

### 2.3. Validation métier
- Validation IHE PAM via `validate_pam` : segments requis, cohérence, format, transitions.
- Contrôles HL7 v2.5 : séparateurs, encodage, dates, identifiants.
- Rejet possible selon configuration endpoint (mode strict/warn).

### 2.4. Routage et gestion des mouvements
- Routage via `IHEMessageRouter` selon le trigger (A01, A02, A03, etc.).
- Handlers dédiés pour chaque type de mouvement : admission, transfert, sortie, permission, fusion, etc.
- Création/mise à jour des entités Patient, Dossier, Venue, Mouvement.
- Gestion des annulations (A11, A12, A13, etc.) et des mises à jour partielles (Z99).
- Persistance des contacts (NK1) pour patient et venue.

### 2.5. Fusions d'identités (A40)
- Traitement du segment MRG pour identifier le patient source.
- Ré-attribution des dossiers, venues, mouvements, identifiants au patient survivant.
- Archivage du patient source, journalisation de l'opération.

## 3. Extensibilité et conventions

- Les parseurs de segments sont factorisés dans `app/infrastructure/hl7/parsing.py` pour faciliter l'évolution.
- Les règles de validation sont configurables via variables d'environnement (STRICT_PAM_FR, ENABLE_PAM_EXT, PID13_STRICT, etc.).
- Les handlers métier sont extensibles : chaque trigger peut être redirigé vers un handler spécifique.
- Les extensions locales (ZBE, Z99) sont gérées de façon tolérante pour le sandbox/test.
- La génération de messages HL7 PAM est centralisée dans `adapters/hl7_pam_fr.py` pour garantir la conformité.

## 4. Points d'intégration et extension

- Ajout de nouveaux triggers : il suffit d'ajouter le mapping dans `IHEMessageRouter.HANDLERS` et d'implémenter le handler.
- Extension des règles de validation : modifier/étendre `pam_validation.py` (SEGMENT_RULES, contrôles, etc.).
- Adaptation du parsing : enrichir les parseurs dans `infrastructure/hl7/parsing.py`.
- Support de nouveaux segments : ajouter le parsing et la validation dans les modules appropriés.

## 5. Limitations et points d'attention

- La validation HL7 v2.5 est partielle : pour une conformité totale, utiliser un parseur certifié (ex : HAPI).
- Les extensions locales (Z99, ZBE) sont tolérantes en sandbox, mais doivent être strictes en production.
- Les transitions de workflow sont validées par scénario, mais certains cas complexes peuvent nécessiter des ajustements.
- Les fusions d'identités (A40) ne gèrent pas les conflits de données cliniques/financières (à étendre si besoin).
- Les variables d'environnement influencent le comportement : bien vérifier la configuration selon le contexte d'intégration.

## 6. Références et documentation

- Spécification IHE PAM France : [Doc/IHE_PAM.md]
- Règles HL7 v2.5 : [Doc/HL7v2.5/CH02A.pdf], [Doc/HL7v2.5/Ch03.pdf]
- Structures HAPI : [Doc/HAPI/hapi/custom/message/]
- Documentation utilisateur : [Doc/IHE_PAM.md], [scripts/validate_pam.py]

---

Pour toute extension ou adaptation, se référer aux modules cités et aux conventions de factorisation et de configuration décrites ci-dessus.
