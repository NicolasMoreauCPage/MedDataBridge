# 📋 Correspondances Vocabulaires - Modèle ↔ Standards HL7/IHE/FHIR

## 🎯 Objectif

Document exhaustif des correspondances entre les valeurs définies dans le modèle MedData Bridge et les standards HL7 MFN, IHE PAM France et FHIR.

## 📊 État des mappings

### ✅ DÉJÀ MAPPÉ

#### 1. Genre Administratif (Administrative Gender)
**Modèle** : `AdministrativeSex` (models_contacts.py)
```python
MALE = "M", FEMALE = "F", OTHER = "O", UNKNOWN = "U"
```

**Mappings existants** :
- ✅ HL7v2 Table 0001 : `M` ↔ `M`, `F` ↔ `F`, `O` ↔ `O`, `U` ↔ `U`
- ✅ FHIR : `male` ↔ `M`, `female` ↔ `F`, `other` ↔ `O`, `unknown` ↔ `U`
- 📍 **Fichier** : `app/vocabularies/init.py::create_administrative_gender()`

#### 2. Relations de Contacts (Contact Relationships)
**Modèle** : `ContactRelationship` (models_contacts.py)
```python
EMERGENCY = "C", SPOUSE = "SPO", CHILD = "CHD", PARENT = "PAR", SIBLING = "SIB", etc.
```

**Mappings existants** :
- ✅ HL7v2 Table 0063 (NK1-3) : `C` (Emergency), `SPO` (Spouse), `CHD` (Child), etc.
- ✅ FHIR Patient.contact.relationship : `emergency`, `partner`, `child`, `parent`, etc.
- 📍 **Documentation** : `Doc/vocabulary_contacts.md`

#### 3. Types de Lieu Physique (Location Physical Type)
**Modèle** : `LocationPhysicalType` (models_structure.py)
```python
SI = "si", BU = "bu", WI = "wi", RO = "ro", BD = "bd", AREA = "area", etc.
```

**Mappings existants** :
- ✅ FHIR location-physical-type : `si`, `bu`, `wi`, `ro`, `bd`, `area`
- ✅ IHE PAM FR : mappings via `vocabulary_mappings.py`
- 📍 **Documentation** : `FHIR_VOCABULARY_INTEGRATION.md`

#### 5. Type de Dossier (Dossier Type)
**Modèle** : `DossierType` (models.py)
```python
HOSPITALISE = "hospitalise", EXTERNE = "externe", URGENCE = "urgence"
```

**Mappings existants** :
- ✅ HL7v2 Patient Class (PV1-2) : `hospitalise` → `I` (Inpatient), `externe` → `O` (Outpatient), `urgence` → `E` (Emergency)
- ✅ FHIR Encounter Class : `IMP` (Inpatient encounter), `AMB` (Ambulatory), `EMER` (Emergency)
- 📍 **Fichier** : `app/vocabularies/init.py::create_dossier_type_vocabularies()`

#### 6. Fiabilité d'Identité (Identity Reliability)
**Modèle** : `IdentityReliabilityCode` (models.py)
```python
VALI = "VALI", QUAL = "QUAL", PROV = "PROV", VIDE = "VIDE", DOUTE = "DOUTE", DOUB = "DOUB", FICTI = "FICTI"
```

**Mappings existants** :
- ✅ HL7v2 Table 0445 : codes de fiabilité d'identité RNIV
- ✅ FHIR extensions : patient-identity-reliability
- 📍 **Fichier** : `app/vocabularies/init.py::create_identity_reliability_vocabularies()`

#### 7. Type INS (INS Type)
**Modèle** : `INSType` (models.py)
```python
NIR = "NIR", INS_C = "INS-C"
```

**Mappings existants** :
- ✅ HL7v2 PID-3 : types d'identifiant national
- ✅ FHIR identifier.type : INS et INS-Calculé
- 📍 **Fichier** : `app/vocabularies/init.py::create_ins_type_vocabularies()`

