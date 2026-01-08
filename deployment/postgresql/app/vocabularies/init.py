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

def create_administrative_gender() -> List[VocabularySystem]:
    """Crée les vocabulaires pour le genre administratif"""
    systems = []
    
    # --- Genre administratif (IHE interne) ---
    fhir_system = VocabularySystem(
        name="administrative-gender",
        label="Genre administratif (IHE)",
        system_type=VocabularySystemType.FHIR,
        uri="http://hl7.org/fhir/administrative-gender",
        is_user_defined=False
    )
    
    fhir_values = [
        VocabularyValue(code="male", display="Masculin", definition="Homme", order=1),
        VocabularyValue(code="female", display="Féminin", definition="Femme", order=2),
        VocabularyValue(code="other", display="Autre", definition="Autre genre", order=3),
        VocabularyValue(code="unknown", display="Inconnu", definition="Genre non spécifié", order=4)
    ]
    fhir_system.values = fhir_values
    systems.append(fhir_system)
    
    # Système HL7v2 (Table 0001) utilisé pour les mappings
    hl7_system = VocabularySystem(
        name="administrative-gender-v2",
        label="Sexe administratif (HL7v2)",
        oid="2.16.840.1.113883.12.1",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Table HL7 0001 - Administrative Sex"
    )
    
    hl7_values = [
        VocabularyValue(code="M", display="Masculin", definition="Homme", order=1),
        VocabularyValue(code="F", display="Féminin", definition="Femme", order=2),
        VocabularyValue(code="O", display="Autre", definition="Autre", order=3),
        VocabularyValue(code="U", display="Inconnu", definition="Inconnu", order=4),
        VocabularyValue(code="A", display="Ambigu", definition="Ambigu", order=5),
        VocabularyValue(code="N", display="Non applicable", definition="Non applicable", order=6)
    ]
    hl7_system.values = hl7_values
    
    # Mappings
    mappings = [
        # FHIR male -> HL7 M
        VocabularyMapping(
            source_value=fhir_values[0],  # male
            target_system=hl7_system,
            target_code="M",
            map_type="equivalent"
        ),
        # FHIR female -> HL7 F
        VocabularyMapping(
            source_value=fhir_values[1],  # female
            target_system=hl7_system,
            target_code="F",
            map_type="equivalent"
        ),
        # FHIR other -> HL7 O
        VocabularyMapping(
            source_value=fhir_values[2],  # other
            target_system=hl7_system,
            target_code="O",
            map_type="equivalent"
        ),
        # FHIR unknown -> HL7 U
        VocabularyMapping(
            source_value=fhir_values[3],  # unknown
            target_system=hl7_system,
            target_code="U",
            map_type="equivalent"
        )
    ]
    
    return [fhir_system, hl7_system]

