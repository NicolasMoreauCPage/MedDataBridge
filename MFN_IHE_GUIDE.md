# Guide des Messages MFN (Master File Notification) - IHE PAM France 2.11

Ce guide documente l'implémentation des messages MFN^M05 pour la gestion des fichiers maîtres (structures et organisations) conformément à IHE PAM France 2.11.

## Table des Matières

1. [Introduction](#introduction)
2. [Format MSH des Messages MFN](#format-msh-des-messages-mfn)
3. [Types d'Événements MFE](#types-dévénements-mfe)
4. [MFN^M05 pour Structures (Locations)](#mfnm05-pour-structures-locations)
5. [MFN^M05 pour Organisations](#mfnm05-pour-organisations)
6. [Vocabulaires Locaux](#vocabulaires-locaux)
7. [Exemples Complets](#exemples-complets)

---

## Introduction

Les messages MFN (Master File Notification) sont utilisés pour synchroniser les fichiers maîtres entre systèmes :
- **Structures hospitalières** : Entités géographiques, pôles, services, unités fonctionnelles, chambres, lits
- **Organisations** : Entités juridiques, établissements
- **Professionnels** : Staff, practitioners
- **Observations** : Tests, nomenclatures

Ce guide se concentre sur **MFN^M05** (Master File Notification - Patient Location).

---

## Format MSH des Messages MFN

### Structure MSH Conforme IHE PAM France 2.11

```
MSH|^~\&|APP|FAC|RECEIVER|RECEIVER|20251110203000||MFN^M05^MFN_M05|MSG123|P|2.5^FRA^2.11|||||FRA|8859/1
```

### Champs MSH Obligatoires

| Champ | Position | Valeur | Description |
|-------|----------|--------|-------------|
| MSH-1 | 1 | `\|` | Field Separator |
| MSH-2 | 2 | `^~\\&` | Encoding Characters |
| MSH-3 | 3 | STR, MedBridge | Sending Application |
| MSH-4 | 4 | STR, MedBridge | Sending Facility |
| MSH-5 | 5 | RECEIVER | Receiving Application |
| MSH-6 | 6 | RECEIVER | Receiving Facility |
| MSH-7 | 7 | YYYYMMDDHHmmss | Date/Time of Message |
| MSH-9 | 9 | **MFN^M05^MFN_M05** | Message Type |
| MSH-10 | 10 | Unique ID | Message Control ID |
| MSH-11 | 11 | P | Processing ID (P=Production) |
| MSH-12 | 12 | **2.5^FRA^2.11** | Version ID (IHE PAM France 2.11) |
| MSH-17 | 17 | **FRA** | Country Code |
| MSH-18 | 18 | **8859/1** | Character Set (ISO-8859-1) |

### ⚠️ Corrections Appliquées

✅ **AVANT** : `MSH|...|P|2.5|||||FRA|8859/15`
✅ **APRÈS** : `MSH|...|P|2.5^FRA^2.11|||||FRA|8859/1`

- MSH-12 : `2.5` → `2.5^FRA^2.11`
- MSH-18 : `8859/15` → `8859/1`

---

## Types d'Événements MFE

Le segment MFE (Master File Entry) définit l'action à effectuer sur une entrée du fichier maître.

### MFE-1 : Record-Level Event Code

| Code | Description | Utilisation |
|------|-------------|-------------|
| **MAD** | **Master File Add** | Ajouter/Mettre à jour une entrée |
| **MUP** | **Master File Update** | Mettre à jour une entrée existante |
| **MDL** | **Master File Delete** | Supprimer une entrée |
| **MUC** | **Master File Update on Commit** | Mise à jour différée |

### MFE-5 : Primary Key Value Type

| Code | Description |
|------|-------------|
| **PL** | Person Location (structure hospitalière) |
| **ORG** | Organization (entité juridique) |
| **STF** | Staff (professionnel) |

### Exemple MFE

```
MFE|MAD|||^^^^^M^^^^EG001|PL
```

Décomposition :
- **MFE-1** : `MAD` (Add/Update)
- **MFE-4** : `^^^^^M^^^^EG001` (Primary Key - Entité Géographique EG001)
- **MFE-5** : `PL` (Person Location)

---

## MFN^M05 pour Structures (Locations)

### Architecture Hiérarchique

```
EntiteGeographique (M)
  └─ Pole (P)
      └─ Service (D)
          └─ UniteFonctionnelle (UF)
              └─ UniteHebergement (UH)
                  └─ Chambre (CH)
                      └─ Lit (LIT)
```

### Structure du Message

```
MSH|^~\&|STR|STR|RECEIVER|RECEIVER|20251110203000||MFN^M05^MFN_M05|MSG123|P|2.5^FRA^2.11|||||FRA|8859/1
MFI|LOC|CPAGE_LOC_FRA|REP||20251110203000|AL
MFE|MAD|||^^^^^M^^^^EG001|PL
LOC|^^^^^M^^^^EG001||M|Etablissement juridique
LCH|^^^^^M^^^^EG001|||ID_GLBL^Identifiant unique global^L|^EG001
LCH|^^^^^M^^^^EG001|||LBL^Libelle^L|^CHU Test
LCH|^^^^^M^^^^EG001|||LBL_CRT^Libelle court^L|^CHU
LCH|^^^^^M^^^^EG001|||FNS^Code FINESS^L|^010000123
```

### Segments Principaux

#### MFI - Master File Identification

```
MFI|LOC|CPAGE_LOC_FRA|REP||20251110203000|AL
```

- **MFI-1** : `LOC` (Location master file)
- **MFI-2** : `CPAGE_LOC_FRA` (Application identifier)
- **MFI-3** : `REP` (Replace/Snapshot) ou `UPD` (Update)
- **MFI-6** : `AL` (Always - response level)

#### LOC - Location Identification

```
LOC|^^^^^M^^^^EG001||M|Etablissement juridique
```

- **LOC-1** : `^^^^^M^^^^EG001` (Primary Key)
- **LOC-3** : `M`, `P`, `D`, `UF`, `UH`, `CH`, `LIT` (Location Type)
- **LOC-4** : Description

#### LCH - Location Characteristic

```
LCH|^^^^^M^^^^EG001|||ID_GLBL^Identifiant unique global^L|^EG001
```

- **LCH-1** : Primary Key (même que LOC-1)
- **LCH-4** : `CODE^Description^L` (Code caractéristique)
- **LCH-5** : `^Valeur` (Valeur de la caractéristique)

#### LRL - Location Relationship

```
LRL|^^^^^P^^^^POLE001|||LCLSTN^Relation de localisation^L||^^^^^M^^^^EG001
```

- **LRL-1** : Primary Key (location enfant)
- **LRL-4** : `LCLSTN^Relation de localisation^L` (Type de relation)
- **LRL-6** : Primary Key (location parent)

### Types de Locations

| Code | Description | Segments Spécifiques |
|------|-------------|----------------------|
| **M** | Entité Géographique (Établissement) | FNS (FINESS), CTGR_S (Catégorie SAE) |
| **P** | Pôle | Relation → EG |
| **D** | Service | TPLG (Typologie), Relation → Pôle |
| **UF** | Unité Fonctionnelle | CD_UM (Code UM), Relation → Service |
| **UH** | Unité d'Hébergement | Relation → UF |
| **CH** | Chambre | Relation → UH |
| **LIT** | Lit | OPERATIONAL_STATUS, Relation → Chambre |

---

## MFN^M05 pour Organisations

### Structure du Message

```
MSH|^~\&|MedBridge|MedBridge|RECEIVER|RECEIVER|20251110203000||MFN^M05^MFN_M05|MSG123|P|2.5^FRA^2.11|||||FRA|8859/1
MFI|ORG|MEDBRIDGE_ORG|REP||20251110203000|AL
MFE|MAD|||010000123^^^FINESS&1.2.250.1.71.4.2.2&ISO^FINEJ|ORG
STF|010000123^^^FINESS&1.2.250.1.71.4.2.2&ISO^FINEJ|010000123^^^FINESS&1.2.250.1.71.4.2.2&ISO^FINEJ|CHU Test^^^^||||||||||||||
PRA|010000123^^^FINESS&1.2.250.1.71.4.2.2&ISO^FINEJ||ORG
```

### Segments Spécifiques

#### MFI pour Organizations

```
MFI|ORG|MEDBRIDGE_ORG|REP||20251110203000|AL
```

- **MFI-1** : `ORG` (Organization master file)

#### MFE pour Organizations

```
MFE|MAD|||010000123^^^FINESS&1.2.250.1.71.4.2.2&ISO^FINEJ|ORG
```

- **MFE-4** : Format CX avec FINESS et OID
- **MFE-5** : `ORG` (Organization type)

#### STF - Staff Identification (adapté pour Organization)

```
STF|ID|ID|NOM^^^^|...
```

- **STF-1** : Primary Key
- **STF-2** : Staff Identifier (FINESS)
- **STF-3** : Nom de l'organisation (format XPN)

#### PRA - Practitioner Detail (adapté pour Organization)

```
PRA|ID||ORG
```

- **PRA-1** : Primary Key (même que STF-1)
- **PRA-3** : `ORG` (Category)

---

## Vocabulaires Locaux

### Codes LCH pour Entité Géographique

| Code | Description | Exemple |
|------|-------------|---------|
| **ID_GLBL** | Identifiant unique global | `^EG001` |
| **LBL** | Libellé | `^CHU Test` |
| **LBL_CRT** | Libellé court | `^CHU` |
| **FNS** | Code FINESS | `^010000123` |
| **CTGR_S** | Catégorie SAE | `^355` |
| **ADRS_1** | Adresse 1 | `^1 rue de l'Hôpital` |
| **ADRS_2** | Adresse 2 | `^Bâtiment A` |
| **ADRS_3** | Adresse 3 | `^CS 12345` |
| **CD_PSTL** | Code postal | `^75001` |
| **VL** | Ville | `^Paris` |
| **INS** | Code INSEE commune | `^75101` |
| **TPLG** | Typologie | `^MCO` |
| **DT_OVRTR** | Date d'ouverture | `^20200101` |
| **DT_ACTVTN** | Date d'activation | `^20200101` |
| **DT_FRMTR** | Date de fermeture | `^20251231` |
| **DT_FN_ACTVTN** | Date de fin d'activation | `^20251231` |

### Codes LCH pour Service

| Code | Description |
|------|-------------|
| **ID_GLBL_RSPNSBL** | Identifiant unique global du responsable |
| **NM_USL_RSPNSBL** | Nom usuel du responsable |
| **PRNM_RSPNSBL** | Prénom du responsable |
| **RPPS_RSPNSBL** | Code RPPS du responsable |
| **ADL_RSPNSBL** | Code ADELI du responsable |
| **CD_SPCLT_RSPNSBL** | Code spécialité B2 du responsable |

### Codes LRL pour Relations

| Code | Description |
|------|-------------|
| **LCLSTN** | Relation de localisation (enfant → parent) |
| **ETBLSMNT** | Relation établissement (pôle → EG) |

### Format des Codes

Tous les codes utilisent le système local :
```
CODE^Description^L
```

Exemple :
```
LCH|^^^^^M^^^^EG001|||ID_GLBL^Identifiant unique global^L|^EG001
```

---

## Exemples Complets

### Exemple 1 : Entité Géographique Complète

```hl7
MSH|^~\&|STR|STR|RECEIVER|RECEIVER|20251110203000||MFN^M05^MFN_M05|MSG123|P|2.5^FRA^2.11|||||FRA|8859/1
MFI|LOC|CPAGE_LOC_FRA|REP||20251110203000|AL
MFE|MAD|||^^^^^M^^^^EG001|PL
LOC|^^^^^M^^^^EG001||M|Etablissement juridique
LCH|^^^^^M^^^^EG001|||ID_GLBL^Identifiant unique global^L|^EG001
LCH|^^^^^M^^^^EG001|||LBL^Libelle^L|^CHU de Test
LCH|^^^^^M^^^^EG001|||LBL_CRT^Libelle court^L|^CHU Test
LCH|^^^^^M^^^^EG001|||FNS^Code FINESS^L|^010000123
LCH|^^^^^M^^^^EG001|||ADRS_1^Adresse 1^L|^1 rue de l'Hôpital
LCH|^^^^^M^^^^EG001|||CD_PSTL^Code postal^L|^75001
LCH|^^^^^M^^^^EG001|||VL^Ville^L|^Paris
LCH|^^^^^M^^^^EG001|||CTGR_S^Catégorie SAE^L|^355
LCH|^^^^^M^^^^EG001|||INS^Code INSEE commune^L|^75101
LCH|^^^^^M^^^^EG001|||TPLG^Typologie^L|^CHU
LCH|^^^^^M^^^^EG001|||DT_OVRTR^Date d'ouverture^L|^20200101
```

### Exemple 2 : Hiérarchie Complète

```hl7
MSH|^~\&|STR|STR|RECEIVER|RECEIVER|20251110203000||MFN^M05^MFN_M05|MSG123|P|2.5^FRA^2.11|||||FRA|8859/1
MFI|LOC|CPAGE_LOC_FRA|REP||20251110203000|AL
# Entité Géographique
MFE|MAD|||^^^^^M^^^^EG001|PL
LOC|^^^^^M^^^^EG001||M|Etablissement juridique
LCH|^^^^^M^^^^EG001|||ID_GLBL^Identifiant unique global^L|^EG001
LCH|^^^^^M^^^^EG001|||LBL^Libelle^L|^CHU Test
# Pôle
MFE|MAD|||^^^^^P^^^^POLE001|PL
LOC|^^^^^P^^^^POLE001||P|Pole
LCH|^^^^^P^^^^POLE001|||ID_GLBL^Identifiant unique global^L|^POLE001
LCH|^^^^^P^^^^POLE001|||LBL^Libelle^L|^Pôle Médecine
LRL|^^^^^P^^^^POLE001|||ETBLSMNT^Relation établissement^L||^^^^^M^^^^EG001
# Service
MFE|MAD|||^^^^^D^^^^SRV001|PL
LOC|^^^^^D^^^^SRV001||D|Service
LCH|^^^^^D^^^^SRV001|||ID_GLBL^Identifiant unique global^L|^SRV001
LCH|^^^^^D^^^^SRV001|||LBL^Libelle^L|^Service Cardiologie
LCH|^^^^^D^^^^SRV001|||TPLG^Typologie^L|^MCO
LRL|^^^^^D^^^^SRV001|||LCLSTN^Relation de localisation^L||^^^^^P^^^^POLE001
```

### Exemple 3 : Lit avec Hiérarchie

```hl7
# UF
MFE|MAD|||^^^^^UF^^^^UF001|PL
LOC|^^^^^UF^^^^UF001||UF|Unite Fonctionnelle
LCH|^^^^^UF^^^^UF001|||ID_GLBL^Identifiant unique global^L|^UF001
LCH|^^^^^UF^^^^UF001|||LBL^Libelle^L|^UF Cardiologie
LCH|^^^^^UF^^^^UF001|||CD_UM^Code UM^L|^CARDIO
LRL|^^^^^UF^^^^UF001|||LCLSTN^Relation de localisation^L||^^^^^D^^^^SRV001
# UH
MFE|MAD|||^^^^^UH^^^^UH001|PL
LOC|^^^^^UH^^^^UH001||UH|Unite Hebergement
LCH|^^^^^UH^^^^UH001|||ID_GLBL^Identifiant unique global^L|^UH001
LCH|^^^^^UH^^^^UH001|||LBL^Libelle^L|^UH Cardiologie
LRL|^^^^^UH^^^^UH001|||LCLSTN^Relation de localisation^L||^^^^^UF^^^^UF001
# Chambre
MFE|MAD|||^^^^^CH^^^^CH101|PL
LOC|^^^^^CH^^^^CH101||CH|Chambre
LCH|^^^^^CH^^^^CH101|||ID_GLBL^Identifiant unique global^L|^CH101
LCH|^^^^^CH^^^^CH101|||LBL^Libelle^L|^Chambre 101
LRL|^^^^^CH^^^^CH101|||LCLSTN^Relation de localisation^L||^^^^^UH^^^^UH001
# Lit
MFE|MAD|||^^^^^LIT^^^^LIT101A|PL
LOC|^^^^^LIT^^^^LIT101A||LIT|Lit
LCH|^^^^^LIT^^^^LIT101A|||ID_GLBL^Identifiant unique global^L|^LIT101A
LCH|^^^^^LIT^^^^LIT101A|||LBL^Libelle^L|^Lit 101A
LCH|^^^^^LIT^^^^LIT101A|||OPERATIONAL_STATUS^Statut opérationnel^L|^AVAILABLE
LRL|^^^^^LIT^^^^LIT101A|||LCLSTN^Relation de localisation^L||^^^^^CH^^^^CH101
```

---

## Validation et Tests

### Tests Automatiques

Le fichier `tests/test_mfn_structure.py` contient 9 tests complets :

1. **test_mfn_msh_structure_format** : Valide MSH-12, MSH-17, MSH-18
2. **test_mfn_msh_field_count** : Valide le nombre de champs MSH
3. **test_mfi_structure** : Valide MFI-1, MFI-3, MFI-6
4. **test_generate_mfn_entite_geographique** : EG complète
5. **test_mfn_eg_lch_vocabulary** : Vocabulaires LCH pour EG
6. **test_generate_mfn_service_with_pole** : Service + Pôle + Relations
7. **test_generate_mfn_complete_hierarchy** : Hiérarchie complète (7 niveaux)
8. **test_lch_coding_system_local** : Tous les LCH utilisent `^L`
9. **test_lrl_coding_system_local** : Tous les LRL utilisent `^L`

### Exécution des Tests

```bash
python3 -m pytest tests/test_mfn_structure.py -v
```

**Résultat** : ✅ 9/9 tests passants

---

## Références

- **IHE PAM France 2.11** : [https://www.interopsante.org/](https://www.interopsante.org/)
- **HL7 v2.5 MFN^M05** : HL7 Version 2.5 Implementation Guide
- **Segments HL7** : LOC, LCH, LRL, MFE, MFI
- **FINESS** : Fichier National des Établissements Sanitaires et Sociaux
- **Code SAE** : Statistique Annuelle des Établissements

---

## Historique des Modifications

| Date | Version | Modification |
|------|---------|--------------|
| 2025-11-10 | 1.0 | Création du guide - Corrections MSH + Tests MFN |
| | | - MSH-12 : `2.5` → `2.5^FRA^2.11` |
| | | - MSH-18 : `8859/15` → `8859/1` |
| | | - 9 tests MFN structure (100% passants) |
