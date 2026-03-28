# app/api/hprim_ccam.py
"""
API endpoints pour la gestion des actes CCAM HPRIM
Émission, réception et gestion des actes médicaux
"""

import logging
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlmodel import select

from app.db import get_session
from app.models.hprim_models import HprimCCAMAct as StoredHprimCCAMAct, HprimMessage as StoredHprimMessage
from app.hprim_models import (
    HprimActeCCAM, HprimPatient, HprimProfessionnel,
    HprimMessage, HprimMessageType, HprimAction
)
from app.services.hprim import HprimService, HprimValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hprim/actes/ccam", tags=["HPRIM CCAM"])


# Modèles Pydantic pour les requêtes/réponses API
class ActeCCAMRequest(BaseModel):
    """Requête pour créer un acte CCAM"""
    code_acte: str = Field(..., description="Code CCAM (AAAA999)")
    code_activite: str = Field(..., description="Code activité (01-99)")
    code_phase: str = Field(..., description="Code phase (00-99)")
    executant_rpps: str = Field(..., description="RPPS du médecin exécutant")
    date_execution: datetime = Field(..., description="Date d'exécution")
    quantite: int = Field(1, description="Quantité", ge=1)
    modificateurs: List[str] = Field(default_factory=list, description="Modificateurs (A-Z, 0-9)")
    montant: Optional[float] = Field(None, description="Montant en euros")
    commentaire: Optional[str] = Field(None, description="Commentaire")

class PatientInfo(BaseModel):
    """Informations patient pour HPRIM"""
    identifiant_id: str = Field(..., description="ID patient")
    identifiant_clef: str = Field(..., description="Clé patient")
    nom: str = Field(..., description="Nom")
    prenom: str = Field(..., description="Prénom")
    date_naissance: Optional[str] = Field(None, description="Date naissance (YYYY-MM-DD)")
    sexe: Optional[str] = Field(None, description="Sexe")
    # Identifiants HPRIM optionnels
    numero_identifiant_sante: Optional[str] = Field(None, description="Numéro INS")
    numero_identifiant_patient: Optional[str] = Field(None, description="Numéro IPP/NDA")
    autorite_affectation: Optional[str] = Field(None, description="Autorité d'affectation (L/M/N/ISO/DNS/UUID)")


class MedecinInfo(BaseModel):
    """Informations médecin pour HPRIM"""
    nom: str = Field(..., description="Nom")
    prenom: str = Field(..., description="Prénom")
    numero_rpps: Optional[str] = Field(None, description="RPPS (11 chiffres)")
    numero_adeli: Optional[str] = Field(None, description="ADELI (format spécifique)")
    specialite: Optional[str] = Field(None, description="Spécialité")


class VenueInfo(BaseModel):
    """Informations de venue/structure pour HPRIM"""
    identifiant: str = Field(..., description="Identifiant de la venue")
    libelle: str = Field(..., description="Libellé de la venue")
    numero_finess: Optional[str] = Field(None, description="FINESS (9 chiffres)")
    numero_adeli: Optional[str] = Field(None, description="ADELI de l'établissement")
    autorite_affectation: Optional[str] = Field(None, description="Autorité d'affectation (L/M/N/ISO/DNS/UUID)")


class EmissionRequest(BaseModel):
    """Requête d'émission d'actes CCAM"""
    emetteur_id: str = Field(..., description="ID émetteur (FINESS)")
    emetteur_nom: str = Field(..., description="Nom émetteur")
    destinataire_id: str = Field(..., description="ID destinataire (FINESS)")
    destinataire_nom: str = Field(..., description="Nom destinataire")
    patient: PatientInfo = Field(..., description="Informations patient")
    acteur: MedecinInfo = Field(..., description="Médecin acteur")
    venue: Optional[VenueInfo] = Field(None, description="Informations de venue")
    actes: List[ActeCCAMRequest] = Field(..., description="Liste des actes CCAM")
    message_id: Optional[str] = Field(None, description="ID du message (auto-généré)")


class ActeCCAMResponse(BaseModel):
    """Réponse pour un acte CCAM"""
    id: str
    code_acte: str
    code_activite: str
    code_phase: str
    executant_rpps: str
    date_execution: datetime
    quantite: int
    modificateurs: List[str]
    montant: Optional[float]
    commentaire: Optional[str]
    action: str
    facturable: bool
    valide: bool
    facture: bool

class MessageHPRIMResponse(BaseModel):
    """Réponse pour un message HPRIM"""
    message_id: str
    type_message: str
    xml_content: str
    xml_size: int
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime

class ReceptionRequest(BaseModel):
    """Requête de réception d'actes CCAM"""
    xml_content: str = Field(..., description="Contenu XML HPRIM reçu")
    validate_only: bool = Field(False, description="Validation uniquement (pas de stockage)")


class ReceptionResponse(BaseModel):
    """Réponse de réception d'actes CCAM"""
    succes: bool
    message_id: Optional[str]
    actes_recus: List[ActeCCAMResponse] = Field(default_factory=list)
    erreurs_validation: List[Dict[str, Any]] = Field(default_factory=list)
    erreurs_traitement: List[str] = Field(default_factory=list)


# Instance du service HPRIM
hprim_service = HprimService()


def _split_modificateurs(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []
    return [item for item in raw_value.split(",") if item]


def _join_modificateurs(values: List[str]) -> str:
    return ",".join(value.strip() for value in values if value and value.strip())


def _serialize_validation_errors(errors: List[HprimValidationError]) -> str:
    payload = [
        {"code": err.code, "message": err.message, "field": err.field}
        for err in errors
    ]
    return json.dumps(payload, ensure_ascii=False)


def _message_filename(message_id: str) -> str:
    return f"{message_id}.xml"


def _make_acte_response(record: StoredHprimCCAMAct) -> ActeCCAMResponse:
    return ActeCCAMResponse(
        id=record.id,
        code_acte=record.code_acte,
        code_activite=record.code_activite,
        code_phase=record.code_phase,
        executant_rpps=record.executant_rpps,
        date_execution=record.date_execution,
        quantite=record.quantite,
        modificateurs=_split_modificateurs(record.modificateurs),
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
        stored = StoredHprimMessage(
            message_id=message_id,
            type_message=type_message,
            direction=direction,
        )

    stored.type_message = type_message
    stored.direction = direction
    stored.status = status
    stored.patient_id = patient_id
    stored.emetteur_id = emetteur_id
    stored.destinataire_id = destinataire_id
    stored.filename = _message_filename(message_id)
    stored.source = source
    stored.xml_content = xml_content
    stored.xml_size = len(xml_content)
    stored.validation_errors = _serialize_validation_errors(validation_errors or []) if validation_errors else None
    stored.updated_at = datetime.utcnow()
    db.add(stored)
    return stored


def _persist_acte_record(
    db: Session,
    *,
    acte_id: str,
    patient_id: Optional[str],
    message_id: Optional[str],
    code_acte: str,
    code_activite: str,
    code_phase: str,
    executant_rpps: str,
    date_execution: datetime,
    quantite: int,
    modificateurs: List[str],
    montant: Optional[float],
    commentaire: Optional[str],
    action: str,
    facturable: bool,
    valide: bool,
    facture: bool,
    deleted: bool = False,
) -> StoredHprimCCAMAct:
    stored = db.get(StoredHprimCCAMAct, acte_id)
    if not stored:
        stored = StoredHprimCCAMAct(id=acte_id)
        stored.created_at = datetime.utcnow()

    stored.patient_id = patient_id
    stored.message_id = message_id
    stored.code_acte = code_acte
    stored.code_activite = code_activite
    stored.code_phase = code_phase
    stored.executant_rpps = executant_rpps
    stored.date_execution = date_execution
    stored.quantite = quantite
    stored.modificateurs = _join_modificateurs(modificateurs)
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


@router.post("", response_model=ActeCCAMResponse)
async def creer_acte_ccam(
    acte: ActeCCAMRequest,
    patient_id: Optional[str] = None,
    db: Session = Depends(get_session),
):
    """Créer un acte CCAM unitaire via API (hors flux XML)."""
    try:
        acte_id = str(uuid.uuid4())
        record = _persist_acte_record(
            db,
            acte_id=acte_id,
            patient_id=patient_id,
            message_id=None,
            code_acte=acte.code_acte,
            code_activite=acte.code_activite,
            code_phase=acte.code_phase,
            executant_rpps=acte.executant_rpps,
            date_execution=acte.date_execution,
            quantite=acte.quantite,
            modificateurs=list(acte.modificateurs),
            montant=acte.montant,
            commentaire=acte.commentaire,
            action=HprimAction.CREATION.value,
            facturable=True,
            valide=False,
            facture=False,
        )
        db.commit()
        db.refresh(record)
        return _make_acte_response(record)
    except Exception as e:
        logger.error(f"Erreur création acte CCAM: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/emission", response_model=MessageHPRIMResponse)
async def emettre_actes_ccam(
    request: EmissionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Émettre des actes CCAM vers un destinataire HPRIM

    Cette endpoint permet d'envoyer des actes CCAM à un système partenaire
    via le protocole HPRIM XML.
    """
    try:
        logger.info(f"Émission actes CCAM: {len(request.actes)} actes vers {request.destinataire_id}")

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

        # Créer les actes CCAM
        actes = []
        persisted_actes: List[StoredHprimCCAMAct] = []
        for acte_req in request.actes:
            acte = hprim_service.creer_acte_ccam_simple(
                code_acte=acte_req.code_acte,
                code_activite=acte_req.code_activite,
                code_phase=acte_req.code_phase,
                executant_rpps=acte_req.executant_rpps,
                date_execution=acte_req.date_execution,
                quantite=acte_req.quantite,
                modificateurs=acte_req.modificateurs,
                montant=acte_req.montant
            )
            actes.append(acte)

        # Créer le message HPRIM
        message = hprim_service.creer_message_actes_ccam(
            emetteur_id=request.emetteur_id,
            emetteur_nom=request.emetteur_nom,
            destinataire_id=request.destinataire_id,
            destinataire_nom=request.destinataire_nom,
            patient=patient,
            acteur=acteur,
            actes=actes,
            venue=venue,
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
            source="api-hprim-ccam-emission",
        )
        for acte in actes:
            persisted_actes.append(
                _persist_acte_record(
                    db,
                    acte_id=acte.identifiant,
                    patient_id=request.patient.identifiant_id,
                    message_id=message.entete.message_id,
                    code_acte=acte.code_acte,
                    code_activite=acte.code_activite,
                    code_phase=acte.code_phase,
                    executant_rpps=acte.executant.numero_rpps or "",
                    date_execution=acte.execute_date,
                    quantite=acte.quantite,
                    modificateurs=[m.code for m in acte.modificateurs],
                    montant=float(acte.montant.valeur) if acte.montant else None,
                    commentaire=acte.commentaire,
                    action=acte.action.value,
                    facturable=acte.facturable,
                    valide=acte.valide,
                    facture=acte.facture,
                )
            )
        db.commit()

        # Préparer la réponse
        response = MessageHPRIMResponse(
            message_id=message.entete.message_id,
            type_message=message.entete.message_type.value,
            xml_content=xml_content,
            xml_size=len(xml_content),
            validation_errors=[{
                "code": err.code,
                "message": err.message,
                "field": err.field
            } for err in erreurs_validation],
            created_at=datetime.now()
        )

        # Ajouter tâche en arrière-plan pour l'envoi réel
        if not erreurs_validation:
            background_tasks.add_task(
                envoyer_message_hprim,
                message.entete.message_id,
                xml_content,
                request.destinataire_id
            )

        logger.info(f"Message HPRIM généré: {message.entete.message_id} ({len(xml_content)} caractères)")
        return response

    except HprimValidationError as e:
        logger.error(f"Erreur validation HPRIM: {e}")
        raise HTTPException(status_code=400, detail=f"Erreur de validation: {e}")
    except Exception as e:
        logger.error(f"Erreur émission actes CCAM: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.post("/reception", response_model=ReceptionResponse)
async def recevoir_actes_ccam(
    request: ReceptionRequest,
    db: Session = Depends(get_session)
):
    """
    Recevoir des actes CCAM depuis un partenaire HPRIM

    Cette endpoint traite les messages XML HPRIM reçus et
    peut soit les valider uniquement, soit les stocker.
    """
    try:
        logger.info(f"Réception actes CCAM: {len(request.xml_content)} caractères")

        # Traiter le message XML
        result = hprim_service.traiter_message_xml(request.xml_content)

        if not result["succes"]:
            return ReceptionResponse(
                succes=False,
                erreurs_traitement=[result.get("erreur", "Erreur inconnue")]
            )

        # Extraire les actes du message
        message = result["message"]
        actes_recus = []

        for acte in message.actes_ccam:
            acte_response = ActeCCAMResponse(
                id=acte.identifiant,
                code_acte=acte.code_acte,
                code_activite=acte.code_activite,
                code_phase=acte.code_phase,
                executant_rpps=acte.executant.numero_rpps,
                date_execution=acte.execute_date,
                quantite=acte.quantite,
                modificateurs=[m.code for m in acte.modificateurs],
                montant=float(acte.montant.valeur) if acte.montant else None,
                commentaire=acte.commentaire,
                action=acte.action.value,
                facturable=acte.facturable,
                valide=acte.valide,
                facture=acte.facture
            )
            actes_recus.append(acte_response)

            if not request.validate_only:
                _persist_acte_record(
                    db,
                    acte_id=acte.identifiant,
                    patient_id=message.patient.identifiant_id,
                    message_id=message.entete.message_id,
                    code_acte=acte.code_acte,
                    code_activite=acte.code_activite,
                    code_phase=acte.code_phase,
                    executant_rpps=acte.executant.numero_rpps or "",
                    date_execution=acte.execute_date,
                    quantite=acte.quantite,
                    modificateurs=[m.code for m in acte.modificateurs],
                    montant=float(acte.montant.valeur) if acte.montant else None,
                    commentaire=acte.commentaire,
                    action=acte.action.value,
                    facturable=acte.facturable,
                    valide=acte.valide,
                    facture=acte.facture,
                )

        if not request.validate_only:
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
                source="api-hprim-ccam-reception",
            )
            db.commit()

        return ReceptionResponse(
            succes=True,
            message_id=message.entete.message_id,
            actes_recus=actes_recus
        )

    except Exception as e:
        logger.error(f"Erreur réception actes CCAM: {e}")
        return ReceptionResponse(
            succes=False,
            erreurs_traitement=[f"Erreur de traitement: {str(e)}"]
        )


@router.get("/{acte_id}", response_model=ActeCCAMResponse)
async def consulter_acte_ccam(
    acte_id: str,
    db: Session = Depends(get_session)
):
    """
    Consulter un acte CCAM par son ID

    Retourne les détails d'un acte CCAM spécifique.
    """
    try:
        acte_record = db.get(StoredHprimCCAMAct, acte_id)

        if not acte_record or acte_record.deleted:
            raise HTTPException(status_code=404, detail="Acte CCAM introuvable")

        return _make_acte_response(acte_record)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Erreur consultation acte {acte_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.put("/{acte_id}", response_model=ActeCCAMResponse)
async def modifier_acte_ccam(
    acte_id: str,
    acte_update: ActeCCAMRequest,
    db: Session = Depends(get_session)
):
    """
    Modifier un acte CCAM existant

    Permet de modifier les propriétés d'un acte CCAM.
    """
    try:
        existing = db.get(StoredHprimCCAMAct, acte_id)
        if not existing or existing.deleted:
            raise HTTPException(status_code=404, detail="Acte CCAM introuvable")

        updated = _persist_acte_record(
            db,
            acte_id=acte_id,
            patient_id=existing.patient_id,
            message_id=existing.message_id,
            code_acte=acte_update.code_acte,
            code_activite=acte_update.code_activite,
            code_phase=acte_update.code_phase,
            executant_rpps=acte_update.executant_rpps,
            date_execution=acte_update.date_execution,
            quantite=acte_update.quantite,
            modificateurs=list(acte_update.modificateurs),
            montant=acte_update.montant,
            commentaire=acte_update.commentaire,
            action=HprimAction.MODIFICATION.value,
            facturable=existing.facturable,
            valide=existing.valide,
            facture=existing.facture,
            deleted=False,
        )
        db.commit()
        db.refresh(updated)

        return _make_acte_response(updated)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Erreur modification acte {acte_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.delete("/{acte_id}")
async def supprimer_acte_ccam(
    acte_id: str,
    db: Session = Depends(get_session)
):
    """
    Supprimer un acte CCAM

    Marque un acte comme supprimé (logique ou physique selon la politique).
    """
    try:
        existing = db.get(StoredHprimCCAMAct, acte_id)
        if not existing or existing.deleted:
            raise HTTPException(status_code=404, detail="Acte CCAM introuvable")

        existing.deleted = True
        existing.action = HprimAction.SUPPRESSION.value
        existing.updated_at = datetime.utcnow()
        db.add(existing)
        db.commit()

        return {
            "status": "deleted",
            "acte_id": acte_id,
            "deleted_at": datetime.now().isoformat(),
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Erreur suppression acte {acte_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/patient/{patient_id}/historique")
async def historique_actes_patient(
    patient_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session)
):
    """
    Récupérer l'historique des actes CCAM pour un patient

    Retourne la liste paginée des actes CCAM d'un patient.
    """
    try:
        safe_limit = max(1, min(limit, 200))
        safe_offset = max(0, offset)

        statement = (
            select(StoredHprimCCAMAct)
            .where(StoredHprimCCAMAct.patient_id == patient_id)
            .where(StoredHprimCCAMAct.deleted == False)
            .order_by(StoredHprimCCAMAct.date_execution.desc())
            .offset(safe_offset)
            .limit(safe_limit)
        )
        total_statement = (
            select(StoredHprimCCAMAct)
            .where(StoredHprimCCAMAct.patient_id == patient_id)
            .where(StoredHprimCCAMAct.deleted == False)
        )
        paginated = list(db.exec(statement).all())
        total = len(db.exec(total_statement).all())

        return {
            "patient_id": patient_id,
            "actes": [_make_acte_response(item).model_dump(mode="json") for item in paginated],
            "total": total,
            "limit": safe_limit,
            "offset": safe_offset,
        }

    except Exception as e:
        logger.error(f"Erreur historique patient {patient_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


@router.get("/cotation", response_class=HTMLResponse)
async def page_cotation_actes():
    """
    Page HTML pour la cotation des actes CCAM HPRIM

    Retourne l'interface utilisateur pour créer et gérer les actes médicaux.
    """
    try:
        # Lire le fichier HTML
        html_file_path = Path(__file__).parent.parent / "templates" / "hprim_cotation.html"

        if not html_file_path.exists():
            raise HTTPException(status_code=404, detail="Page de cotation non trouvée")

        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        return HTMLResponse(content=html_content, status_code=200)

    except Exception as e:
        logger.error(f"Erreur chargement page cotation: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur chargement page: {str(e)}")


# Fonctions utilitaires
async def envoyer_message_hprim(message_id: str, xml_content: str, destinataire_id: str):
    """
    Tâche en arrière-plan pour envoyer un message HPRIM

    Cette fonction sera appelée en arrière-plan pour gérer l'envoi
    réel du message XML vers le destinataire.
    """
    try:
        logger.info(f"Envoi message {message_id} vers {destinataire_id}")

        # Validation HPRIM automatique avant émission (XSD + contenu)
        from app.services.hprim.hprim_service import HprimService
        import time as _time
        start = _time.time()
        hprim = HprimService()
        result = hprim.traiter_message_xml(xml_content)
        if not result.get("succes"):
            logger.error(f"Validation HPRIM avant émission échouée: {result.get('erreur')}")
            # Metrics outbound error
            try:
                from app.metrics import record_hprim_validation
                err_type = result.get("type_erreur")
                # Map to helper types
                mapped = {
                    "XSD_VALIDATION": "xsd",
                    "VALIDATION": "content",
                    "ENCODING": "encoding",
                }.get(err_type, "processing")
                record_hprim_validation(
                    succes=False,
                    schema=result.get("schema_utilise"),
                    error_type=mapped,
                    direction="outbound",
                    duration_seconds=_time.time() - start,
                )
            except Exception:
                pass
            # Enregistrer dans MessageLog (out)
            try:
                from app.models_shared import MessageLog
                from app.db import engine
                from sqlmodel import Session as SQLModelSession
                with SQLModelSession(engine) as session:
                    log = MessageLog(
                        direction="out",
                        kind="HPRIM",
                        message_type="HPRIM-XML",
                        endpoint_id=None,
                        correlation_id=message_id,
                        status="error",
                        payload=xml_content,
                        ack_payload=f"HPRIM validation failed before send ({result.get('type_erreur')}): {result.get('erreur')}"
                    )
                    session.add(log)
                    session.commit()
            except Exception:
                pass
            return

        # TODO: Implémenter l'envoi réel (HTTP, file d'attente, etc.)
        # Pour l'instant, on simule un envoi réussi
        logger.info(f"Message {message_id} envoyé avec succès (simulation)")

        # Log emission OK
        try:
            from app.models_shared import MessageLog
            from app.db import engine
            from sqlmodel import Session as SQLModelSession
            with SQLModelSession(engine) as session:
                schema_info = result.get("schema_utilise")
                log = MessageLog(
                    direction="out",
                    kind="HPRIM",
                    message_type="HPRIM-XML",
                    endpoint_id=None,
                    correlation_id=message_id,
                    status="sent",
                    payload=xml_content,
                    ack_payload=f"HPRIM sent OK{(' (' + schema_info + ')') if schema_info else ''}"
                )
                session.add(log)
                session.commit()
        except Exception:
            pass

        # Metrics outbound success
        try:
            from app.metrics import record_hprim_validation
            record_hprim_validation(
                succes=True,
                schema=result.get("schema_utilise"),
                error_type=None,
                direction="outbound",
                duration_seconds=_time.time() - start,
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Erreur envoi message {message_id}: {e}")
        # TODO: Gérer les erreurs d'envoi (retry, alertes, etc.)