def create_dossier_type_vocabularies(session) -> List[VocabularySystem]:
    """Crée les vocabulaires pour le type de dossier (mapping vers patient class)"""

    # Système interne (notre modèle)
    internal_system = VocabularySystem(
        name="dossier-type-internal",
        label="Type de dossier (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types de dossier utilisés dans notre modèle"
    )

    internal_values = [
        VocabularyValue(code="hospitalise", display="Hospitalisé", definition="Hospitalisation complète", order=1),
        VocabularyValue(code="externe", display="Externe", definition="Consultation externe", order=2),
        VocabularyValue(code="urgence", display="Urgence", definition="Passage aux urgences", order=3)
    ]
    internal_system.values = internal_values

    # Système HL7v2 Patient Class (PV1-2)
    hl7_system = VocabularySystem(
        name="patient-class-hl7v2",
        label="Classe patient (HL7v2 PV1-2)",
        oid="2.16.840.1.113883.12.4",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Table HL7 0004 - Patient Class"
    )

    hl7_values = [
        VocabularyValue(code="I", display="Inpatient", definition="Hospitalisé", order=1),
        VocabularyValue(code="O", display="Outpatient", definition="Ambulatoire/Externe", order=2),
        VocabularyValue(code="E", display="Emergency", definition="Urgence", order=3)
    ]
    hl7_system.values = hl7_values

    # Système FHIR Encounter Class
    fhir_system = VocabularySystem(
        name="encounter-class-fhir",
        label="Classe de venue (FHIR)",
        uri="http://terminology.hl7.org/CodeSystem/v3-ActCode",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Classes de venue FHIR"
    )

    fhir_values = [
        VocabularyValue(code="IMP", display="Inpatient encounter", definition="Hospitalisation", order=1),
        VocabularyValue(code="AMB", display="Ambulatory", definition="Ambulatoire", order=2),
        VocabularyValue(code="EMER", display="Emergency", definition="Urgence", order=3)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> HL7v2
    mappings = [
        # hospitalise -> I (Inpatient)
        VocabularyMapping(
            source_value=internal_values[0],  # hospitalise
            target_system=hl7_system,
            target_code="I",
            map_type="equivalent"
        ),
        # externe -> O (Outpatient)
        VocabularyMapping(
            source_value=internal_values[1],  # externe
            target_system=hl7_system,
            target_code="O",
            map_type="equivalent"
        ),
        # urgence -> E (Emergency)
        VocabularyMapping(
            source_value=internal_values[2],  # urgence
            target_system=hl7_system,
            target_code="E",
            map_type="equivalent"
        ),
        # Mappings internes -> FHIR
        VocabularyMapping(
            source_value=internal_values[0],  # hospitalise
            target_system=fhir_system,
            target_code="IMP",
            map_type="equivalent"
        ),
        VocabularyMapping(
            source_value=internal_values[1],  # externe
            target_system=fhir_system,
            target_code="AMB",
            map_type="equivalent"
        ),
        VocabularyMapping(
            source_value=internal_values[2],  # urgence
            target_system=fhir_system,
            target_code="EMER",
            map_type="equivalent"
        )
    ]

    # Sauvegarder les mappings dans la session
    for mapping in mappings:
        session.add(mapping)

    return [internal_system, hl7_system, fhir_system]

def create_identity_reliability_vocabularies(session) -> List[VocabularySystem]:
    """Crée les vocabulaires pour la fiabilité d'identité (RNIV)"""

    # Système interne (RNIV France)
    internal_system = VocabularySystem(
        name="identity-reliability-internal",
        label="Fiabilité d'identité (RNIV)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Codes de fiabilité d'identité selon le Référentiel National d'Identification des Personnes"
    )

    internal_values = [
        VocabularyValue(code="VALI", display="Validée", definition="Identité validée (présence INS-A dans annuaire national)", order=1),
        VocabularyValue(code="QUAL", display="Qualifiée", definition="Identité qualifiée (5 traits stricts vérifiés)", order=2),
        VocabularyValue(code="PROV", display="Provisoire", definition="Identité provisoire (en cours de qualification)", order=3),
        VocabularyValue(code="VIDE", display="Fictive", definition="Identité fictive (patient non identifiable)", order=4),
        VocabularyValue(code="DOUTE", display="Douteuse", definition="Identité douteuse (incohérences détectées)", order=5),
        VocabularyValue(code="DOUB", display="Doublon", definition="Doublon détecté (fusion requise)", order=6),
        VocabularyValue(code="FICTI", display="Fictive", definition="Fictive (alias HL7 de VIDE, compatibilité)", order=7)
    ]
    internal_system.values = internal_values

    # Système HL7v2 Table 0445 (Identity Reliability Code)
    hl7_system = VocabularySystem(
        name="identity-reliability-hl7v2",
        label="Fiabilité d'identité (HL7v2 Table 0445)",
        oid="2.16.840.1.113883.12.445",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Table HL7 0445 - Identity Reliability Code"
    )

    hl7_values = [
        VocabularyValue(code="VALI", display="Validated", definition="Identity validated", order=1),
        VocabularyValue(code="QUAL", display="Qualified", definition="Identity qualified", order=2),
        VocabularyValue(code="PROV", display="Provisional", definition="Identity provisional", order=3),
        VocabularyValue(code="VIDE", display="Void", definition="Identity void/fictive", order=4),
        VocabularyValue(code="DOUTE", display="Doubtful", definition="Identity doubtful", order=5),
        VocabularyValue(code="DOUB", display="Duplicate", definition="Duplicate detected", order=6),
        VocabularyValue(code="FICTI", display="Fictive", definition="Fictive identity", order=7)
    ]
    hl7_system.values = hl7_values

    # Système FHIR extensions pour fiabilité d'identité
    fhir_system = VocabularySystem(
        name="identity-reliability-fhir",
        label="Fiabilité d'identité (FHIR)",
        uri="http://hl7.org/fhir/StructureDefinition/patient-identity-reliability",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Extensions FHIR pour la fiabilité d'identité patient"
    )

    fhir_values = [
        VocabularyValue(code="validated", display="Validated", definition="Identity validated", order=1),
        VocabularyValue(code="qualified", display="Qualified", definition="Identity qualified", order=2),
        VocabularyValue(code="provisional", display="Provisional", definition="Identity provisional", order=3),
        VocabularyValue(code="void", display="Void", definition="Identity void", order=4),
        VocabularyValue(code="doubtful", display="Doubtful", definition="Identity doubtful", order=5),
        VocabularyValue(code="duplicate", display="Duplicate", definition="Duplicate detected", order=6),
        VocabularyValue(code="fictive", display="Fictive", definition="Fictive identity", order=7)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> HL7v2
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=hl7_system, target_code="VALI"),  # VALI -> VALI
        VocabularyMapping(source_value=internal_values[1], target_system=hl7_system, target_code="QUAL"),  # QUAL -> QUAL
        VocabularyMapping(source_value=internal_values[2], target_system=hl7_system, target_code="PROV"),  # PROV -> PROV
        VocabularyMapping(source_value=internal_values[3], target_system=hl7_system, target_code="VIDE"),  # VIDE -> VIDE
        VocabularyMapping(source_value=internal_values[4], target_system=hl7_system, target_code="DOUTE"), # DOUTE -> DOUTE
        VocabularyMapping(source_value=internal_values[5], target_system=hl7_system, target_code="DOUB"),  # DOUB -> DOUB
        VocabularyMapping(source_value=internal_values[6], target_system=hl7_system, target_code="FICTI"), # FICTI -> FICTI
        # Mappings internes -> FHIR
        VocabularyMapping(source_value=internal_values[0], target_system=fhir_system, target_code="validated"),   # VALI -> validated
        VocabularyMapping(source_value=internal_values[1], target_system=fhir_system, target_code="qualified"),   # QUAL -> qualified
        VocabularyMapping(source_value=internal_values[2], target_system=fhir_system, target_code="provisional"), # PROV -> provisional
        VocabularyMapping(source_value=internal_values[3], target_system=fhir_system, target_code="void"),        # VIDE -> void
        VocabularyMapping(source_value=internal_values[4], target_system=fhir_system, target_code="doubtful"),    # DOUTE -> doubtful
        VocabularyMapping(source_value=internal_values[5], target_system=fhir_system, target_code="duplicate"),   # DOUB -> duplicate
        VocabularyMapping(source_value=internal_values[6], target_system=fhir_system, target_code="fictive")      # FICTI -> fictive
    ]

    # Sauvegarder les mappings dans la session
    for mapping in mappings:
        session.add(mapping)

    return [internal_system, hl7_system, fhir_system]

