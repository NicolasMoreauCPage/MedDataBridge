# Référence Modèles de Données

## Vue d'Ensemble

L'architecture repose sur des modèles SQLModel (ORM SQLAlchemy + validation Pydantic). Organisation en 9 modules:

- `models.py`: Entités métier principales

- `models_structure.py`: Hiérarchie organisationnelle

- `models_vocabulary.py`: Vocabulaires contrôlés

- `models_identifiers.py`: Gestion identifiants

- `models_endpoints.py`: Configuration endpoints

- `models_transport.py`: Logs messages

- `models_context.py`: Contextes GHT/EJ

- `models_scenarios.py`: Scénarios tests

- `models_workflows.py`: Workflows métier

## Patient

### Définition

```python

class Patient(SQLModel, table=True):
    __tablename__ = "patient"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=100, index=True)
    prenom: str = Field(max_length=100, index=True)
    nom_usage: str | None = Field(default=None, max_length=100)
    sexe: Sexe
    date_naissance: datetime.date
    lieu_naissance: str | None = Field(default=None, max_length=100)
    code_insee_naissance: str | None = Field(default=None, max_length=10)
    pays_naissance: str | None = Field(default=None, max_length=3)
    adresse: str | None = None
    adresse_naissance: str | None = None
    ville: str | None = Field(default=None, max_length=100)
    code_postal: str | None = Field(default=None, max_length=10)
    pays: str | None = Field(default=None, max_length=3)
    telephone_fixe: str | None = Field(default=None, max_length=20)
    telephone_mobile: str | None = Field(default=None, max_length=20)
    nom_jeune_fille: str | None = Field(default=None, max_length=100)

```

### Relations

- `identifiants`: List[PatientIdentifier] (one-to-many)

- `dossiers`: List[Dossier] (one-to-many)

### Indices

- nom (recherche rapide)

- prenom (recherche rapide)

- (nom, prenom, date_naissance) composite (unicité fonctionnelle)

### Énumération Sexe

```python

class Sexe(str, Enum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"

```

## Dossier

### Définition

```python

class Dossier(SQLModel, table=True):
    __tablename__ = "dossier"
    id: int | None = Field(default=None, primary_key=True)
    numero_dossier: str = Field(max_length=50, unique=True, index=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    ej_id: int = Field(foreign_key="entite_juridique.id", index=True)
    type_dossier: TypeDossier
    date_heure_admission: datetime.datetime
    uf_responsabilite: str | None = Field(default=None, max_length=20)
    uf_medicale_code: str | None = Field(default=None, max_length=20)
    uf_medicale_label: str | None = Field(default=None, max_length=100)

```

### Relations

- `patient`: Patient (many-to-one)

- `ej`: EntiteJuridique (many-to-one)

- `venues`: List[Venue] (one-to-many)

- `identifiants`: List[DossierIdentifier] (one-to-many)

### TypeDossier

```python

class TypeDossier(str, Enum):
    HOSPITALISE = "HOSPITALISE"
    URGENCES = "URGENCES"
    EXTERNE = "EXTERNE"
    AMBULATOIRE = "AMBULATOIRE"

```

## Venue (Séjour)

### Définition

```python

class Venue(SQLModel, table=True):
    __tablename__ = "venue"
    id: int | None = Field(default=None, primary_key=True)
    code_venue: str = Field(max_length=50, unique=True, index=True)
    dossier_id: int = Field(foreign_key="dossier.id", index=True)
    date_heure_debut: datetime.datetime
    date_heure_fin: datetime.datetime | None = None
    uf_responsabilite: str | None = Field(default=None, max_length=20)

```

### Relations

- `dossier`: Dossier (many-to-one)

- `mouvements`: List[Mouvement] (one-to-many)

### Indices

- code_venue (unicité)

- dossier_id (requêtes filtrées)

## Mouvement (Mouvement)

### Définition (Complet avec ZBE Compliance)

```python

class Mouvement(SQLModel, table=True):
    __tablename__ = "mouvement"
    id: int | None = Field(default=None, primary_key=True)
    numero_sequence: str = Field(max_length=50, index=True)
    venue_id: int = Field(foreign_key="venue.id", index=True)
    dossier_id: int = Field(foreign_key="dossier.id", index=True)
    date_heure_mouvement: datetime.datetime = Field(index=True)
    location: str | None = Field(default=None, max_length=200)
    trigger_event: str = Field(max_length=3)
    action: ActionZBE = Field(default=ActionZBE.INSERT)
    is_historic: bool = Field(default=False)
    original_trigger: str | None = Field(default=None, max_length=3)
    nature: str | None = Field(default=None, max_length=2)
    uf_medicale_code: str | None = Field(default=None, max_length=20, index=True)
    uf_medicale_label: str | None = Field(default=None, max_length=100)
    uf_soins_code: str | None = Field(default=None, max_length=20, index=True)
    uf_soins_label: str | None = Field(default=None, max_length=100)
    movement_ids: str | None = Field(default=None, sa_type=JSON)
    cancelled_movement_seq: str | None = Field(default=None, max_length=50)
    type_mouvement: str | None = Field(default=None, max_length=10)

```