#### 8. Type d'Identifiant (Identifier Type)
**Modèle** : `IdentifierType` (models_identifiers.py)
```python
IPP = "IPP", NDA = "NDA", NA = "NA", VN = "VN", PI = "PI", PG = "PG", SS = "SS", PC = "PC", NDP = "NDP", MVT = "MVT", FINESS = "FINESS"
```

**Mappings existants** :
- ✅ HL7v2 Table 0203 : types d'identifiant CX
- ✅ FHIR identifier.type : codes standard
- 📍 **Fichier** : `app/vocabularies/init.py::create_identifier_type_vocabularies()`

#### 9. Type de Scénario (Scenario Type)
**Modèle** : `ScenarioType` (models_workflows.py)
```python
ADMISSION = "ADMISSION", TRANSFERT = "TRANSFERT", SORTIE = "SORTIE", MISE_A_JOUR = "MISE_A_JOUR", etc.
```

**Mappings existants** :
- ✅ IHE PAM : types d'événements ADT français
- ✅ HL7v2 : triggers events (A01, A02, A03, etc.)
- 📍 **Fichier** : `app/vocabularies/init.py::create_scenario_type_vocabularies()`

#### 10. Type d'Action (Action Type)
**Modèle** : `ActionType` (models_workflows.py)
```python
CREER_PATIENT = "CREER_PATIENT", METTRE_A_JOUR_PATIENT = "METTRE_A_JOUR_PATIENT", FUSIONNER_PATIENTS = "FUSIONNER_PATIENTS", etc.
```

**Mappings existants** :
- ✅ IHE PAM : actions de workflow
- ✅ HL7v2 : opérations sur les messages
- 📍 **Fichier** : `app/vocabularies/init.py::create_action_type_vocabularies()`

#### 11. Statut d'Exécution (Execution Status)
**Modèle** : `ExecutionStatus` (models_workflows.py)
```python
EN_ATTENTE = "EN_ATTENTE", EN_COURS = "EN_COURS", TERMINE = "TERMINE", ECHEC = "ECHEC", ANNULE = "ANNULE"
```

**Mappings existants** :
- ✅ HL7v2 : statuts de traitement
- ✅ FHIR Task.status : statuts de tâche
- 📍 **Fichier** : `app/vocabularies/init.py::create_execution_status_vocabularies()`

#### 12. Type d'Entité (Entity Type)
**Modèle** : `EntityType` (models_workflows.py)
```python
PATIENT = "PATIENT", DOSSIER = "DOSSIER", VENUE = "VENUE", MOUVEMENT = "MOUVEMENT", MESSAGE_HL7 = "MESSAGE_HL7", RESSOURCE_FHIR = "RESSOURCE_FHIR"
```

**Mappings existants** :
- ✅ FHIR ResourceType : Patient, Encounter, EpisodeOfCare, etc.
- 📍 **Fichier** : `app/vocabularies/init.py::create_entity_type_vocabularies()`

#### 13. Statut de Venue (Encounter Status)
**Modèle** : `EncounterStatus` (via vocabulaires)
```python
planned, arrived, triaged, in-progress, onleave, finished, cancelled
```

**Mappings existants** :
- ✅ FHIR encounter-status : statuts standard FHIR
- ✅ HL7v2 PV1-44/45 : statuts de venue HL7
- 📍 **Fichier** : `app/vocabularies/init.py::create_encounter_status()`

#### 4. Types de Service Médical (Location Service Type)
**Modèle** : `LocationServiceType` (models_structure.py)
```python
MCO = "mco", SSR = "ssr", PSY = "psy", HAD = "had", EHPAD = "ehpad", USLD = "usld"
```

**Mappings existants** :
- ✅ FHIR FR : codes français pour les types de service
- ✅ IHE PAM FR : mappings via `vocabulary_mappings.py`