def create_ins_type_vocabularies(session) -> List[VocabularySystem]:
    """Crée les vocabulaires pour les types d'Identifiant National de Santé"""

    # Système interne (RNIV France)
    internal_system = VocabularySystem(
        name="ins-type-internal",
        label="Type INS (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types d'Identifiant National de Santé selon RNIV"
    )

    internal_values = [
        VocabularyValue(code="NIR", display="NIR", definition="Numéro d'Inscription au Répertoire (Sécurité Sociale)", order=1),
        VocabularyValue(code="INS-C", display="INS-Calculé", definition="INS Calculé (pour personnes sans NIR)", order=2)
    ]
    internal_system.values = internal_values

    # Système HL7v2 PID-3.5 (Identifier Type Code)
    hl7_system = VocabularySystem(
        name="ins-type-hl7v2",
        label="Type INS (HL7v2 PID-3.5)",
        oid="2.16.840.1.113883.12.203",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Table HL7 0203 - Identifier Type"
    )

    hl7_values = [
        VocabularyValue(code="NIR", display="NIR", definition="Numéro d'Inscription au Répertoire", order=1),
        VocabularyValue(code="INS-C", display="INS-C", definition="INS Calculé", order=2)
    ]
    hl7_system.values = hl7_values

    # Système FHIR identifier.type
    fhir_system = VocabularySystem(
        name="ins-type-fhir",
        label="Type INS (FHIR)",
        uri="http://terminology.hl7.org/CodeSystem/v2-0203",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Types d'identifiant FHIR"
    )

    fhir_values = [
        VocabularyValue(code="NIR", display="NIR", definition="French Social Security Number", order=1),
        VocabularyValue(code="INS-C", display="INS-C", definition="Calculated INS", order=2)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> HL7v2 (identiques pour ce cas)
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=hl7_system, target_code="NIR"),    # NIR -> NIR
        VocabularyMapping(source_value=internal_values[1], target_system=hl7_system, target_code="INS-C"), # INS-C -> INS-C
        # Mappings internes -> FHIR (identiques pour ce cas)
        VocabularyMapping(source_value=internal_values[0], target_system=fhir_system, target_code="NIR"),    # NIR -> NIR
        VocabularyMapping(source_value=internal_values[1], target_system=fhir_system, target_code="INS-C")  # INS-C -> INS-C
    ]

    # Sauvegarder les mappings dans la session
    for mapping in mappings:
        session.add(mapping)

    return [internal_system, hl7_system, fhir_system]