### Relations

- `venue`: Venue (many-to-one)

- `dossier`: Dossier (many-to-one)

### ActionZBE

```python

class ActionZBE(str, Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    CANCEL = "CANCEL"

```

### Indices

- numero_sequence + venue_id (unicité composite)

- date_heure_mouvement (tri chronologique)

- uf_medicale_code, uf_soins_code (filtrage UF)

- (dossier_id, date_heure_mouvement) composite (requêtes dossier)

### Champs ZBE (Migration 014)

- `action`: INSERT | UPDATE | CANCEL (ZBE-4)

- `is_historic`: Mouvement historique Y/N (ZBE-5)

- `original_trigger`: Trigger initial pour UPDATE/CANCEL (ZBE-6)

- `nature`: S,H,M,L,D,SM (ZBE-9)

- `uf_medicale_code/label`: UF médicale (ZBE-7)

- `uf_soins_code/label`: UF soins optionnelle (ZBE-8)

- `movement_ids`: JSON array identifiants mouvement (ZBE-1 répétitions)

## Structure Hiérarchique

### EntiteJuridique (EJ)

```python

class EntiteJuridique(SQLModel, table=True):
    __tablename__ = "entite_juridique"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200, index=True)
    finess: str = Field(max_length=9, unique=True, index=True)
    ght_id: int | None = Field(default=None, foreign_key="ght.id")

```

### GHT (Groupement Hospitalier de Territoire)

```python

class GHT(SQLModel, table=True):
    __tablename__ = "ght"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200, unique=True, index=True)
    code: str = Field(max_length=20, unique=True, index=True)

```

### Pole

```python

class Pole(SQLModel, table=True):
    __tablename__ = "pole"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200)
    identifiant: str = Field(max_length=20, unique=True, index=True)
    ej_id: int = Field(foreign_key="entite_juridique.id")

```

### Service

```python

class Service(SQLModel, table=True):
    __tablename__ = "service"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200)
    identifiant: str = Field(max_length=20, unique=True, index=True)
    pole_id: int = Field(foreign_key="pole.id")

```

### UniteFonctionnelle (UF)

```python

class UniteFonctionnelle(SQLModel, table=True):
    __tablename__ = "unite_fonctionnelle"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200)
    code: str = Field(max_length=20, unique=True, index=True)
    service_id: int = Field(foreign_key="service.id")
    is_virtual: bool = Field(default=False)

```

### UniteHebergement (UH)

```python class UniteHebergement(SQLModel, table=True):

    __tablename__ = "unite_hebergement"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200)
    identifiant: str = Field(max_length=20, unique=True, index=True)
    uf_id: int = Field(foreign_key="unite_fonctionnelle.id")
    is_virtual: bool = Field(default=False)

```

### Chambre

```python

class Chambre(SQLModel, table=True):
    __tablename__ = "chambre"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=100)
    identifiant: str = Field(max_length=20, unique=True, index=True)
    uh_id: int = Field(foreign_key="unite_hebergement.id")

```

### Lit

```python

class Lit(SQLModel, table=True):
    __tablename__ = "lit"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=100)
    identifiant: str = Field(max_length=20, unique=True, index=True)
    chambre_id: int = Field(foreign_key="chambre.id")
    statut: StatutLit = Field(default=StatutLit.disponible)
    
    model_config = {"use_enum_values": True}

class StatutLit(str, Enum):
    disponible = "disponible"
    occupe = "occupe"
    hors_service = "hors_service"

```

## Identifiants

### PatientIdentifier

```python

class PatientIdentifier(SQLModel, table=True):
    __tablename__ = "patient_identifier"
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    namespace_id: str = Field(max_length=20, index=True)
    value: str = Field(max_length=100, index=True)
    is_primary: bool = Field(default=False)

```

### DossierIdentifier

```python

class DossierIdentifier(SQLModel, table=True):
    __tablename__ = "dossier_identifier"
    id: int | None = Field(default=None, primary_key=True)
    dossier_id: int = Field(foreign_key="dossier.id", index=True)
    namespace_id: str = Field(max_length=20, index=True)
    value: str = Field(max_length=100, index=True)
    is_primary: bool = Field(default=False)

```