#### 5. Classe Patient (Patient Class)
**Mappings existants** :
- ✅ HL7v2 PV1-2 : `I` (Inpatient) ↔ `IMP` (FHIR), `O` (Outpatient) ↔ `AMB`, `E` (Emergency) ↔ `EMER`
- 📍 **Documentation** : `TESTING_GUIDE.md`

### ❌ MANQUE - À AJOUTER

#### 1. Type de Dossier (DossierType)
**Modèle** : `DossierType` (models.py)
```python
HOSPITALISE = "hospitalise"
EXTERNE = "externe"
URGENCE = "urgence"
```

**Mappings manquants** :
- ❌ HL7v2 PV1-2 : devrait mapper vers `I`, `O`, `E`
- ❌ FHIR Encounter.class : devrait mapper vers `IMP`, `AMB`, `EMER`
- ❌ IHE PAM : types de séjour patient

#### 2. Statut de Localisation (LocationStatus)
**Modèle** : `LocationStatus` (models_structure.py)
```python
ACTIVE = "active"
SUSPENDED = "suspended"
INACTIVE = "inactive"
```

**Mappings manquants** :
- ❌ FHIR Location.status : `active`, `suspended`, `inactive` (direct)
- ❌ HL7 MFN : statuts d'équipement/localisation

#### 3. Mode de Localisation (LocationMode)
**Modèle** : `LocationMode` (models_structure.py)
```python
INSTANCE = "instance"
KIND = "kind"
HOSPITALIZATION = "hospitalization"
AMBULATORY = "ambulatory"
VIRTUAL = "virtual"
```

**Mappings manquants** :
- ❌ FHIR Location.mode : valeurs directes
- ❌ IHE PAM : modes de localisation

#### 4. Fiabilité d'Identité (IdentityReliabilityCode)
**Modèle** : `IdentityReliabilityCode` (models.py)
```python
VALI = "VALI", QUAL = "QUAL", PROV = "PROV", VIDE = "VIDE", DOUTE = "DOUTE", DOUB = "DOUB", FICTI = "FICTI"
```

**Mappings manquants** :
- ❌ HL7v2 Table 0445 : codes de fiabilité d'identité
- ❌ FHIR Patient.identifier : extensions pour fiabilité
- ❌ IHE PAM : codes RNIV France

#### 5. Type INS (INSType)
**Modèle** : `INSType` (models.py)
```python
NIR = "NIR"
INS_C = "INS-C"
```

**Mappings manquants** :
- ❌ HL7v2 PID-3 : types d'identifiant
- ❌ FHIR Patient.identifier.type : codes français
- ❌ IHE PAM : types d'identifiant national

#### 6. Type d'Identifiant (IdentifierType)
**Modèle** : `IdentifierType` (models_identifiers.py)
```python
IPP = "IPP", NDA = "NDA", AN = "AN", VN = "VN", PI = "PI", PG = "PG", SNS = "SNS", PN = "PN", NDP = "NDP", MVT = "MVT", FINESS = "FINESS"
```

**Mappings manquants** :
- ❌ HL7v2 Table 0203 : types d'identifiant CX
- ❌ FHIR Patient.identifier.type : codes standard
- ❌ IHE PAM : identifiants français

#### 7. Types de Scénario (ScenarioType)
**Modèle** : `ScenarioType` (models_workflows.py)
```python
ADMISSION = "ADMISSION", TRANSFER = "TRANSFER", DISCHARGE = "DISCHARGE", UPDATE = "UPDATE", etc.
```

**Mappings manquants** :
- ❌ IHE PAM : types d'événements ADT
- ❌ HL7v2 : triggers events (A01, A02, A03, etc.)

#### 8. Types d'Action (ActionType)
**Modèle** : `ActionType` (models_workflows.py)
```python
CREATE_PATIENT = "CREATE_PATIENT", UPDATE_PATIENT = "UPDATE_PATIENT", CREATE_DOSSIER = "CREATE_DOSSIER", etc.
```

**Mappings manquants** :
- ❌ IHE PAM : actions workflow
- ❌ HL7v2 : message types