def create_identifier_type_vocabularies(session) -> List[VocabularySystem]:
    """Crée les vocabulaires pour les types d'identifiant"""

    # Système interne (valeurs françaises)
    internal_system = VocabularySystem(
        name="identifier-type-internal",
        label="Type d'identifiant (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types d'identifiant utilisés dans notre modèle"
    )

    internal_values = [
        VocabularyValue(code="IPP", display="IPP", definition="Identifiant Patient Permanent", order=1),
        VocabularyValue(code="NDA", display="NDA", definition="Numéro de Dossier Administratif", order=2),
        VocabularyValue(code="NA", display="NA", definition="Numéro d'Admission", order=3),
        VocabularyValue(code="VN", display="VN", definition="Numéro de Venue", order=4),
        VocabularyValue(code="PI", display="PI", definition="Patient Interne", order=5),
        VocabularyValue(code="PG", display="PG", definition="Patient Global", order=6),
        VocabularyValue(code="SS", display="SS", definition="Sécurité Sociale", order=7),
        VocabularyValue(code="PC", display="PC", definition="Personne à Contacter", order=8),
        VocabularyValue(code="NDP", display="NDP", definition="Numéro Dossier Patient", order=9),
        VocabularyValue(code="MVT", display="MVT", definition="Identifiant de Mouvement", order=10),
        VocabularyValue(code="FINESS", display="FINESS", definition="Numéro FINESS Établissement", order=11)
    ]
    internal_system.values = internal_values

    # Système HL7v2 Table 0203 (Identifier Type)
    hl7_system = VocabularySystem(
        name="identifier-type-hl7v2",
        label="Type d'identifiant (HL7v2 Table 0203)",
        oid="2.16.840.1.113883.12.203",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Table HL7 0203 - Identifier Type"
    )

    hl7_values = [
        VocabularyValue(code="PI", display="Patient internal identifier", definition="Patient internal identifier", order=1),
        VocabularyValue(code="AN", display="Account number", definition="Account number", order=2),
        VocabularyValue(code="VN", display="Visit number", definition="Visit number", order=3),
        VocabularyValue(code="SS", display="Social Security Number", definition="Social Security Number", order=4),
        VocabularyValue(code="PN", display="Person number", definition="Person number", order=5),
        VocabularyValue(code="NDA", display="NDA", definition="Numéro de Dossier Administratif", order=6),
        VocabularyValue(code="IPP", display="IPP", definition="Identifiant Patient Permanent", order=7),
        VocabularyValue(code="FINESS", display="FINESS", definition="FINESS establishment number", order=8)
    ]
    hl7_system.values = hl7_values

    # Système FHIR identifier.type
    fhir_system = VocabularySystem(
        name="identifier-type-fhir",
        label="Type d'identifiant (FHIR)",
        uri="http://terminology.hl7.org/CodeSystem/v2-0203",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Types d'identifiant FHIR"
    )

    fhir_values = [
        VocabularyValue(code="PI", display="Patient internal identifier", definition="Patient internal identifier", order=1),
        VocabularyValue(code="AN", display="Account number", definition="Account number", order=2),
        VocabularyValue(code="VN", display="Visit number", definition="Visit number", order=3),
        VocabularyValue(code="SS", display="Social Security Number", definition="Social Security Number", order=4),
        VocabularyValue(code="PPN", display="Passport number", definition="Passport number", order=5),
        VocabularyValue(code="NDA", display="NDA", definition="Numéro de Dossier Administratif", order=6),
        VocabularyValue(code="IPP", display="IPP", definition="Identifiant Patient Permanent", order=7),
        VocabularyValue(code="FIN", display="Facility ID", definition="Facility identifier", order=8)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> HL7v2
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=hl7_system, target_code="IPP"),     # IPP -> IPP
        VocabularyMapping(source_value=internal_values[1], target_system=hl7_system, target_code="NDA"),     # NDA -> NDA
        VocabularyMapping(source_value=internal_values[2], target_system=hl7_system, target_code="AN"),      # NA -> AN
        VocabularyMapping(source_value=internal_values[3], target_system=hl7_system, target_code="VN"),      # VN -> VN
        VocabularyMapping(source_value=internal_values[4], target_system=hl7_system, target_code="PI"),      # PI -> PI
        VocabularyMapping(source_value=internal_values[5], target_system=hl7_system, target_code="PI"),      # PG -> PI (approximation)
        VocabularyMapping(source_value=internal_values[6], target_system=hl7_system, target_code="SS"),      # SS -> SS
        VocabularyMapping(source_value=internal_values[7], target_system=hl7_system, target_code="PN"),      # PC -> PN
        VocabularyMapping(source_value=internal_values[8], target_system=hl7_system, target_code="PI"),      # NDP -> PI (approximation)
        VocabularyMapping(source_value=internal_values[9], target_system=hl7_system, target_code="VN"),      # MVT -> VN (approximation)
        VocabularyMapping(source_value=internal_values[10], target_system=hl7_system, target_code="FINESS"), # FINESS -> FINESS
        # Mappings internes -> FHIR
        VocabularyMapping(source_value=internal_values[0], target_system=fhir_system, target_code="PI"),      # IPP -> PI (approximation)
        VocabularyMapping(source_value=internal_values[1], target_system=fhir_system, target_code="AN"),      # NDA -> AN (approximation)
        VocabularyMapping(source_value=internal_values[2], target_system=fhir_system, target_code="AN"),      # NA -> AN
        VocabularyMapping(source_value=internal_values[3], target_system=fhir_system, target_code="VN"),      # VN -> VN
        VocabularyMapping(source_value=internal_values[4], target_system=fhir_system, target_code="PI"),      # PI -> PI
        VocabularyMapping(source_value=internal_values[5], target_system=fhir_system, target_code="PI"),      # PG -> PI (approximation)
        VocabularyMapping(source_value=internal_values[6], target_system=fhir_system, target_code="SS"),      # SS -> SS
        VocabularyMapping(source_value=internal_values[7], target_system=fhir_system, target_code="PPN"),     # PC -> PPN (approximation)
        VocabularyMapping(source_value=internal_values[8], target_system=fhir_system, target_code="PI"),      # NDP -> PI (approximation)
        VocabularyMapping(source_value=internal_values[9], target_system=fhir_system, target_code="VN"),      # MVT -> VN (approximation)
        VocabularyMapping(source_value=internal_values[10], target_system=fhir_system, target_code="FIN")     # FINESS -> FIN (approximation)
    ]

    # Sauvegarder les mappings dans la session
    for mapping in mappings:
        session.add(mapping)

    return [internal_system, hl7_system, fhir_system]

