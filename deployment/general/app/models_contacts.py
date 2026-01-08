"""Modèles pour les contacts et personnes à prévenir (segments NK1).

Ce module définit les entités pour représenter :
- PatientContact : Contacts du patient (famille, proches) - segments NK1 des messages identité (ADT^A28, A31)
- VenueContact : Contacts liés à une venue (accompagnants, personne à prévenir) - segments NK1 des messages mouvements

Structure du segment NK1 (HL7 v2.5 IHE PAM France 2.11) :
-----------------------------------------------------------
NK1-1  : SET ID (numéro de séquence)
NK1-2  : Name (nom de la personne)  - XPN (Extended Person Name)
NK1-3  : Relationship (lien avec le patient) - CE (Coded Element)
NK1-4  : Address (adresse) - XAD
NK1-5  : Phone Number (téléphone) - XTN
NK1-6  : Business Phone Number (téléphone professionnel) - XTN
NK1-7  : Contact Role (rôle du contact) - CE
NK1-8  : Start Date (date début relation)
NK1-9  : End Date (date fin relation)
NK1-10 : Next of Kin / Associated Parties Job Title
NK1-11 : Next of Kin / Associated Parties Job Code/Class
NK1-12 : Next of Kin / Associated Parties Employee Number
NK1-13 : Organization Name - NK1
NK1-14 : Marital Status
NK1-15 : Administrative Sex
NK1-16 : Date/Time of Birth
NK1-17 : Living Dependency
NK1-18 : Ambulatory Status
NK1-19 : Citizenship
NK1-20 : Primary Language
NK1-21 : Living Arrangement
NK1-22 : Publicity Code
NK1-23 : Protection Indicator
NK1-24 : Student Indicator
NK1-25 : Religion
NK1-26 : Mother's Maiden Name
NK1-27 : Nationality
NK1-28 : Ethnic Group
NK1-29 : Contact Reason (raison du contact)
NK1-30 : Contact Person's Name
NK1-31 : Contact Person's Telephone Number
NK1-32 : Contact Person's Address
NK1-33 : Next of Kin/Associated Party's Identifiers
NK1-34 : Job Status
NK1-35 : Race
NK1-36 : Handicap
NK1-37 : Contact Person Social Security Number
NK1-38 : Next of Kin Birth Place
NK1-39 : VIP Indicator

Mapping FHIR :
--------------
PatientContact → Patient.contact[] (FHIR R4)
  - relationship : code de lien (ex: "C" = urgency contact, "E" = employer)
  - name : HumanName
  - telecom : ContactPoint[]
  - address : Address
  - gender : code
  - period : Period (start/end dates)

VenueContact → Encounter.participant[] + RelatedPerson (FHIR R4)
  - type : ParticipationType (ex: "PART" = participant)
  - individual : Reference(RelatedPerson | Practitioner)
  - period : Period

RelatedPerson (FHIR R4) :
  - patient : Reference(Patient)
  - relationship : CodeableConcept[]
  - name : HumanName
  - telecom : ContactPoint[]
  - gender : code
  - birthDate : date
  - address : Address
"""
from datetime import datetime, date
from typing import Optional
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models import Patient, Venue


class ContactRelationship(str, Enum):
    """Types de relations NK1-3 (codification HL7 Table 0063).
    
    Valeurs courantes IHE PAM France :
    - C : Emergency Contact (contact d'urgence)
    - E : Employer (employeur)
    - F : Federal Agency (agence fédérale)
    - I : Insurance Company (compagnie d'assurance)
    - N : Next-of-Kin (plus proche parent)
    - S : State Agency (agence d'état)
    - U : Unknown (inconnu)
    - O : Other (autre)
    - SPO : Spouse (conjoint)
    - CHD : Child (enfant)
    - PAR : Parent
    - SIB : Sibling (frère/soeur)
    - GRD : Guardian (tuteur)
    - FTH : Father (père)
    - MTH : Mother (mère)
    """
    EMERGENCY = "C"  # Contact d'urgence
    EMPLOYER = "E"
    NEXT_OF_KIN = "N"  # Plus proche parent
    SPOUSE = "SPO"
    CHILD = "CHD"
    PARENT = "PAR"
    SIBLING = "SIB"
    GUARDIAN = "GRD"
    FATHER = "FTH"
    MOTHER = "MTH"
    UNKNOWN = "U"
    OTHER = "O"


