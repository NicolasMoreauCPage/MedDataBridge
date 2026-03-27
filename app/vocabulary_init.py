"""
Initialisation des vocabulaires standards et leurs correspondances
"""
from typing import List
from sqlmodel import Session
from app.models_vocabulary import VocabularySystem, VocabularyValue, VocabularyMapping, VocabularySystemType
from app.services.vocabulary_loader import create_ihe_pam_vocabularies, create_fhir_encounter_vocabularies
from app.services.vocabulary_ihe_fr import create_patient_type_vocabularies, create_patient_location_vocabularies, create_movement_vocabularies
from app.services.vocabulary_mfn import create_mfn_segment_fields
from app.services.vocabulary_fhir_fr import (
    create_fr_practitioner_specialty,
    create_fr_organization_type,
    create_fr_location_type,
    create_fr_patient_contact_role,
    create_fr_encounter_hospitalization,
    create_fr_encounter_priority,
    create_fr_patient_identity_reliability,
    create_fr_identity_method_collection,
    create_fr_encounter_discharge_circumstances,
)
from app.services.vocabulary_mappings import init_vocabulary_mappings
from app.models_vocabulary import VocabularySystemType

# --- Nouveaux vocabulaires de centralisation pour éliminer les doublons sémantiques ---
def create_location_status_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="location-status",
        label="Statut d'emplacement",
        system_type=VocabularySystemType.LOCAL,
        description="Codes statut pour Pole/Service/UF/UH/Chambre/Lit (centralisé)"
    )
    system.values = [
        VocabularyValue(code="active", display="Actif", order=1),
        VocabularyValue(code="suspended", display="Suspendu", order=2),
        VocabularyValue(code="inactive", display="Inactif", order=3),
    ]
    return [system]

def create_location_mode_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="location-mode",
        label="Mode d'emplacement",
        system_type=VocabularySystemType.LOCAL,
        description="Codes mode pour emplacements (instance/kind/hospitalization/ambulatory/virtual)"
    )
    system.values = [
        VocabularyValue(code="instance", display="Instance", order=1),
        VocabularyValue(code="kind", display="Type", order=2),
        VocabularyValue(code="hospitalization", display="Hospitalisation", order=3),
        VocabularyValue(code="ambulatory", display="Ambulatoire", order=4),
        VocabularyValue(code="virtual", display="Virtuel", order=5),
    ]
    return [system]

def create_location_physical_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="location-physical-type",
        label="Type physique emplacement",
        system_type=VocabularySystemType.LOCAL,
        description="Codes physiques HL7 harmonisés (si, bu, wi, fl, ro, bd, ve, ho, ca, rd, area, jdn)"
    )
    codes = [
        ("si", "Site"), ("bu", "Bâtiment"), ("wi", "Aile"), ("fl", "Étage"),
        ("ro", "Chambre"), ("bd", "Lit"), ("ve", "Véhicule"), ("ho", "Domicile"),
        ("ca", "Cabinet"), ("rd", "Route"), ("area", "Zone"), ("jdn", "Juridiction"),
    ]
    system.values = [
        VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(codes)
    ]
    return [system]

def create_location_service_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="location-service-type",
        label="Type de service médical",
        system_type=VocabularySystemType.LOCAL,
        description="Types de service français (MCO, SSR, PSY, HAD, EHPAD, USLD)"
    )
    codes = [
        ("mco", "Médecine/Chirurgie/Obstétrique"),
        ("ssr", "Soins de suite et de réadaptation"),
        ("psy", "Psychiatrie"),
        ("had", "Hospitalisation à domicile"),
        ("ehpad", "EHPAD"),
        ("usld", "Soins longue durée"),
    ]
    system.values = [
        VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(codes)
    ]
    return [system]

def create_dossier_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="dossier-type",
        label="Type de dossier patient",
        system_type=VocabularySystemType.LOCAL,
        description="Types de dossier (hospitalise/externe/urgence) centralisés"
    )
    system.values = [
        VocabularyValue(code="hospitalise", display="Hospitalisé", order=1),
        VocabularyValue(code="externe", display="Externe", order=2),
        VocabularyValue(code="urgence", display="Urgence", order=3),
    ]
    return [system]

def create_movement_nature_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="movement-nature",
        label="Nature mouvement ZBE",
        system_type=VocabularySystemType.LOCAL,
        description="Codes nature mouvement (S,H,M,L,D,SM) centralisés"
    )
    codes = [
        ("S", "Séjour"), ("H", "Hospitalisation"), ("M", "Mouvement"),
        ("L", "Localisation"), ("D", "Diagnostic"), ("SM", "Sous-mouvement")
    ]
    system.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(codes)]
    return [system]