def create_scenario_type_vocabularies() -> List[VocabularySystem]:
    """Crée les vocabulaires pour les types de scénario"""

    # Système interne (valeurs françaises)
    internal_system = VocabularySystem(
        name="scenario-type-internal",
        label="Type de scénario (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types de scénarios cliniques utilisés dans notre modèle"
    )

    internal_values = [
        VocabularyValue(code="ADMISSION", display="Admission", definition="Admission d'un patient", order=1),
        VocabularyValue(code="TRANSFERT", display="Transfert", definition="Transfert de patient", order=2),
        VocabularyValue(code="SORTIE", display="Sortie", definition="Sortie de patient", order=3),
        VocabularyValue(code="MISE_A_JOUR", display="Mise à jour", definition="Mise à jour d'informations", order=4),
        VocabularyValue(code="ADMISSION_AVEC_TRANSFERT", display="Admission avec transfert", definition="Admission suivie d'un transfert", order=5),
        VocabularyValue(code="ADMISSION_AVEC_SORTIE", display="Admission avec sortie", definition="Admission suivie d'une sortie", order=6),
        VocabularyValue(code="FUSION_PATIENTS", display="Fusion patients", definition="Fusion de dossiers patients", order=7),
        VocabularyValue(code="ANNULATION_ADMISSION", display="Annulation admission", definition="Annulation d'admission", order=8),
        VocabularyValue(code="AUTRE", display="Autre", definition="Autre type de scénario", order=9)
    ]
    internal_system.values = internal_values

    # Système IHE PAM (trigger events)
    ihe_system = VocabularySystem(
        name="scenario-type-ihe-pam",
        label="Type de scénario (IHE PAM)",
        uri="urn:ihe:pam:scenario",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Types de scénarios selon IHE PAM France"
    )

    ihe_values = [
        VocabularyValue(code="ADMISSION", display="Admission", definition="Patient admission", order=1),
        VocabularyValue(code="TRANSFER", display="Transfer", definition="Patient transfer", order=2),
        VocabularyValue(code="DISCHARGE", display="Discharge", definition="Patient discharge", order=3),
        VocabularyValue(code="UPDATE", display="Update", definition="Information update", order=4),
        VocabularyValue(code="MERGE", display="Merge", definition="Patient merge", order=5),
        VocabularyValue(code="CANCEL", display="Cancel", definition="Cancel admission", order=6)
    ]
    ihe_system.values = ihe_values

    # Système HL7v2 (trigger events)
    hl7_system = VocabularySystem(
        name="scenario-type-hl7v2",
        label="Type de scénario (HL7v2)",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Événements déclencheurs HL7v2"
    )

    hl7_values = [
        VocabularyValue(code="A01", display="A01 - Admit/visit notification", definition="Admission", order=1),
        VocabularyValue(code="A02", display="A02 - Transfer a patient", definition="Transfert", order=2),
        VocabularyValue(code="A03", display="A03 - Discharge/end visit", definition="Sortie", order=3),
        VocabularyValue(code="A08", display="A08 - Update patient information", definition="Mise à jour", order=4),
        VocabularyValue(code="A40", display="A40 - Merge patient information", definition="Fusion", order=5),
        VocabularyValue(code="A11", display="A11 - Cancel admit/visit notification", definition="Annulation", order=6)
    ]
    hl7_system.values = hl7_values

    # Mappings internes -> IHE PAM
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=ihe_system, target_code="ADMISSION"),    # ADMISSION -> ADMISSION
        VocabularyMapping(source_value=internal_values[1], target_system=ihe_system, target_code="TRANSFER"),     # TRANSFERT -> TRANSFER
        VocabularyMapping(source_value=internal_values[2], target_system=ihe_system, target_code="DISCHARGE"),    # SORTIE -> DISCHARGE
        VocabularyMapping(source_value=internal_values[3], target_system=ihe_system, target_code="UPDATE"),       # MISE_A_JOUR -> UPDATE
        VocabularyMapping(source_value=internal_values[6], target_system=ihe_system, target_code="MERGE"),        # FUSION_PATIENTS -> MERGE
        VocabularyMapping(source_value=internal_values[7], target_system=ihe_system, target_code="CANCEL")        # ANNULATION_ADMISSION -> CANCEL
    ]

    return [internal_system, ihe_system, hl7_system]