class ContactRole(str, Enum):
    """Rôles du contact NK1-7 (usage IHE PAM France).
    
    - NEXT_OF_KIN : Personne à prévenir
    - EMERGENCY : Contact d'urgence
    - ACCOMPANYING : Accompagnant
    - GUARANTOR : Garant financier
    - CAREGIVER : Aidant
    """
    NEXT_OF_KIN = "NEXT_OF_KIN"
    EMERGENCY = "EMERGENCY"
    ACCOMPANYING = "ACCOMPANYING"
    GUARANTOR = "GUARANTOR"
    CAREGIVER = "CAREGIVER"


class AdministrativeSex(str, Enum):
    """Sexe administratif (NK1-15, HL7 Table 0001)."""
    MALE = "M"
    FEMALE = "F"
    OTHER = "O"
    UNKNOWN = "U"


class PatientContact(SQLModel, table=True):
    """Contact du patient (segment NK1 des messages identité ADT^A28, A31).
    
    Représente les personnes liées au patient (famille, proches) à contacter
    en cas d'urgence ou pour des questions administratives.
    
    Utilisé dans :
    - ADT^A28 (création patient)
    - ADT^A31 (mise à jour patient)
    
    Mapping FHIR : Patient.contact[]
    """
    __tablename__ = "patient_contact"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relation avec le patient
    patient_id: int = Field(foreign_key="patient.id", index=True)
    patient: Optional["Patient"] = Relationship(back_populates="contacts")
    
    # NK1-1 : Numéro de séquence (ordre d'importance)
    sequence: int = Field(default=1, description="Ordre de priorité du contact (1=principal)")
    
    # NK1-2 : Nom de la personne (XPN)
    family_name: str = Field(max_length=100, description="Nom de famille")
    given_name: Optional[str] = Field(default=None, max_length=100, description="Prénom")
    middle_name: Optional[str] = Field(default=None, max_length=100, description="Deuxième prénom")
    prefix: Optional[str] = Field(default=None, max_length=20, description="Civilité (M., Mme, Dr.)")
    suffix: Optional[str] = Field(default=None, max_length=20, description="Suffixe")
    
    # NK1-3 : Relation (CE - Coded Element)
    relationship_code: str = Field(max_length=20, description="Code relation (HL7 Table 0063)")
    relationship_display: Optional[str] = Field(default=None, max_length=100, description="Libellé relation")
    relationship_system: Optional[str] = Field(default="HL7-0063", max_length=50, description="Système de codage")
    
    # NK1-4 : Adresse (XAD)
    address_line1: Optional[str] = Field(default=None, max_length=200)
    address_line2: Optional[str] = Field(default=None, max_length=200)
    address_city: Optional[str] = Field(default=None, max_length=100)
    address_postalcode: Optional[str] = Field(default=None, max_length=20)
    address_country: Optional[str] = Field(default="FR", max_length=3)
    
    # NK1-5 : Téléphone (XTN)
    phone_number: Optional[str] = Field(default=None, max_length=50, description="Téléphone personnel")
    phone_use: Optional[str] = Field(default="home", max_length=20, description="Usage: home, work, mobile")
    
    # NK1-6 : Téléphone professionnel (XTN)
    business_phone: Optional[str] = Field(default=None, max_length=50)
    
    # NK1-7 : Rôle du contact (CE)
    contact_role: Optional[str] = Field(default=None, max_length=50, description="Rôle (NEXT_OF_KIN, EMERGENCY, etc.)")
    
    # NK1-8/9 : Période de validité
    start_date: Optional[date] = Field(default=None, description="Date début relation")
    end_date: Optional[date] = Field(default=None, description="Date fin relation")
    
    # NK1-15 : Sexe administratif
    gender: Optional[str] = Field(default=None, max_length=1, description="M, F, O, U")
    
    # NK1-16 : Date de naissance
    birth_date: Optional[date] = Field(default=None)
    
    # NK1-20 : Langue principale
    primary_language: Optional[str] = Field(default=None, max_length=10, description="Code langue (ex: fr, en)")
    
    # NK1-29 : Raison du contact
    contact_reason: Optional[str] = Field(default=None, max_length=200)
    
    # Métadonnées
    is_active: bool = Field(default=True, description="Contact actif")
    is_emergency_contact: bool = Field(default=False, description="Contact d'urgence prioritaire")
    priority: int = Field(default=1, description="Priorité (1=le plus important)")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": 1,
                "sequence": 1,
                "family_name": "Dupont",
                "given_name": "Marie",
                "relationship_code": "SPO",
                "relationship_display": "Conjoint",
                "phone_number": "+33612345678",
                "contact_role": "EMERGENCY",
                "is_emergency_contact": True
            }
        }