### Namespace

```python

class Namespace(SQLModel, table=True):
    __tablename__ = "namespace"
    id: str = Field(max_length=20, primary_key=True)
    nom: str = Field(max_length=100)
    description: str | None = None
    ej_id: int | None = Field(default=None, foreign_key="entite_juridique.id")

```

Namespaces standards:

- **IPP**: Identifiant Permanent Patient

- **NDA**: Numéro de Dossier Administratif

- **NIP**: Numéro Inscription Patient

## Endpoints & Transport

### Endpoint

```python

class Endpoint(SQLModel, table=True):
    __tablename__ = "endpoint"
    id: int | None = Field(default=None, primary_key=True)
    nom: str = Field(max_length=200)
    type: EndpointType
    direction: Direction
    host: str | None = Field(default=None, max_length=200)
    port: int | None = None
    path_inbox: str | None = None
    path_outbox: str | None = None
    file_pattern: str | None = Field(default=None, max_length=50)
    ej_emetteur_id: int | None = Field(default=None, foreign_key="entite_juridique.id")
    is_active: bool = Field(default=True)

class EndpointType(str, Enum):
    MLLP = "MLLP"
    FILE = "FILE"

class Direction(str, Enum):
    inbound = "inbound"
    outbound = "outbound"

```

### MessageLog

```python

class MessageLog(SQLModel, table=True):
    __tablename__ = "message_log"
    id: int | None = Field(default=None, primary_key=True)
    message_control_id: str = Field(max_length=100, unique=True, index=True)
    trigger_event: str = Field(max_length=3, index=True)
    direction: Direction = Field(index=True)
    contenu: str
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now, index=True)
    statut: StatutMessage = Field(default=StatutMessage.en_cours, index=True)
    erreur: str | None = None
    endpoint_id: int | None = Field(default=None, foreign_key="endpoint.id")

class StatutMessage(str, Enum):
    en_cours = "en_cours"
    succes = "succes"
    erreur = "erreur"

```

### Indices MessageLog

- message_control_id (unicité)

- trigger_event + direction + statut (requêtes filtrées)

- timestamp (tri chronologique)

## Vocabulaires

### Vocabulary

```python

class Vocabulary(SQLModel, table=True):
    __tablename__ = "vocabulary"
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(max_length=20, unique=True, index=True)
    libelle: str = Field(max_length=200)
    type: VocabularyType = Field(index=True)

class VocabularyType(str, Enum):
    nature_venue = "nature_venue"
    type_mouvement = "type_mouvement"
    mode_sortie = "mode_sortie"
    provenance = "provenance"
    destination = "destination"

```

Vocabulaires standards (chargés par `vocabulary_init.py`):

- **nature_venue**: S (Somatique), H (Hospitalisation complète), M (Maternité), etc.

- **type_mouvement**: ENTREE, TRANSFERT, SORTIE

- **mode_sortie**: NORMAL, DECES, MUTATION, FUITE, TRANSFERT_AUTRE_EJ

- **provenance**: DOMICILE, AUTRE_EJ, URGENCES, AUTRE_SERVICE

- **destination**: DOMICILE, AUTRE_EJ, DECES, AUTRE_SERVICE

## Contextes GHT & EJ

### GHTContext

```python

class GHTContext(SQLModel, table=True):
    __tablename__ = "ght_context"
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(max_length=100, index=True)
    ght_id: int = Field(foreign_key="ght.id")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

```

### EJContext

```python

class EJContext(SQLModel, table=True):
    __tablename__ = "ej_context"
    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(max_length=100, index=True)
    ej_id: int = Field(foreign_key="entite_juridique.id")
    timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)

```

Sessions web associent GHT/EJ via `session_id`, permettant filtrage contextuel.

## Conventions

### Naming

- Tables: snake_case (patient, mouvement, entite_juridique)

- Champs: snake_case (nom, date_heure_mouvement, uf_medicale_code)

- Enums: PascalCase avec valeurs SCREAMING_SNAKE_CASE ou lowercase selon usage

### Contraintes

- Clés étrangères toujours indexées (_id suffix)

- Champs de recherche indexés (nom, prenom, finess, codes)

- Unicité composite où nécessaire (numero_sequence + venue_id)

### Validation Pydantic

- max_length spécifié pour tous les str

- Field(default=None) pour optionnels

- Énumérations strictes (pas de valeurs libres)

---
Référence modèles v0.2.0
