"""Construction des messages HPRIM sortants pour les actes de cotation.

Ce module ne choisit ni le transport ni les reprises. Il transforme un acte
persisté en XML HPRIM afin que l'orchestrateur multi-protocole puisse déléguer
la livraison à l'outbox durable.
"""

from datetime import datetime
from decimal import Decimal
import logging
from typing import Literal

from sqlmodel import Session

from app.hprim_models import (
    HprimActeCCAM,
    HprimActeLPP,
    HprimActeNGAP,
    HprimActeUCD,
    HprimAction,
    HprimCodeLPP,
    HprimEnteteMessage,
    HprimLPP,
    HprimMessage,
    HprimMessageType,
    HprimModificateur,
    HprimPatient,
    HprimProfessionnel,
    HprimUCD,
)
from app.models import CCAMAct, Dossier, LPPAct, NGAPAct, Patient, UCDAct
from app.models_practitioners import MedecinResponsable
from app.services.hprim.hprim_xml import HprimXmlService
from app.utils.booleans import as_bool


HprimEntityType = Literal["ccam_act", "ngap_act", "ucd_act", "lpp_act"]
logger = logging.getLogger(__name__)


def is_hprim_enabled(endpoint, entity_type: HprimEntityType) -> bool:
    """Indique si un endpoint est abonné au type d'acte demandé."""
    return bool(getattr(endpoint, f"emit_hprim_{entity_type.removesuffix('_act')}", False))


def _professional(medecin: MedecinResponsable | None) -> HprimProfessionnel:
    if medecin:
        return HprimProfessionnel(
            nom=medecin.family_name or "INCONNU",
            prenom=medecin.given_name or "",
            numero_rpps=medecin.rpps,
            numero_adeli=medecin.adeli,
            specialite=medecin.specialty,
        )
    return HprimProfessionnel(nom="INCONNU", prenom="")


def _normalize_sex(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).lower()
    if normalized in {"m", "male", "masculin"}:
        return "M"
    if normalized in {"f", "female", "feminin", "féminin"}:
        return "F"
    return "U"


def _patient(patient: Patient) -> HprimPatient:
    identifier = (
        getattr(patient, "identifier", None)
        or getattr(patient, "nir", None)
        or getattr(patient, "ins_c", None)
        or str(patient.id)
    )
    key = "IPP" if getattr(patient, "identifier", None) else (
        "INS" if getattr(patient, "nir", None) or getattr(patient, "ins_c", None) else "ID"
    )
    birth_date = getattr(patient, "birth_date", None) or getattr(patient, "date_naissance", None)
    return HprimPatient(
        identifiant_id=str(identifier),
        identifiant_clef=key,
        nom=getattr(patient, "family", None) or getattr(patient, "nom", None) or "INCONNU",
        prenom=getattr(patient, "given", None) or getattr(patient, "prenom", None) or "",
        date_naissance=birth_date.isoformat() if hasattr(birth_date, "isoformat") else None,
        sexe=_normalize_sex(getattr(patient, "gender", None) or getattr(patient, "sexe", None)),
    )


def _resolve_professional(entity, entity_type: HprimEntityType, session: Session):
    if entity_type == "ccam_act":
        medecin = getattr(entity, "executant", None) or getattr(entity, "prescripteur", None)
        ids = (getattr(entity, "executant_id", None), getattr(entity, "prescripteur_id", None))
    elif entity_type == "ngap_act":
        medecin = getattr(entity, "prestataire", None)
        ids = (getattr(entity, "prestataire_id", None),)
    elif entity_type == "ucd_act":
        medecin = getattr(entity, "prestataire", None) or getattr(entity, "prescripteur", None)
        ids = (getattr(entity, "prestataire_id", None) or getattr(entity, "prescripteur_id", None),)
    else:
        medecin = getattr(entity, "prestataire", None)
        ids = (getattr(entity, "prestataire_id", None),)
    for medecin_id in ids:
        if medecin is None and medecin_id:
            medecin = session.get(MedecinResponsable, medecin_id)
    return _professional(medecin)