def create_action_type_vocabularies() -> List[VocabularySystem]:
    """Crée les vocabulaires pour les types d'action"""

    # Système interne (valeurs françaises)
    internal_system = VocabularySystem(
        name="action-type-internal",
        label="Type d'action (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types d'actions dans les workflows"
    )

    internal_values = [
        VocabularyValue(code="CREER_PATIENT", display="Créer patient", definition="Créer un nouveau patient", order=1),
        VocabularyValue(code="METTRE_A_JOUR_PATIENT", display="Mettre à jour patient", definition="Modifier les informations patient", order=2),
        VocabularyValue(code="FUSIONNER_PATIENTS", display="Fusionner patients", definition="Fusionner des dossiers patients", order=3),
        VocabularyValue(code="CREER_DOSSIER", display="Créer dossier", definition="Créer un nouveau dossier", order=4),
        VocabularyValue(code="METTRE_A_JOUR_DOSSIER", display="Mettre à jour dossier", definition="Modifier les informations dossier", order=5),
        VocabularyValue(code="CLOTURER_DOSSIER", display="Clôturer dossier", definition="Fermer un dossier", order=6),
        VocabularyValue(code="ANNULER_DOSSIER", display="Annuler dossier", definition="Annuler un dossier", order=7),
        VocabularyValue(code="CREER_VENUE", display="Créer venue", definition="Créer une nouvelle venue", order=8),
        VocabularyValue(code="METTRE_A_JOUR_VENUE", display="Mettre à jour venue", definition="Modifier les informations venue", order=9),
        VocabularyValue(code="TERMINER_VENUE", display="Terminer venue", definition="Terminer une venue", order=10),
        VocabularyValue(code="CREER_MOUVEMENT", display="Créer mouvement", definition="Créer un nouveau mouvement", order=11),
        VocabularyValue(code="ANNULER_MOUVEMENT", display="Annuler mouvement", definition="Annuler un mouvement", order=12),
        VocabularyValue(code="EMETTRE_HL7", display="Émettre HL7", definition="Générer un message HL7", order=13),
        VocabularyValue(code="EMETTRE_FHIR", display="Émettre FHIR", definition="Générer une ressource FHIR", order=14)
    ]
    internal_system.values = internal_values

    # Système IHE PAM (action types)
    ihe_system = VocabularySystem(
        name="action-type-ihe-pam",
        label="Type d'action (IHE PAM)",
        uri="urn:ihe:pam:action",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Types d'actions selon IHE PAM France"
    )

    ihe_values = [
        VocabularyValue(code="CREATE_PATIENT", display="Create patient", definition="Create new patient", order=1),
        VocabularyValue(code="UPDATE_PATIENT", display="Update patient", definition="Update patient information", order=2),
        VocabularyValue(code="MERGE_PATIENTS", display="Merge patients", definition="Merge patient records", order=3),
        VocabularyValue(code="CREATE_ENCOUNTER", display="Create encounter", definition="Create new encounter", order=4),
        VocabularyValue(code="UPDATE_ENCOUNTER", display="Update encounter", definition="Update encounter information", order=5),
        VocabularyValue(code="END_ENCOUNTER", display="End encounter", definition="End encounter", order=6),
        VocabularyValue(code="CREATE_MOVEMENT", display="Create movement", definition="Create new movement", order=7),
        VocabularyValue(code="EMIT_HL7", display="Emit HL7", definition="Generate HL7 message", order=8),
        VocabularyValue(code="EMIT_FHIR", display="Emit FHIR", definition="Generate FHIR resource", order=9)
    ]
    ihe_system.values = ihe_values

    # Mappings internes -> IHE PAM
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=ihe_system, target_code="CREATE_PATIENT"),    # CREER_PATIENT -> CREATE_PATIENT
        VocabularyMapping(source_value=internal_values[1], target_system=ihe_system, target_code="UPDATE_PATIENT"),    # METTRE_A_JOUR_PATIENT -> UPDATE_PATIENT
        VocabularyMapping(source_value=internal_values[2], target_system=ihe_system, target_code="MERGE_PATIENTS"),    # FUSIONNER_PATIENTS -> MERGE_PATIENTS
        VocabularyMapping(source_value=internal_values[3], target_system=ihe_system, target_code="CREATE_ENCOUNTER"),  # CREER_DOSSIER -> CREATE_ENCOUNTER
        VocabularyMapping(source_value=internal_values[4], target_system=ihe_system, target_code="UPDATE_ENCOUNTER"),  # METTRE_A_JOUR_DOSSIER -> UPDATE_ENCOUNTER
        VocabularyMapping(source_value=internal_values[5], target_system=ihe_system, target_code="END_ENCOUNTER"),     # CLOTURER_DOSSIER -> END_ENCOUNTER
        VocabularyMapping(source_value=internal_values[7], target_system=ihe_system, target_code="CREATE_ENCOUNTER"),  # CREER_VENUE -> CREATE_ENCOUNTER
        VocabularyMapping(source_value=internal_values[8], target_system=ihe_system, target_code="UPDATE_ENCOUNTER"),  # METTRE_A_JOUR_VENUE -> UPDATE_ENCOUNTER
        VocabularyMapping(source_value=internal_values[9], target_system=ihe_system, target_code="END_ENCOUNTER"),     # TERMINER_VENUE -> END_ENCOUNTER
        VocabularyMapping(source_value=internal_values[10], target_system=ihe_system, target_code="CREATE_MOVEMENT"),  # CREER_MOUVEMENT -> CREATE_MOVEMENT
        VocabularyMapping(source_value=internal_values[12], target_system=ihe_system, target_code="EMIT_HL7"),         # EMETTRE_HL7 -> EMIT_HL7
        VocabularyMapping(source_value=internal_values[13], target_system=ihe_system, target_code="EMIT_FHIR")         # EMETTRE_FHIR -> EMIT_FHIR
    ]

    return [internal_system, ihe_system]