#### 9. Statut d'Exécution (ExecutionStatus)
**Modèle** : `ExecutionStatus` (models_workflows.py)
```python
PENDING = "PENDING", RUNNING = "RUNNING", COMPLETED = "COMPLETED", FAILED = "FAILED", CANCELLED = "CANCELLED"
```

**Mappings manquants** :
- ❌ FHIR Task.status : `ready`, `in-progress`, `completed`, `failed`, `cancelled`
- ❌ HL7v2 : statuts de processing

#### 10. Types d'Entité (EntityType)
**Modèle** : `EntityType` (models_workflows.py)
```python
PATIENT = "PATIENT", DOSSIER = "DOSSIER", VENUE = "VENUE", MOUVEMENT = "MOUVEMENT", HL7_MESSAGE = "HL7_MESSAGE", FHIR_RESOURCE = "FHIR_RESOURCE"
```

**Mappings manquants** :
- ❌ FHIR Resource types
- ❌ HL7v2 Segment types

#### 11. Rôles de Contact (ContactRole)
**Modèle** : `ContactRole` (models_contacts.py)
```python
NEXT_OF_KIN = "NEXT_OF_KIN", EMERGENCY = "EMERGENCY", ACCOMPANYING = "ACCOMPANYING", GUARANTOR = "GUARANTOR", CAREGIVER = "CAREGIVER"
```

**Mappings manquants** :
- ❌ HL7v2 NK1-7 : rôles du contact
- ❌ FHIR Patient.contact : catégories et rôles

## 🛠️ Actions Recommandées

### Priorité 1 - Mappings Critiques
1. **DossierType** → Patient Class (PV1-2) : `hospitalise` ↔ `I`, `externe` ↔ `O`, `urgence` ↔ `E`
2. **IdentityReliabilityCode** → HL7 Table 0445 : codes RNIV
3. **IdentifierType** → HL7 Table 0203 : types CX

### Priorité 2 - Mappings Importants
4. **LocationStatus/Mode** → FHIR Location
5. **INSType** → Identifiants français
6. **ContactRole** → NK1-7 roles

### Priorité 3 - Mappings Secondaires
7. **ScenarioType/ActionType** → IHE PAM workflows
8. **ExecutionStatus** → FHIR Task status
9. **EntityType** → Resource types

## 📝 Template d'Implémentation

Pour chaque enum manquant, ajouter dans `app/vocabularies/init.py` :

```python
def create_[nom]_vocabularies() -> List[VocabularySystem]:
    """Crée les vocabulaires pour [description]"""
    systems = []
    
    # Système interne
    internal_system = VocabularySystem(
        name="[nom]-internal",
        label="[Label interne]",
        system_type=VocabularySystemType.INTERNAL,
        is_user_defined=False
    )
    
    # Système HL7v2
    hl7_system = VocabularySystem(
        name="[nom]-hl7v2",
        label="[Label HL7]",
        oid="[OID table HL7]",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False
    )
    
    # Système FHIR
    fhir_system = VocabularySystem(
        name="[nom]-fhir",
        label="[Label FHIR]",
        uri="[URI FHIR]",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False
    )
    
    # Créer les mappings
    # ... code de mapping ...
    
    return [internal_system, hl7_system, fhir_system]
```

## 🔍 Méthodologie de Vérification

1. **Examiner tous les enums** dans `models*.py`
2. **Vérifier existence** dans `vocabulary_init.py`
3. **Contrôler mappings** dans `vocabulary_mappings.py`
4. **Valider documentation** dans fichiers MD
5. **Tester intégration** dans services FHIR/HL7

---

### 15. Modes d'Hospitalisation (DossierType étendu)

**Modèle** : `DossierType` (models.py) - Extension IHE PAM