def generate_hprim_xml(
    entity,
    entity_type: HprimEntityType,
    session: Session,
    endpoint,
    operation: str,
) -> tuple[str, str] | None:
    """Construit l'XML et son identifiant de corrélation, ou ``None`` sans dossier/patient."""
    dossier = session.get(Dossier, entity.dossier_id)
    if not dossier:
        return None
    patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None
    if not patient:
        return None

    now = datetime.now()
    header = HprimEnteteMessage(
        message_id=f"COTATION-{entity.id}-{int(now.timestamp())}",
        date_emission=now,
        emetteur_id=getattr(endpoint, "sending_app", None) or "MEDBRIDGE",
        emetteur_nom=getattr(endpoint, "sending_facility", None) or "MedData Bridge",
        destinataire_id=getattr(endpoint, "receiving_app", None) or "REMOTE",
        destinataire_nom=getattr(endpoint, "receiving_facility", None) or "Remote System",
        message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES,
    )
    actor = _resolve_professional(entity, entity_type, session)
    message = HprimMessage(
        entete=header,
        patient=_patient(patient),
        acteur=actor,
        version="2.4",
        acquittement_attendu=True,
        identifiant_attendu=True,
        realise=True,
        interrogation=False,
    )
    action = HprimAction.CREATION if operation == "insert" else HprimAction.MODIFICATION
    if entity_type == "ccam_act" and isinstance(entity, CCAMAct):
        modifiers = [HprimModificateur(code=code.strip()) for code in (entity.modificateurs or "").split(",") if code.strip()]
        message.actes_ccam = [HprimActeCCAM(
            identifiant=str(getattr(entity, "identifiant_acte", None) or f"CCAM-{entity.id}"),
            code_acte=entity.code_acte, code_activite=entity.code_activite, code_phase=entity.code_phase,
            execute_date=entity.execute_date, executant=actor, modificateurs=modifiers,
            quantite=entity.quantite or 1, execute_heure=getattr(entity, "execute_heure", None), action=action,
            facturable=entity.facturable if hasattr(entity, "facturable") else True,
            valide=entity.valide if hasattr(entity, "valide") else False, facture=as_bool(getattr(entity, "facture", False)),
        )]
    elif entity_type == "ngap_act" and isinstance(entity, NGAPAct):
        message.actes_ngap = [HprimActeNGAP(
            identifiant=str(getattr(entity, "identifiant_acte", None) or f"NGAP-{entity.id}"),
            lettre_cle=entity.lettre_cle, coefficient=Decimal(str(entity.coefficient)), execute_date=entity.execute_date,
            prestataire=actor, denombrement=entity.denombrement or 1, execute_heure=getattr(entity, "execute_heure", None),
            position_dentaire=getattr(entity, "position_dentaire", None), action=action,
            facturable=entity.facturable if hasattr(entity, "facturable") else True,
            valide=entity.valide if hasattr(entity, "valide") else False, facture=as_bool(getattr(entity, "facture", False)),
        )]
    elif entity_type == "ucd_act" and isinstance(entity, UCDAct):
        quantity, unit_price = Decimal(str(entity.quantite or 1)), Decimal(str(entity.montant_unitaire_facture_ttc or 0))
        message.actes_ucd = HprimActeUCD(identifiant=str(getattr(entity, "identifiant_acte", None) or f"UCD-{entity.id}"), ucds=[HprimUCD(
            code=entity.code_ucd, designation=entity.denomination_libelle or entity.code_ucd, quantite=quantity,
            prix_unitaire=unit_price, montant_total=unit_price * quantity,
        )])
    elif entity_type == "lpp_act" and isinstance(entity, LPPAct):
        if not entity.code_lpp:
            raise ValueError("Un code LPP est requis pour l'émission HPRIM")
        quantity, unit_price = entity.quantite or 1, Decimal(str(entity.montant_unitaire_facture_ttc or 0))
        message.actes_lpp = HprimActeLPP(identifiant=str(getattr(entity, "identifiant_acte", None) or f"LPP-{entity.id}"), lpps=[HprimLPP(
            code=HprimCodeLPP(code=entity.code_lpp), prix_unitaire=unit_price, montant_total=unit_price * quantity,
            libelle=entity.denomination_libelle, quantite=quantity,
        )])
    else:
        raise ValueError(f"Type d'acte HPRIM incompatible: {entity_type}")
    return HprimXmlService().generate_xml(message), header.message_id


def emit_hprim_act(
    session: Session,
    *,
    entity: object,
    entity_type: HprimEntityType,
    endpoint: object,
    operation: str,
    correlation_id: str | None,
):
    """Prépare une cotation HPRIM et la remet à l'outbox durable.

    La livraison fichier, FTP ou HTTP est traitée ultérieurement par le worker;
    l'orchestrateur multi-protocole ne garde donc que le routage de l'événement.
    """
    if not is_hprim_enabled(endpoint, entity_type):
        logger.debug("[HPRIM] Endpoint %s not configured for %s", endpoint.id, entity_type)
        return None

    generated = generate_hprim_xml(entity, entity_type, session, endpoint, operation)
    if generated is None:
        logger.error("[HPRIM] Missing dossier or patient for act %s", getattr(entity, "id", "unknown"))
        return None

    from app.services.hprim_delivery import queue_hprim_delivery

    hprim_xml, message_id = generated
    delivery = queue_hprim_delivery(
        session,
        xml_content=hprim_xml,
        message_id=correlation_id or message_id,
        message_type=HprimMessageType.EVENEMENTS_SERVEUR_ACTES.value,
        endpoint_id=endpoint.id,
    )
    session.commit()
    if delivery is not None:
        logger.info(
            "[HPRIM] Queued %s emission for endpoint %s (outbox #%s)",
            entity_type,
            endpoint.id,
            delivery.outbox.id,
        )
        return delivery.source_log
    return None