def create_execution_status_vocabularies() -> List[VocabularySystem]:
    """Crée les vocabulaires pour les statuts d'exécution"""

    # Système interne (valeurs françaises)
    internal_system = VocabularySystem(
        name="execution-status-internal",
        label="Statut d'exécution (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Statuts d'exécution des workflows"
    )

    internal_values = [
        VocabularyValue(code="EN_ATTENTE", display="En attente", definition="Exécution en attente", order=1),
        VocabularyValue(code="EN_COURS", display="En cours", definition="Exécution en cours", order=2),
        VocabularyValue(code="TERMINE", display="Terminé", definition="Exécution terminée avec succès", order=3),
        VocabularyValue(code="ECHEC", display="Échec", definition="Exécution terminée en erreur", order=4),
        VocabularyValue(code="ANNULE", display="Annulé", definition="Exécution annulée", order=5)
    ]
    internal_system.values = internal_values

    # Système HL7v2 (processing status)
    hl7_system = VocabularySystem(
        name="execution-status-hl7v2",
        label="Statut d'exécution (HL7v2)",
        system_type=VocabularySystemType.HL7V2,
        is_user_defined=False,
        description="Statuts de traitement HL7v2"
    )

    hl7_values = [
        VocabularyValue(code="P", display="Pending", definition="Pending", order=1),
        VocabularyValue(code="I", display="In Progress", definition="In Progress", order=2),
        VocabularyValue(code="C", display="Completed", definition="Completed", order=3),
        VocabularyValue(code="F", display="Failed", definition="Failed", order=4),
        VocabularyValue(code="X", display="Cancelled", definition="Cancelled", order=5)
    ]
    hl7_system.values = hl7_values

    # Système FHIR Task.status
    fhir_system = VocabularySystem(
        name="execution-status-fhir",
        label="Statut d'exécution (FHIR)",
        uri="http://hl7.org/fhir/task-status",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Statuts de tâche FHIR"
    )

    fhir_values = [
        VocabularyValue(code="ready", display="Ready", definition="Ready for execution", order=1),
        VocabularyValue(code="in-progress", display="In Progress", definition="Execution in progress", order=2),
        VocabularyValue(code="completed", display="Completed", definition="Successfully completed", order=3),
        VocabularyValue(code="failed", display="Failed", definition="Failed", order=4),
        VocabularyValue(code="cancelled", display="Cancelled", definition="Cancelled", order=5)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> HL7v2
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=hl7_system, target_code="P"),  # EN_ATTENTE -> P
        VocabularyMapping(source_value=internal_values[1], target_system=hl7_system, target_code="I"),  # EN_COURS -> I
        VocabularyMapping(source_value=internal_values[2], target_system=hl7_system, target_code="C"),  # TERMINE -> C
        VocabularyMapping(source_value=internal_values[3], target_system=hl7_system, target_code="F"),  # ECHEC -> F
        VocabularyMapping(source_value=internal_values[4], target_system=hl7_system, target_code="X")   # ANNULE -> X
    ]

    return [internal_system, hl7_system, fhir_system]