def create_identity_reliability_vocab() -> List[VocabularySystem]:
    # Système canonique RNIV (sans doublon FICTI)
    rniv = VocabularySystem(
        name="identity-reliability-rniv",
        label="Fiabilité identité (RNIV)",
        system_type=VocabularySystemType.LOCAL,
        description="Codes RNIV sans doublon (VALI, QUAL, PROV, VIDE, DOUTE, DOUB)"
    )
    rniv_codes = [
        ("VALI", "Validée"), ("QUAL", "Qualifiée"), ("PROV", "Provisoire"),
        ("VIDE", "Fictive"), ("DOUTE", "Douteuse"), ("DOUB", "Doublon"),
    ]
    rniv.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(rniv_codes)]

    # Système legacy HL7 (avec FICTI) pour mapping équivalent -> VIDE
    legacy = VocabularySystem(
        name="identity-reliability-hl7v2",
        label="Fiabilité identité (HL7v2 étendu)",
        system_type=VocabularySystemType.HL7V2,
        description="Table 0445 étendue avec FICTI conservée" 
    )
    legacy_codes = rniv_codes + [("FICTI", "Fictive (HL7)")]
    legacy.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(legacy_codes)]

    # Mapping FICTI -> VIDE sera créé après commit via init_vocabulary_mappings
    # (les IDs sont nécessaires). On retourne simplement les deux systèmes.
    return [rniv, legacy]

def create_ins_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="ins-type",
        label="Type INS",
        system_type=VocabularySystemType.LOCAL,
        description="Type d'Identifiant National de Santé (NIR ou INS-C)"
    )
    system.values = [
        VocabularyValue(code="NIR", display="NIR", order=1),
        VocabularyValue(code="INS-C", display="INS Calculé", order=2),
    ]
    return [system]

def create_marital_status_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="marital-status",
        label="Statut marital",
        system_type=VocabularySystemType.LOCAL,
        description="Statuts maritaux HL7v2 (S,M,D,W,P,A,U)"
    )
    codes = [
        ("S", "Célibataire"), ("M", "Marié"), ("D", "Divorcé"),
        ("W", "Veuf"), ("P", "Partenaire"), ("A", "Séparé"), ("U", "Inconnu")
    ]
    system.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(codes)]
    return [system]

def create_country_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="country-codes",
        label="Codes pays",
        system_type=VocabularySystemType.LOCAL,
        description="Codes ISO 3 lettres pour les pays (conformité FHIR France)"
    )
    system.values = [
        VocabularyValue(code="FRA", display="🇫🇷 France", order=1),
        VocabularyValue(code="BEL", display="🇧🇪 Belgique", order=2),
        VocabularyValue(code="CHE", display="🇨🇭 Suisse", order=3),
        VocabularyValue(code="LUX", display="🇱🇺 Luxembourg", order=4),
        VocabularyValue(code="DEU", display="🇩🇪 Allemagne", order=5),
        VocabularyValue(code="ITA", display="🇮🇹 Italie", order=6),
        VocabularyValue(code="ESP", display="🇪🇸 Espagne", order=7),
        VocabularyValue(code="GBR", display="🇬🇧 Royaume-Uni", order=8),
    ]
    return [system]

def create_transport_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="transport-type",
        label="Type de transport",
        system_type=VocabularySystemType.LOCAL,
        description="Types de transport pour les messages (MLLP, FHIR, etc.)"
    )
    system.values = [
        VocabularyValue(code="MLLP", display="MLLP (HL7 v2)", order=1),
        VocabularyValue(code="FHIR", display="FHIR (JSON)", order=2),
    ]
    return [system]

def create_structure_type_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="structure-type",
        label="Type de structure",
        system_type=VocabularySystemType.LOCAL,
        description="Types de structures hospitalières (pole, service, uf, uh)"
    )
    system.values = [
        VocabularyValue(code="pole", display="Pôles", order=1),
        VocabularyValue(code="service", display="Services", order=2),
        VocabularyValue(code="uf", display="Unités Fonctionnelles", order=3),
        VocabularyValue(code="uh", display="Unités d'Hébergement", order=4),
    ]
    return [system]

def create_structure_status_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="structure-status",
        label="Statut de structure",
        system_type=VocabularySystemType.LOCAL,
        description="Statuts des structures (active, inactive)"
    )
    system.values = [
        VocabularyValue(code="active", display="Actif", order=1),
        VocabularyValue(code="inactive", display="Inactif", order=2),
    ]
    return [system]