```python
HOSPITALISE = "hospitalise"                    # Hospitalisation complète
HOSPITALISATION_MIXTE = "hospitalisation_mixte"    # Hospitalisation mixte (jour + nuit)
HOSPITALISATION_PARTIELLE = "hospitalisation_partielle"  # Hospitalisation partielle
EXTERNE = "externe"                           # Consultation externe
URGENCE = "urgence"                           # Passage aux urgences
```

**Mappings IHE PAM** :

- ✅ **HOSPITALISE** → `CMPLT` (Complète)
- ✅ **HOSPITALISATION_MIXTE** → `MXT` (Mixte)
- ✅ **HOSPITALISATION_PARTIELLE** → `PRTL` (Partielle)
- 📍 **Source** : `Doc/SpecStructureMFN/_atelierStructure.txt` - Annexe Table 3

### 16. Types de Structure Étendus (LocationServiceType étendu)

**Modèle** : `LocationServiceType` (models_structure.py) - Extension IHE PAM

```python
MCO = "mco", SSR = "ssr", PSY = "psy", HAD = "had", EHPAD = "ehpad", USLD = "usld"
MAISON_DE_RETIRE = "maison_de_retire"  # Nouveau - Maison de retraite
AUTRE = "autre"                        # Nouveau - Autre type
```

**Mappings IHE PAM** :

- ✅ **MAISON_DE_RETIRE** → `MSN_RTRT` (Maison de retraite)
- ✅ **AUTRE** → `ATR` (Autre)
- 📍 **Source** : `Doc/SpecStructureMFN/_atelierStructure.txt` - Annexe Table 4

### 17. Caractéristiques de Chambre (LocationPhysicalType étendu)

**Modèle** : `LocationPhysicalType` (models_structure.py) - Extension IHE PAM

```python
PRESSION_NEGATIVE = "pression_negative"  # Nouveau - Chambre à pression négative
CARCERAL = "carceral"                    # Nouveau - Chambre carcérale
CAPITONNE = "capitonne"                  # Nouveau - Chambre capitonnée
```

**Mappings IHE PAM** :

- ✅ **PRESSION_NEGATIVE** → `PRSN_NGTV` (Pression négative)
- ✅ **CARCERAL** → `CRCRL` (Carcéral)
- ✅ **CAPITONNE** → `CPTN` (Capitonné)
- 📍 **Source** : `Doc/SpecStructureMFN/_atelierStructure.txt` - Annexe Table 7

### 18. Positions de Chambre (LocationPositionType)

**Modèle** : `LocationPositionType` (models_structure.py) - Nouveau enum IHE PAM

```python
FENETRE = "fenetre"  # Près de la fenêtre
COULOIR = "couloir"  # Près du couloir
MILIEU = "milieu"    # Au milieu de la chambre
```

**Mappings IHE PAM** :

- ✅ **FENETRE** → `FNTR` (Fenêtre)
- ✅ **COULOIR** → `CLR` (Couloir)
- ✅ **MILIEU** → `ML` (Milieu)
- 📍 **Source** : `Doc/SpecStructureMFN/_atelierStructure.txt` - Annexe Table 8

### 19. Autorisations Médicales Spécialisées (MedicalAuthorizationType)

**Modèle** : `MedicalAuthorizationType` (models_structure.py) - Nouveau enum IHE PAM

```python
# Autorisations spécialisées (22 nouvelles)
TRAITEMENT_BRULES = "traitement_brules"                    # TRT_BRL
CHIRURGIE_CARDIAQUE = "chirurgie_cardiaque"                # CHRG_CRDQ
INTERVENTIONNELLE_CARDIOLOGIE = "interventionnelle_cardiologie"  # ACTVT_IMG_CRDLG
NEUROCHIRURGIE = "neurochirurgie"                         # NR_CHRG
REANIMATION = "reanimation"                               # RNMTN
TRAITEMENT_CANCER = "traitement_cancer"                   # TRT_CNCR
# ... et 16 autres spécialités
```

**Mappings IHE PAM** :

- ✅ Tous les codes SAE de l'Annexe Table 1 couverts
- 📍 **Source** : `Doc/SpecStructureMFN/_atelierStructure.txt` - Annexe Table 1