def create_entity_type_vocabularies() -> List[VocabularySystem]:
    """Crée les vocabulaires pour les types d'entité"""

    # Système interne (valeurs françaises)
    internal_system = VocabularySystem(
        name="entity-type-internal",
        label="Type d'entité (interne)",
        system_type=VocabularySystemType.LOCAL,
        is_user_defined=False,
        description="Types d'entités dans le système"
    )

    internal_values = [
        VocabularyValue(code="PATIENT", display="Patient", definition="Entité patient", order=1),
        VocabularyValue(code="DOSSIER", display="Dossier", definition="Entité dossier", order=2),
        VocabularyValue(code="VENUE", display="Venue", definition="Entité venue", order=3),
        VocabularyValue(code="MOUVEMENT", display="Mouvement", definition="Entité mouvement", order=4),
        VocabularyValue(code="MESSAGE_HL7", display="Message HL7", definition="Message HL7", order=5),
        VocabularyValue(code="RESSOURCE_FHIR", display="Ressource FHIR", definition="Ressource FHIR", order=6)
    ]
    internal_system.values = internal_values

    # Système FHIR ResourceType
    fhir_system = VocabularySystem(
        name="entity-type-fhir",
        label="Type d'entité (FHIR)",
        uri="http://hl7.org/fhir/resource-types",
        system_type=VocabularySystemType.FHIR,
        is_user_defined=False,
        description="Types de ressources FHIR"
    )

    fhir_values = [
        VocabularyValue(code="Patient", display="Patient", definition="Patient resource", order=1),
        VocabularyValue(code="Encounter", display="Encounter", definition="Encounter resource", order=2),
        VocabularyValue(code="EpisodeOfCare", display="EpisodeOfCare", definition="EpisodeOfCare resource", order=3),
        VocabularyValue(code="Account", display="Account", definition="Account resource", order=4),
        VocabularyValue(code="MessageHeader", display="MessageHeader", definition="MessageHeader resource", order=5),
        VocabularyValue(code="Bundle", display="Bundle", definition="Bundle resource", order=6)
    ]
    fhir_system.values = fhir_values

    # Mappings internes -> FHIR ResourceType
    mappings = [
        VocabularyMapping(source_value=internal_values[0], target_system=fhir_system, target_code="Patient"),        # PATIENT -> Patient
        VocabularyMapping(source_value=internal_values[1], target_system=fhir_system, target_code="EpisodeOfCare"), # DOSSIER -> EpisodeOfCare
        VocabularyMapping(source_value=internal_values[2], target_system=fhir_system, target_code="Encounter"),      # VENUE -> Encounter
        VocabularyMapping(source_value=internal_values[3], target_system=fhir_system, target_code="Account"),        # MOUVEMENT -> Account
        VocabularyMapping(source_value=internal_values[4], target_system=fhir_system, target_code="MessageHeader"), # MESSAGE_HL7 -> MessageHeader
        VocabularyMapping(source_value=internal_values[5], target_system=fhir_system, target_code="Bundle")          # RESSOURCE_FHIR -> Bundle
    ]

    return [internal_system, fhir_system]

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
    mappings = [
        VocabularyMapping(source_value=fhir_values[0], target_system=hl7_system, target_code="P"),  # planned -> P
        VocabularyMapping(source_value=fhir_values[1], target_system=hl7_system, target_code="A"),  # arrived -> A
        VocabularyMapping(source_value=fhir_values[3], target_system=hl7_system, target_code="H"),  # in-progress -> H
        VocabularyMapping(source_value=fhir_values[4], target_system=hl7_system, target_code="L"),  # onleave -> L
        VocabularyMapping(source_value=fhir_values[5], target_system=hl7_system, target_code="C"),  # finished -> C
        VocabularyMapping(source_value=fhir_values[6], target_system=hl7_system, target_code="X")   # cancelled -> X
    ]
    
    return [fhir_system, hl7_system]

def init_vocabularies(session):
    """Initialise toutes les listes de valeurs standards"""
    
    all_systems = []
    
    # Vocabulaires de base
    all_systems.extend(create_administrative_gender())
    all_systems.extend(create_encounter_status())
    all_systems.extend(create_dossier_type_vocabularies(session))
    all_systems.extend(create_identity_reliability_vocabularies(session))
    all_systems.extend(create_ins_type_vocabularies(session))
    all_systems.extend(create_identifier_type_vocabularies(session))
    all_systems.extend(create_scenario_type_vocabularies())
    all_systems.extend(create_action_type_vocabularies())
    all_systems.extend(create_execution_status_vocabularies())
    all_systems.extend(create_entity_type_vocabularies())
    
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
    
    # Sauvegarder tous les systèmes et leurs valeurs
    for system in all_systems:
        session.add(system)
    
    session.commit()
    
    # Initialiser les mappings entre vocabulaires
    # REMARQUE: doit être fait après la création des systèmes car utilise leurs IDs
    init_vocabulary_mappings(session)