def create_message_direction_vocab() -> List[VocabularySystem]:
    system = VocabularySystem(
        name="message-direction",
        label="Direction des messages",
        system_type=VocabularySystemType.LOCAL,
        description="Directions des messages (entrante, sortante)"
    )
    system.values = [
        VocabularyValue(code="in", display="Entrante", order=1),
        VocabularyValue(code="out", display="Sortante", order=2),
    ]
    return [system]

def _create_contact_relationship_and_role_vocab() -> List[VocabularySystem]:
    """Crée les vocabulaires pour NK1-3 (relationship) et NK1-7 (contact role).

    Deux systèmes distincts:
    - contact-relationship-hl7v2 : Représente HL7 Table 0063 codes tels que utilisés en NK1-3
    - contact-role : Système LOCAL unifié pour les rôles fonctionnels (NEXT_OF_KIN, EMERGENCY, ACCOMPANYING, GUARANTOR, CAREGIVER, OTHER)

    Les mappings (HL7 -> LOCAL) seront ajoutés par `init_vocabulary_mappings` dans une phase ultérieure.
    """
    # HL7 Table 0063 subset (IHE PAM France fréquemment utilisée)
    rel_system = VocabularySystem(
        name="contact-relationship-hl7v2",
        label="Relation contact (HL7 Table 0063)",
        system_type=VocabularySystemType.HL7V2,
        description="Codes relation NK1-3: C/E/N/SPO/CHD/PAR/SIB/GRD/FTH/MTH/O/U"
    )
    rel_codes = [
        ("C", "Contact d'urgence"),
        ("E", "Employeur"),
        ("N", "Plus proche parent"),
        ("SPO", "Conjoint"),
        ("CHD", "Enfant"),
        ("PAR", "Parent"),
        ("SIB", "Frère/Soœur"),
        ("GRD", "Tuteur"),
        ("FTH", "Père"),
        ("MTH", "Mère"),
        ("O", "Autre"),
        ("U", "Inconnu"),
    ]
    rel_system.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(rel_codes)]

    role_system = VocabularySystem(
        name="contact-role",
        label="Rôle fonctionnel du contact",
        system_type=VocabularySystemType.LOCAL,
        description="Rôles NK1-7 unifiés (NEXT_OF_KIN, EMERGENCY, ACCOMPANYING, GUARANTOR, CAREGIVER, OTHER)"
    )
    role_codes = [
        ("NEXT_OF_KIN", "Personne à prévenir"),
        ("EMERGENCY", "Contact d'urgence"),
        ("ACCOMPANYING", "Accompagnant"),
        ("GUARANTOR", "Garant financier"),
        ("CAREGIVER", "Aidant"),
        ("OTHER", "Autre rôle"),
    ]
    role_system.values = [VocabularyValue(code=c, display=lbl, order=i+1) for i, (c, lbl) in enumerate(role_codes)]

    return [rel_system, role_system]


def create_encounter_status() -> List[VocabularySystem]:
    """Statut d'une venue - vocabulaire interne et mappings HL7v2 PV1-44/45"""
    
    # Système interne (IHE)
    fhir_system = VocabularySystem(
        name="encounter-status",
        label="Statut de venue (IHE)",
        uri="http://hl7.org/fhir/encounter-status",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Statuts de venue utilisés par notre modèle IHE"
    )
    
    fhir_values = [
        VocabularyValue(code="planned", display="Planifié", order=1),
        VocabularyValue(code="arrived", display="Arrivé", order=2),
        VocabularyValue(code="triaged", display="Trié", order=3),
        VocabularyValue(code="in-progress", display="En cours", order=4),
        VocabularyValue(code="onleave", display="En permission", order=5),
        VocabularyValue(code="finished", display="Terminé", order=6),
        VocabularyValue(code="cancelled", display="Annulé", order=7)
    ]
    fhir_system.values = fhir_values
    
    # Système HL7v2 (adapté de PV1-44/45)
    hl7_system = VocabularySystem(
        name="encounter-status-v2",
        label="Statut de venue (HL7v2)",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Statuts de venue en HL7v2 (PV1-44/45)"
    )
    
    hl7_values = [
        VocabularyValue(code="P", display="Planifié", order=1),
        VocabularyValue(code="A", display="Arrivé", order=2),
        VocabularyValue(code="H", display="En hospitalisation", order=3),
        VocabularyValue(code="L", display="En permission", order=4),
        VocabularyValue(code="C", display="Terminé", order=5),
        VocabularyValue(code="X", display="Annulé", order=6)
    ]
    hl7_system.values = hl7_values
    
    # Mappings
    # NOTE: encounter-status mappings are created via init_vocabulary_mappings()
    # after commit so that value IDs are available. Do not create them here.

    return [fhir_system, hl7_system]