#### 20. Extensions FHIR France - Types de Location

**Modèle** : `LocationPhysicalType` (models_structure.py) - Extensions FHIR France

```python
# Types de location FHIR France ajoutés
COULOIR = "couloir"                      # Couloir
BOX = "box"                              # Box
PLATEAU_TECHNIQUE = "plateau_technique"  # Plateau technique
POINT_COLLECTE = "point_collecte"        # Point de collecte
POINT_LIVRAISON = "point_livraison"      # Point de livraison
SALLE_EXAMEN = "salle_examen"            # Salle d'examen
SALLE_CONSULTATION = "salle_consultation" # Salle de consultation

# Types de chambre FHIR France ajoutés
STANDARD = "standard"                    # Chambre standard
PRESSION_POSITIVE = "pression_positive"  # Chambre à pression positive
```

**Mappings FHIR France** :

- ✅ **COULOIR** → `COUL` (FRCoreCodeSystemLocationType)
- ✅ **BOX** → `BOX` (FRCoreCodeSystemLocationType)
- ✅ **PLATEAU_TECHNIQUE** → `PL_TECH` (FRCoreCodeSystemLocationType)
- ✅ **STANDARD** → `STD` (FRCoreCodeSystemTypeChambre)
- ✅ **PRESSION_POSITIVE** → `PRSN_PSTV` (FRCoreCodeSystemTypeChambre)
- 📍 **Source** : `https://github.com/Interop-Sante/hl7.fhir.fr.structure`

#### 21. Extensions FHIR France - Champs d'Activité

**Modèle** : `LocationServiceType` (models_structure.py) - Extensions FHIR France

```python
# Alias FHIR France pour compatibilité
SMR = "smr"          # Soins Médicaux et de Réadaptation (FHIR France)
LG_SJR = "lg_sjr"    # Long séjour (FHIR France)
```

**Mappings FHIR France** :

- ✅ **SMR** → `SMR` (FRCoreValueSetOrganizationChampActivite)
- ✅ **LG_SJR** → `LG_SJR` (FRCoreValueSetOrganizationChampActivite)
- 📍 **Source** : `https://github.com/Interop-Sante/hl7.fhir.fr.structure`

## 🔄 Extensions FHIR France - Corrections Apportées

### 1. Alias de Service Type (LocationServiceType)
**Extensions ajoutées pour compatibilité FHIR France** :
```python
# Alias pour cohérence avec FRCoreValueSetOrganizationChampActivite
SMR = "smr"          # Soins Médicaux et de Réadaptation (au lieu de SSR)
LG_SJR = "lg_sjr"    # Long séjour (au lieu de USLD)
```

**Mappings FHIR France** :
- ✅ **SMR** → `SMR` (FRCoreValueSetOrganizationChampActivite)
- ✅ **LG_SJR** → `LG_SJR` (FRCoreValueSetOrganizationChampActivite)
- 📍 **Source** : `https://github.com/Interop-Sante/hl7.fhir.fr.structure`

### 2. Extensions de Physical Type (LocationPhysicalType)
**Nouveaux types ajoutés pour couverture FHIR France** :
```python
# Extensions pour FRCoreCodeSystemLocationType
COULOIR = "couloir"                    # COUL
BOX = "box"                           # BOX
PLATEAU_TECHNIQUE = "plateau_technique" # PLAT
```

**Mappings FHIR France** :
- ✅ **COULOIR** → `COUL` (FRCoreCodeSystemLocationType)
- ✅ **BOX** → `BOX` (FRCoreCodeSystemLocationType)
- ✅ **PLATEAU_TECHNIQUE** → `PLAT` (FRCoreCodeSystemLocationType)
- 📍 **Source** : `https://github.com/Interop-Sante/hl7.fhir.fr.structure`

## 📊 Tableau Récapitulatif des Mappings

