# app/api/hprim_ngap.py
"""
API endpoints pour la gestion des actes NGAP HPRIM
Émission, réception et gestion des actes infirmiers
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app.hprim_models import (
    HprimActeNGAP, HprimPatient, HprimProfessionnel,
    HprimMessage, HprimMessageType, HprimAction, HprimContexteDossier
)
from app.services.hprim import HprimService, HprimValidationError

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

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


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

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


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

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


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


@router.post("/reception", response_model=ReceptionResponse)
async def recevoir_actes_ngap(
    request: ReceptionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    Recevoir des actes NGAP d'un émetteur HPRIM

    Cette endpoint permet de recevoir des actes infirmiers d'un système partenaire.
    """
    try:
        logger.info(f"Réception actes NGAP: {len(request.xml_content)} caractères")

        # Parser le XML
        message = hprim_service.parser_xml(request.xml_content)

        # Valider le message
        erreurs_validation = hprim_service.valider_message(message)

        # Traiter les actes NGAP
        actes_traitees = []
        for acte in message.actes_ngap:
            # TODO: Sauvegarder en base de données
            # TODO: Mettre à jour le dossier médical
            actes_traitees.append({
                "id": acte.identifiant,
                "lettre_cle": acte.lettre_cle,
                "coefficient": float(acte.coefficient),
                "execute_date": acte.execute_date.isoformat(),
                "valide": len(erreurs_validation) == 0
            })

        # Générer l'acquittement
        acquittement = hprim_service.generer_acquittement(message, erreurs_validation)

        # Préparer la réponse
        response = ReceptionResponse(
            message_id_original=message.entete.message_id,
            statut="OK" if not erreurs_validation else "ERREUR",
            actes_traitees=actes_traitees,
            erreurs_validation=[{
                "code": err.code,
                "message": err.message,
                "field": err.field
            } for err in erreurs_validation],
            acquittement_xml=acquittement,
            created_at=datetime.now()
        )

        # Ajouter tâche en arrière-plan pour l'acquittement
        background_tasks.add_task(
            envoyer_acquittement_hprim,
            acquittement,
            message.entete.emetteur_id
        )

        logger.info(f"Message NGAP traité: {message.entete.message_id}")
        return response

    except Exception as e:
        logger.error(f"Erreur réception actes NGAP: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne: {str(e)}")


# Fonctions utilitaires (à implémenter)
async def envoyer_message_hprim(message_id: str, xml_content: str, destinataire: str):
    """Envoie un message HPRIM en arrière-plan"""
    # TODO: Implémenter l'envoi réel (MLLP, HTTP, etc.)
    logger.info(f"Message {message_id} envoyé à {destinataire}")


async def envoyer_acquittement_hprim(acquittement_xml: str, destinataire: str):
    """Envoie un acquittement HPRIM en arrière-plan"""
    # TODO: Implémenter l'envoi réel
    logger.info(f"Acquittement envoyé à {destinataire}")


# Importer les modèles partagés depuis hprim_ccam
from app.api.hprim_ccam import (
    PatientInfo, MedecinInfo, VenueInfo, ReceptionRequest, ReceptionResponse,
    hprim_service
)