class VenueContact(SQLModel, table=True):
    """Contact lié à une venue (segment NK1 des messages de mouvements).
    
    Représente les accompagnants ou personnes à prévenir dans le cadre
    d'une venue spécifique (hospitalisation, consultation).
    
    Utilisé dans :
    - ADT^A01 (admission)
    - ADT^A02 (transfert)
    - ADT^A03 (sortie)
    - ADT^A04 (consultation externe)
    - Autres événements de mouvements
    
    Mapping FHIR : Encounter.participant[] + RelatedPerson
    """
    __tablename__ = "venue_contact"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relation avec la venue
    venue_id: int = Field(foreign_key="venue.id", index=True)
    venue: Optional["Venue"] = Relationship(back_populates="contacts")
    
    # NK1-1 : Numéro de séquence
    sequence: int = Field(default=1, description="Ordre du contact")
    
    # NK1-2 : Nom de la personne (XPN)
    family_name: str = Field(max_length=100, description="Nom de famille")
    given_name: Optional[str] = Field(default=None, max_length=100, description="Prénom")
    middle_name: Optional[str] = Field(default=None, max_length=100)
    prefix: Optional[str] = Field(default=None, max_length=20)
    suffix: Optional[str] = Field(default=None, max_length=20)
    
    # NK1-3 : Relation avec le patient (CE)
    relationship_code: str = Field(max_length=20, description="Code relation (HL7 Table 0063)")
    relationship_display: Optional[str] = Field(default=None, max_length=100)
    relationship_system: Optional[str] = Field(default="HL7-0063", max_length=50)
    
    # NK1-4 : Adresse (XAD)
    address_line1: Optional[str] = Field(default=None, max_length=200)
    address_line2: Optional[str] = Field(default=None, max_length=200)
    address_city: Optional[str] = Field(default=None, max_length=100)
    address_postalcode: Optional[str] = Field(default=None, max_length=20)
    address_country: Optional[str] = Field(default="FR", max_length=3)
    
    # NK1-5 : Téléphone (XTN)
    phone_number: Optional[str] = Field(default=None, max_length=50)
    phone_use: Optional[str] = Field(default="home", max_length=20)
    
    # NK1-6 : Téléphone professionnel
    business_phone: Optional[str] = Field(default=None, max_length=50)
    
    # NK1-7 : Rôle du contact pour cette venue
    contact_role: Optional[str] = Field(default=None, max_length=50, description="ACCOMPANYING, NEXT_OF_KIN, etc.")
    
    # NK1-8/9 : Période (spécifique à cette venue)
    start_datetime: Optional[datetime] = Field(default=None, description="Début présence")
    end_datetime: Optional[datetime] = Field(default=None, description="Fin présence")
    
    # NK1-15 : Sexe
    gender: Optional[str] = Field(default=None, max_length=1)
    
    # NK1-16 : Date de naissance
    birth_date: Optional[date] = Field(default=None)
    
    # NK1-29 : Raison du contact pour cette venue
    contact_reason: Optional[str] = Field(default=None, max_length=200, description="Ex: Accompagnant mineur")
    
    # Flags spécifiques venue
    is_accompanying: bool = Field(default=False, description="Présent physiquement lors de la venue")
    can_visit: bool = Field(default=True, description="Autorisé à rendre visite")
    notification_required: bool = Field(default=False, description="Doit être notifié des événements")
    
    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "venue_id": 1,
                "sequence": 1,
                "family_name": "Martin",
                "given_name": "Jean",
                "relationship_code": "PAR",
                "relationship_display": "Parent",
                "phone_number": "+33698765432",
                "contact_role": "ACCOMPANYING",
                "is_accompanying": True,
                "contact_reason": "Accompagnant mineur"
            }
        }