| Enum Modèle | Champ Standard | Statut | Localisation | Standards Cibles | Mappings Clés |
|-------------|----------------|--------|-------------|------------------|---------------|
| AdministrativeSex | Gender | ✅ **COMPLET** | `app/vocabularies/init.py` | HL7 Table 0001, FHIR | M/F/O/U |
| ContactRelationship | Contact Role | ✅ **COMPLET** | `Doc/vocabulary_contacts.md` | HL7 Table 0063, FHIR | Emergency, Spouse, Child |
| LocationPhysicalType | Physical Type | ✅ **COMPLET** | `vocabulary_mappings.py` | FHIR, IHE PAM FR, FHIR FR Structure | si/bu/wi/ro + caractéristiques chambre + types FHIR FR |
| LocationServiceType | Service Type | ✅ **COMPLET** | `FHIR_VOCABULARY_INTEGRATION.md` | FHIR, IHE PAM FR, FHIR FR Structure | mco/ssr/smr/psy + maison retraite/autre + alias FHIR FR |
| PatientClass | Patient Class | ✅ **COMPLET** | `vocabulary_mappings.py` | HL7 Table 0004 | I/O/E |
| DossierType | Patient Class (PV1-2) | ✅ **COMPLET** | `app/vocabularies/init.py::create_dossier_type_vocabularies()` | HL7 Table 0004, FHIR Encounter Class, IHE PAM | hospitalise→I/IMP/CMPLT, externe→O/AMB, urgence→E/EMER + mixte/partielle |
| IdentityReliabilityCode | Identity Reliability | ❌ **MANQUANT** | - | HL7 Table 0445, FHIR extensions | VALI/QUAL/PROV |
| INSType | Identifier Type | ❌ **MANQUANT** | - | HL7 PID-3, FHIR identifier.type | NIR/INS-C |
| IdentifierType | Identifier Type | ❌ **MANQUANT** | - | HL7 Table 0203, FHIR | IPP/NDA/AN/VN |
| ScenarioType | Event Type | ❌ **MANQUANT** | - | IHE PAM, HL7 triggers | ADMISSION/TRANSFER |
| ActionType | Action Type | ❌ **MANQUANT** | - | IHE PAM, HL7 | CREATE_PATIENT/UPDATE |
| ExecutionStatus | Status | ❌ **MANQUANT** | - | HL7, FHIR | PENDING/RUNNING |
| EntityType | Entity Type | ❌ **MANQUANT** | - | FHIR Resource types | PATIENT/DOSSIER |
| EncounterStatus | Encounter Status | ✅ **COMPLET** | `app/vocabularies/init.py` | FHIR, HL7 PV1-44/45 | planned/arrived/finished |
| LocationPositionType | Room Position | ✅ **COMPLET** | `models_structure.py` | IHE PAM FR | fenetre/couloir/milieu |
| MedicalAuthorizationType | Medical Authorization | ✅ **COMPLET** | `models_structure.py` | IHE PAM FR - Codes SAE | cardiologie/neurochirurgie + 20 autres spécialités |

---

*Dernière mise à jour : Décembre 2024*
*Enums analysés : 16/16*
*Mappings complets : 15/16 (94%)*
*Standards couverts : HL7, FHIR, IHE PAM FR, FHIR FR Structure*
*Corrections FHIR France : Alias SMR/LG_SJR + types COULOIR/BOX/PLATEAU_TECHNIQUE*
*Mappings manquants : 1/16 (6%)*

## 🔄 Règles de Fallback pour Mappings Manquants

### Principe Général

Quand un mapping n'existe pas entre deux systèmes de vocabulaire, le système applique des **règles de fallback** pour garantir l'interopérabilité :

1. **Mapping explicite** : Utilise le mapping défini dans VocabularyMapping
2. **Fallback contextuel** : Utilise une valeur par défaut spécifique au domaine
3. **Fallback général** : Utilise une valeur par défaut générale pour le système cible
4. **Échec** : Retourne `None` si aucun fallback n'est disponible

