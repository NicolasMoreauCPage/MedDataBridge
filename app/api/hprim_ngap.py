# app/api/hprim_ngap.py
"""
API endpoints pour la gestion des actes NGAP HPRIM
Émission, réception et gestion des actes infirmiers
"""

import logging
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlmodel import select

from app.db import get_session
from app.models.hprim_models import HprimNGAPAct as StoredHprimNGAPAct, HprimMessage as StoredHprimMessage
from app.hprim_models import (
    HprimActeNGAP, HprimPatient, HprimProfessionnel,
    HprimMessage, HprimMessageType, HprimAction, HprimContexteDossier
)
from app.services.hprim import HprimService, HprimValidationError
from app.api.hprim_ccam import (
    PatientInfo, MedecinInfo, VenueInfo, ReceptionRequest,
    hprim_service
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hprim/actes/ngap", tags=["HPRIM NGAP"])


# Modèles Pydantic pour les requêtes/réponses API
class ActeNGAPRequest(BaseModel):
    """Requête pour créer un acte NGAP"""
    lettre_cle: str = Field(..., description="Lettre-clé NGAP (A-Z)")
    coefficient: float = Field(..., description="Coefficient", gt=0)
    execute_date: datetime = Field(..., description="Date d'exécution")
    denombrement: Optional[int] = Field(None, description="Dénombrement")
    position_dentaire: Optional[str] = Field(None, description="Position dentaire (ex: 11, 12, 21-28)")
    execute_heure: Optional[str] = Field(None, description="Heure d'exécution")
    numero_seance: Optional[int] = Field(None, description="Numéro de séance")
    nabms: List[int] = Field(default_factory=list, description="NABM (Nomenclature des Actes Bucco-dentaires)")
    minor_major: Optional[str] = Field(None, description="Mineur/Majeur")
    montant: Optional[float] = Field(None, description="Montant en euros")
    commentaire: Optional[str] = Field(None, description="Commentaire")
    bhn_phns: Optional[Dict[str, Any]] = Field(None, description="BHN/PHNS")

class NGAPInfo(BaseModel):
    """Informations NGAP pour HPRIM"""
    lettre_cle: str = Field(..., description="Lettre-clé")
    coefficient: float = Field(..., description="Coefficient")
    position_dentaire: Optional[str] = Field(None, description="Position dentaire")


class EmissionNGAPRequest(BaseModel):
    """Requête d'émission d'actes NGAP"""
    emetteur_id: str = Field(..., description="ID émetteur (FINESS)")
    emetteur_nom: str = Field(..., description="Nom émetteur")
    destinataire_id: str = Field(..., description="ID destinataire (FINESS)")
    destinataire_nom: str = Field(..., description="Nom destinataire")
    patient: PatientInfo = Field(..., description="Informations patient")
    acteur: MedecinInfo = Field(..., description="Professionnel acteur")
    venue: Optional[VenueInfo] = Field(None, description="Informations de venue")
    actes: List[ActeNGAPRequest] = Field(..., description="Liste des actes NGAP")
    dossier_id: Optional[str] = Field(None, description="ID du dossier médical")
    message_id: Optional[str] = Field(None, description="ID du message (auto-généré)")


class ActeNGAPResponse(BaseModel):
    """Réponse pour un acte NGAP"""
    id: str
    lettre_cle: str
    coefficient: float
    execute_date: datetime
    denombrement: Optional[int]
    position_dentaire: Optional[str]
    execute_heure: Optional[str]
    numero_seance: Optional[int]
    nabms: List[int]
    minor_major: Optional[str]
    montant: Optional[float]
    commentaire: Optional[str]
    action: str
    facturable: bool
    valide: bool
    facture: bool

class MessageNGAPResponse(BaseModel):
    """Réponse pour un message NGAP"""
    message_id: str
    type_message: str
    xml_content: str
    xml_size: int
    actes_count: int
    validation_errors: List[Dict[str, Any]]
    created_at: datetime
    dossier_id: Optional[str] = None

class ReceptionNGAPResponse(BaseModel):
    succes: bool
    message_id: Optional[str]
    actes_recus: List[ActeNGAPResponse] = Field(default_factory=list)
    erreurs_validation: List[Dict[str, Any]] = Field(default_factory=list)
    erreurs_traitement: List[str] = Field(default_factory=list)


def _split_nabms(raw_value: str) -> List[int]:
    if not raw_value:
        return []
    values = []
    for item in raw_value.split(","):
        item = item.strip()
        if item:
            try:
                values.append(int(item))
            except ValueError:
                continue
    return values


def _join_nabms(values: List[int]) -> str:
    return ",".join(str(value) for value in values)


def _serialize_validation_errors(errors: List[HprimValidationError]) -> str:
    return json.dumps([
        {"code": err.code, "message": err.message, "field": err.field}
        for err in errors
    ], ensure_ascii=False)


def _make_ngap_response(record: StoredHprimNGAPAct) -> ActeNGAPResponse:
    return ActeNGAPResponse(
        id=record.id,
        lettre_cle=record.lettre_cle,
        coefficient=record.coefficient,
        execute_date=record.execute_date,
        denombrement=record.denombrement,
        position_dentaire=record.position_dentaire,
        execute_heure=record.execute_heure,
        numero_seance=record.numero_seance,
        nabms=_split_nabms(record.nabms),
        minor_major=record.minor_major,
        montant=record.montant,
        commentaire=record.commentaire,
        action=record.action,
        facturable=record.facturable,
        valide=record.valide,
        facture=record.facture,
    )


def _persist_message(
    db: Session,
    *,
    message_id: str,
    type_message: str,
    direction: str,
    status: str,
    xml_content: str,
    patient_id: Optional[str] = None,
    emetteur_id: Optional[str] = None,
    destinataire_id: Optional[str] = None,
    validation_errors: Optional[List[HprimValidationError]] = None,
    source: Optional[str] = None,
) -> StoredHprimMessage:
    stored = db.get(StoredHprimMessage, message_id)
    if not stored:
        stored = StoredHprimMessage(message_id=message_id, type_message=type_message, direction=direction)

    stored.type_message = type_message
    stored.direction = direction
    stored.status = status
    stored.patient_id = patient_id
    stored.emetteur_id = emetteur_id
    stored.destinataire_id = destinataire_id
    stored.filename = f"{message_id}.xml"
    stored.source = source
    stored.xml_content = xml_content
    stored.xml_size = len(xml_content)
    stored.validation_errors = _serialize_validation_errors(validation_errors or []) if validation_errors else None
    stored.updated_at = datetime.utcnow()
    db.add(stored)
    return stored


def _persist_ngap_record(
    db: Session,
    *,
    acte_id: str,
    patient_id: Optional[str],
    message_id: Optional[str],
    lettre_cle: str,
    coefficient: float,
    execute_date: datetime,
    denombrement: Optional[int],
    position_dentaire: Optional[str],
    execute_heure: Optional[str],
    numero_seance: Optional[int],
    nabms: List[int],
    minor_major: Optional[str],
    montant: Optional[float],
    commentaire: Optional[str],
    action: str,
    facturable: bool,
    valide: bool,
    facture: bool,
    deleted: bool = False,
) -> StoredHprimNGAPAct:
    stored = db.get(StoredHprimNGAPAct, acte_id)
    if not stored:
        stored = StoredHprimNGAPAct(id=acte_id)
        stored.created_at = datetime.utcnow()

    stored.patient_id = patient_id
    stored.message_id = message_id
    stored.lettre_cle = lettre_cle
    stored.coefficient = coefficient
    stored.execute_date = execute_date
    stored.denombrement = denombrement
    stored.position_dentaire = position_dentaire
    stored.execute_heure = execute_heure
    stored.numero_seance = numero_seance
    stored.nabms = _join_nabms(nabms)
    stored.minor_major = minor_major
    stored.montant = montant
    stored.commentaire = commentaire
    stored.action = action
    stored.facturable = facturable
    stored.valide = valide
    stored.facture = facture
    stored.deleted = deleted
    stored.updated_at = datetime.utcnow()
    db.add(stored)
    return stored


@router.post("", response_model=ActeNGAPResponse)
async def creer_acte_ngap(
    acte: ActeNGAPRequest,
    patient_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    try:
        acte_id = str(uuid.uuid4())
        stored = _persist_ngap_record(
            db,
            acte_id=acte_id,
            patient_id=patient_id,
            message_id=None,
            lettre_cle=acte.lettre_cle,
            coefficient=acte.coefficient,
            execute_date=acte.execute_date,
            denombrement=acte.denombrement,
            position_dentaire=acte.position_dentaire,
            execute_heure=acte.execute_heure,
            numero_seance=acte.numero_seance,
            nabms=acte.nabms,
            minor_major=acte.minor_major,
            montant=acte.montant,
            commentaire=acte.commentaire,
            action=HprimAction.CREATION.value,
            facturable=True,
            valide=False,
            facture=False,
        )
        db.commit()
        db.refresh(stored)
        return _make_ngap_response(stored)
    except Exception as e:
        logger.error(f"Erreur création acte NGAP: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/emission", response_model=MessageNGAPResponse)
async def emettre_actes_ngap(
    request: EmissionNGAPRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Émettre des actes NGAP vers un destinataire HPRIM

    Cette endpoint permet d'envoyer des actes infirmiers à un système partenaire
    via le protocole HPRIM XML.
    """
    try:
        logger.info(f"Émission actes NGAP: {len(request.actes)} actes vers {request.destinataire_id}")

        # Convertir les données de requête en objets HPRIM
        from app.hprim_models import (
            HprimIdentifiantAdministrationPatient, HprimNumeroIdentifiantSante,
            HprimNumeroIdentifiantPatients, HprimNumeroIdentifiantPatient,
            HprimAutoriteAffectation, AutoriteAffectation, HprimVenue,
            HprimEntiteJuridique
        )

        # Créer les identifiants patient si fournis
        identifiant_admin_patient = None
        if request.patient.numero_identifiant_sante or request.patient.numero_identifiant_patient:
            numero_identifiant_sante = None
            if request.patient.numero_identifiant_sante:
                numero_identifiant_sante = HprimNumeroIdentifiantSante(
                    identifiant=request.patient.numero_identifiant_sante
                )

            numero_identifiant_patients = None
            if request.patient.numero_identifiant_patient and request.patient.autorite_affectation:
                autorite = HprimAutoriteAffectation(
                    nom=request.patient.autorite_affectation,
                    type_autorite=AutoriteAffectation(request.patient.autorite_affectation)
                )
                numero_patient = HprimNumeroIdentifiantPatient(
                    identifiant=request.patient.numero_identifiant_patient,
                    autorite=autorite
                )
                numero_identifiant_patients = HprimNumeroIdentifiantPatients(
                    numero_identifiant_patient=[numero_patient]
                )

            if numero_identifiant_sante or numero_identifiant_patients:
                identifiant_admin_patient = HprimIdentifiantAdministrationPatient(
                    numero_identifiant_sante=numero_identifiant_sante,
                    numero_identifiant_patients=numero_identifiant_patients
                )

        patient = HprimPatient(
            identifiant_id=request.patient.identifiant_id,
            identifiant_clef=request.patient.identifiant_clef,
            nom=request.patient.nom,
            prenom=request.patient.prenom,
            date_naissance=request.patient.date_naissance,
            sexe=request.patient.sexe,
            identifiant_administration_patient=identifiant_admin_patient
        )

        acteur = HprimProfessionnel(
            nom=request.acteur.nom,
            prenom=request.acteur.prenom,
            numero_rpps=request.acteur.numero_rpps,
            numero_adeli=request.acteur.numero_adeli,
            specialite=request.acteur.specialite
        )

        # Créer la venue si fournie
        venue = None
        if request.venue:
            entite_juridique = None
            if request.venue.numero_finess or request.venue.numero_adeli:
                entite_juridique = HprimEntiteJuridique(
                    libelle=request.venue.libelle,
                    numero_finess=request.venue.numero_finess,
                    numero_adeli=request.venue.numero_adeli
                )

            venue = HprimVenue(
                identifiant=request.venue.identifiant,
                libelle=request.venue.libelle,
                entite_juridique=entite_juridique
            )

        # Créer les actes NGAP
        actes = []
        for acte_req in request.actes:
            acte = hprim_service.creer_acte_ngap_simple(
                lettre_cle=acte_req.lettre_cle,
                coefficient=acte_req.coefficient,
                execute_date=acte_req.execute_date,
                prestataire_rpps=request.acteur.numero_rpps,
                denombrement=acte_req.denombrement,
                position_dentaire=acte_req.position_dentaire,
                execute_heure=acte_req.execute_heure,
                numero_seance=acte_req.numero_seance,
                nabms=acte_req.nabms,
                minor_major=acte_req.minor_major,
                montant=acte_req.montant,
                commentaire=acte_req.commentaire,
                bhn_phns=acte_req.bhn_phns
            )
            actes.append(acte)

        # Créer le message HPRIM
        message = hprim_service.creer_message_actes_ngap(
            emetteur_id=request.emetteur_id,
            emetteur_nom=request.emetteur_nom,
            destinataire_id=request.destinataire_id,
            destinataire_nom=request.destinataire_nom,
            patient=patient,
            acteur=acteur,
            actes=actes,
            venue=venue,
            dossier_id=request.dossier_id,
            message_id=request.message_id
        )

        # Valider le message
        erreurs_validation = hprim_service.valider_message(message)

        # Générer le XML
        xml_content = hprim_service.generer_xml(message, valider=False)

        _persist_message(
            db,
            message_id=message.entete.message_id,
            type_message=message.entete.message_type.value,
            direction="outbound",
            status="validated" if not erreurs_validation else "validation_error",
            xml_content=xml_content,
            patient_id=request.patient.identifiant_id,
            emetteur_id=request.emetteur_id,
            destinataire_id=request.destinataire_id,
            validation_errors=erreurs_validation,
            source="api-hprim-ngap-emission",
        )
        for acte in actes:
            _persist_ngap_record(
                db,
                acte_id=acte.identifiant,
                patient_id=request.patient.identifiant_id,
                message_id=message.entete.message_id,
                lettre_cle=acte.lettre_cle,
                coefficient=float(acte.coefficient),
                execute_date=acte.execute_date,
                denombrement=acte.denombrement,
                position_dentaire=acte.position_dentaire,
                execute_heure=acte.execute_heure,
                numero_seance=acte.numero_seance,
                nabms=acte.nabms,
                minor_major=acte.minor_major,
                montant=float(acte.montant.valeur) if acte.montant else None,
                commentaire=acte.commentaire,
                action=acte.action.value,
                facturable=acte.facturable,
                valide=acte.valide,
                facture=acte.facture,
            )
        db.commit()

        # Préparer la réponse
        response = MessageNGAPResponse(
            message_id=message.entete.message_id,
            type_message=message.entete.message_type.value,
            xml_content=xml_content,
            xml_size=len(xml_content),
            actes_count=len(actes),
            validation_errors=[{
                "code": err.code,
                "message": err.message,
                "field": err.field
            } for err in erreurs_validation],
            created_at=datetime.now(),
            dossier_id=request.dossier_id
        )

        # Ajouter tâche en arrière-plan pour l'envoi réel
        if not erreurs_validation:
            background_tasks.add_task(
                envoyer_message_hprim,
                message.entete.message_id,
                xml_content,
                request.destinataire_id
            )

        logger.info(f"Message NGAP généré: {message.entete.message_id} ({len(xml_content)} caractères)")
        return response

    except HprimValidationError as e:
        logger.error(f"Erreur validation HPRIM NGAP: {e}")
        raise HTTPException(status_code=400, detail=f"Erreur de validation: {e}")
    except Exception as e:
        logger.error(f"Erreur émission actes NGAP: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/reception", response_model=ReceptionNGAPResponse)
async def recevoir_actes_ngap(
    request: ReceptionRequest,
    db: Session = Depends(get_session)
):
    """
    Recevoir des actes NGAP d'un émetteur HPRIM

    Cette endpoint permet de recevoir des actes infirmiers d'un système partenaire.
    """
    try:
        logger.info(f"Réception actes NGAP: {len(request.xml_content)} caractères")

        result = hprim_service.traiter_message_xml(request.xml_content)
        if not result["succes"]:
            return ReceptionNGAPResponse(
                succes=False,
                message_id=None,
                erreurs_traitement=[result.get("erreur", "Erreur inconnue")],
                erreurs_validation=result.get("erreurs", []),
            )

        message = result["message"]

        actes_recus = []
        for acte in message.actes_ngap:
            stored = _persist_ngap_record(
                db,
                acte_id=acte.identifiant,
                patient_id=message.patient.identifiant_id,
                message_id=message.entete.message_id,
                lettre_cle=acte.lettre_cle,
                coefficient=float(acte.coefficient),
                execute_date=acte.execute_date,
                denombrement=acte.denombrement,
                position_dentaire=acte.position_dentaire,
                execute_heure=acte.execute_heure,
                numero_seance=acte.numero_seance,
                nabms=acte.nabms,
                minor_major=acte.minor_major,
                montant=float(acte.montant.valeur) if acte.montant else None,
                commentaire=acte.commentaire,
                action=acte.action.value,
                facturable=acte.facturable,
                valide=acte.valide,
                facture=acte.facture,
            )
            actes_recus.append(_make_ngap_response(stored))

        _persist_message(
            db,
            message_id=message.entete.message_id,
            type_message=message.entete.message_type.value,
            direction="inbound",
            status="received",
            xml_content=request.xml_content,
            patient_id=message.patient.identifiant_id,
            emetteur_id=message.entete.emetteur_id,
            destinataire_id=message.entete.destinataire_id,
            validation_errors=[],
            source="api-hprim-ngap-reception",
        )
        db.commit()

        logger.info(f"Message NGAP traité: {message.entete.message_id}")
        return ReceptionNGAPResponse(
            succes=True,
            message_id=message.entete.message_id,
            actes_recus=actes_recus,
        )

    except Exception as e:
        logger.error(f"Erreur réception actes NGAP: {e}")
        return ReceptionNGAPResponse(
            succes=False,
            message_id=None,
            erreurs_traitement=[f"Erreur interne: {str(e)}"],
        )


@router.get("/{acte_id}", response_model=ActeNGAPResponse)
async def consulter_acte_ngap(acte_id: str, db: Session = Depends(get_session)):
    acte = db.get(StoredHprimNGAPAct, acte_id)
    if not acte or acte.deleted:
        raise HTTPException(status_code=404, detail="Acte NGAP introuvable")
    return _make_ngap_response(acte)


@router.put("/{acte_id}", response_model=ActeNGAPResponse)
async def modifier_acte_ngap(acte_id: str, acte_update: ActeNGAPRequest, db: Session = Depends(get_session)):
    existing = db.get(StoredHprimNGAPAct, acte_id)
    if not existing or existing.deleted:
        raise HTTPException(status_code=404, detail="Acte NGAP introuvable")

    stored = _persist_ngap_record(
        db,
        acte_id=acte_id,
        patient_id=existing.patient_id,
        message_id=existing.message_id,
        lettre_cle=acte_update.lettre_cle,
        coefficient=acte_update.coefficient,
        execute_date=acte_update.execute_date,
        denombrement=acte_update.denombrement,
        position_dentaire=acte_update.position_dentaire,
        execute_heure=acte_update.execute_heure,
        numero_seance=acte_update.numero_seance,
        nabms=acte_update.nabms,
        minor_major=acte_update.minor_major,
        montant=acte_update.montant,
        commentaire=acte_update.commentaire,
        action=HprimAction.MODIFICATION.value,
        facturable=existing.facturable,
        valide=existing.valide,
        facture=existing.facture,
    )
    db.commit()
    db.refresh(stored)
    return _make_ngap_response(stored)


@router.delete("/{acte_id}")
async def supprimer_acte_ngap(acte_id: str, db: Session = Depends(get_session)):
    existing = db.get(StoredHprimNGAPAct, acte_id)
    if not existing or existing.deleted:
        raise HTTPException(status_code=404, detail="Acte NGAP introuvable")

    existing.deleted = True
    existing.action = HprimAction.SUPPRESSION.value
    existing.updated_at = datetime.utcnow()
    db.add(existing)
    db.commit()
    return {"status": "deleted", "acte_id": acte_id, "deleted_at": datetime.utcnow().isoformat()}


@router.get("/patient/{patient_id}/historique")
async def historique_actes_ngap(patient_id: str, limit: int = 50, offset: int = 0, db: Session = Depends(get_session)):
    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)
    statement = (
        select(StoredHprimNGAPAct)
        .where(StoredHprimNGAPAct.patient_id == patient_id)
        .where(StoredHprimNGAPAct.deleted == False)
        .order_by(StoredHprimNGAPAct.execute_date.desc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    total_statement = (
        select(StoredHprimNGAPAct)
        .where(StoredHprimNGAPAct.patient_id == patient_id)
        .where(StoredHprimNGAPAct.deleted == False)
    )
    acts = list(db.exec(statement).all())
    total = len(db.exec(total_statement).all())
    return {
        "patient_id": patient_id,
        "actes": [_make_ngap_response(item).model_dump(mode="json") for item in acts],
        "total": total,
        "limit": safe_limit,
        "offset": safe_offset,
    }


# Fonctions utilitaires (à implémenter)
async def envoyer_message_hprim(message_id: str, xml_content: str, destinataire: str):
    """Envoie un message HPRIM en arrière-plan"""
    # TODO: Implémenter l'envoi réel (MLLP, HTTP, etc.)
    logger.info(f"Message {message_id} envoyé à {destinataire}")


async def envoyer_acquittement_hprim(acquittement_xml: str, destinataire: str):
    """Envoie un acquittement HPRIM en arrière-plan"""
    # TODO: Implémenter l'envoi réel
    logger.info(f"Acquittement envoyé à {destinataire}")


# Les modèles partagés PatientInfo, MedecinInfo, VenueInfo, ReceptionRequest,
# ReceptionResponse et hprim_service sont importés en haut du fichier.