def init_vocabularies(session):
    """Initialise toutes les listes de valeurs standards"""
    
    all_systems = []
    # Vocabulaires de base
    from app.vocabularies.init import create_semantic_administrative_gender, create_semantic_patient_class
    all_systems.extend(create_semantic_administrative_gender(session))
    all_systems.extend(create_semantic_patient_class(session))
    all_systems.extend(create_encounter_status())
    
    # Vocabulaires IHE PAM FR
    all_systems.extend(create_patient_type_vocabularies())
    all_systems.extend(create_patient_location_vocabularies())
    all_systems.extend(create_movement_vocabularies())
    
    # Vocabulaires IHE PAM standard
    all_systems.extend(create_ihe_pam_vocabularies())
    
    # Vocabulaires FHIR internationaux
    all_systems.extend(create_fhir_encounter_vocabularies())
    
    # Vocabulaires FHIR français (NOS)
    all_systems.extend(create_fr_practitioner_specialty())
    all_systems.extend(create_fr_organization_type())
    all_systems.extend(create_fr_location_type())
    all_systems.extend(create_fr_patient_contact_role())
    all_systems.extend(create_fr_encounter_hospitalization())
    all_systems.extend(create_fr_encounter_priority())
    all_systems.extend(create_fr_patient_identity_reliability())
    all_systems.extend(create_fr_identity_method_collection())
    all_systems.extend(create_fr_encounter_discharge_circumstances())
    
    # Vocabulaires MFN pour structures
    all_systems.extend(create_mfn_segment_fields())

    # Nouveaux vocabulaires de centralisation (évite doublons sémantiques)
    all_systems.extend(create_location_status_vocab())
    all_systems.extend(create_location_mode_vocab())
    all_systems.extend(create_location_physical_type_vocab())
    all_systems.extend(create_location_service_type_vocab())
    all_systems.extend(create_dossier_type_vocab())
    all_systems.extend(create_movement_nature_vocab())
    all_systems.extend(create_identity_reliability_vocab())
    all_systems.extend(create_ins_type_vocab())
    all_systems.extend(create_marital_status_vocab())
    all_systems.extend(create_country_vocab())
    all_systems.extend(create_transport_type_vocab())
    all_systems.extend(create_structure_type_vocab())
    all_systems.extend(create_structure_status_vocab())
    all_systems.extend(create_message_direction_vocab())
    # --- Nouveau: Vocabulaire des relations et rôles de contact (HL7 NK1) ---
    # Ajout séparé pour éviter collision avec create_fr_patient_contact_role (spécifique NOS FHIR)
    all_systems.extend(_create_contact_relationship_and_role_vocab())
    
    # Sauvegarder tous les systèmes et leurs valeurs
    # Some helper functions may have created VocabularyMapping objects and
    # attached them to VocabularyValue.mappings in-memory. These mapping
    # objects are not attached to the DB session and trigger SAWarnings when
    # SQLModel autoflush inspects relationships. Clear any such in-memory
    # mappings ONLY on transient (non-session-tracked) objects to avoid
    # corrupting already-persisted relationships.
    from sqlalchemy import inspect as _sa_inspect
    for system in all_systems:
        for val in getattr(system, "values", []) or []:
            try:
                state = _sa_inspect(val)
                if state.transient:
                    # Safe to clear raw in-memory collection directly
                    val.__dict__.pop('mappings', None)
            except Exception:
                pass

    for system in all_systems:
        session.add(system)
    
    session.commit()

    # Initialiser les mappings entre vocabulaires
    # REMARQUE: doit être fait après la création des systèmes car utilise leurs IDs
    # Use a fresh session for mappings to avoid identity-map replacement warnings
    # that can occur when new objects are flushed/loaded into the same session
    # during complex commit/flush sequences.
    try:
        from sqlmodel import Session as SQLModelSession
        engine = session.get_bind()
        with SQLModelSession(engine) as new_sess:
            init_vocabulary_mappings(new_sess)
    except Exception:
        # Solution de repli: if creating a new session fails for any reason, attempt
        # to run mappings in the provided session to preserve original behavior.
        init_vocabulary_mappings(session)