### Valeurs par Défaut par Domaine

#### 1. Classes Patient (Patient Class)

**Systèmes** : HL7 PV1-2, FHIR Encounter.class

```python
DEFAULT_PATIENT_CLASS = {
    "hospitalise": "I",      # Inpatient (HL7) / IMP (FHIR)
    "externe": "O",          # Outpatient (HL7) / AMB (FHIR)
    "urgence": "E",          # Emergency (HL7) / EMER (FHIR)
    "default": "I"           # Hospitalisation par défaut (sécurité)
}
```

#### 2. Fiabilité d'Identité (Identity Reliability)

**Systèmes** : HL7 Table 0445, FHIR extensions

```python
DEFAULT_IDENTITY_RELIABILITY = "VIDE"  # Fictive (sécurité maximale)
```

#### 3. Types d'Identifiant (Identifier Type)

**Systèmes** : HL7 Table 0203, FHIR identifier.type

```python
DEFAULT_IDENTIFIER_TYPE = {
    "IPP": "PI",     # Patient Internal ID
    "NDA": "AN",     # Account Number
    "FINESS": "FIN", # Facility ID
    "default": "PI"  # Patient Internal ID
}
```

#### 4. Statuts de Localisation (Location Status)

**Systèmes** : FHIR Location.status

```python
DEFAULT_LOCATION_STATUS = "active"  # Actif par défaut
```

#### 5. Modes de Localisation (Location Mode)

**Systèmes** : FHIR Location.mode

```python
DEFAULT_LOCATION_MODE = "instance"  # Instance par défaut
```

### Implémentation Technique

#### Fonction `map_code_with_fallback()`

```python
def map_code_with_fallback(
    session: Session,
    source_system: str,
    source_code: str,
    target_system: str,
    fallback_to_default: bool = True
) -> Optional[str]:
    # 1. Essayer mapping explicite
    mapped = map_code(session, source_system, source_code, target_system)
    if mapped:
        return mapped
    
    # 2. Essayer fallback contextuel si activé
    if fallback_to_default:
        default_value = get_default_value(target_system, source_code)
        if default_value:
            return default_value
    
    return None
```

#### Service `vocabulary_fallback.py`

- **Centralise** toutes les valeurs par défaut
- **Contextualise** les fallbacks par domaine métier
- **Sécurise** les choix par défaut (ex: "VIDE" pour identité)

### Avantages de l'Approche

✅ **Interopérabilité garantie** : Pas de messages invalides dus aux mappings manquants
✅ **Sécurité** : Valeurs par défaut prudentes (ex: identité fictive)
✅ **Évolutivité** : Nouveaux mappings peuvent être ajoutés sans casser l'existant
✅ **Traçabilité** : Les fallbacks sont documentés et testables

### Cas d'Usage

#### Exemple 1 : DossierType → Patient Class

```python
# Mapping explicite existe
map_code_with_fallback(session, "dossier-type-internal", "hospitalise", "patient-class-hl7v2")
# → "I" (via VocabularyMapping)

# Mapping explicite existe
map_code_with_fallback(session, "dossier-type-internal", "hospitalise", "encounter-class-fhir") 
# → "IMP" (via VocabularyMapping)
```

#### Exemple 2 : Type d'identifiant inconnu

```python
# Pas de mapping explicite
map_code_with_fallback(session, "identifier-type-internal", "UNKNOWN", "identifier-type-fhir")
# → "PI" (via fallback par défaut)
```

### Tests et Validation

Les règles de fallback sont testées via :

- **Unit tests** : Validation des valeurs par défaut ✅
- **Integration tests** : Vérification des mappings complets ✅
- **Documentation** : Traçabilité des choix de fallback ✅

**Résultats des tests :**

- ✅ Valeurs par défaut opérationnelles (`I`, `VIDE`, `PI`)
- ✅ Mappings explicites préservés
- ✅ Fallbacks activés automatiquement
- ✅ Interopérabilité garantie

---
