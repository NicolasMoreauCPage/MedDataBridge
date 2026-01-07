"""
Routes pour visualiser et gérer les messages HPRIM de cotation reçus.
Permet de voir quels dossiers ont des cotations actives.
"""
import logging
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, or_, and_, func
from typing import Optional

from app.db import get_session
from app.models_transport import MessageLog
from app.models import Dossier, Patient, CCAMAct, NGAPAct, UCDAct, LPPAct
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hprim-cotation", tags=["HPRIM Cotation"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def hprim_messages_dashboard(
    request: Request,
    session: Session = Depends(get_session),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    search: Optional[str] = Query(None, description="Rechercher NDA/IPP")
):
    """
    Dashboard des messages HPRIM de cotation reçus.
    Affiche les dossiers ayant des cotations actives.
    """
    # Requête pour les messages HPRIM
    query = select(MessageLog).where(MessageLog.kind == "HPRIM")
    
    if status:
        query = query.where(MessageLog.status == status)
    
    if search:
        query = query.where(
            or_(
                MessageLog.correlation_id.contains(search),
                MessageLog.payload.contains(search)
            )
        )
    
    query = query.order_by(MessageLog.created_at.desc()).limit(100)
    
    hprim_messages = session.exec(query).all()
    
    # Statistiques
    stats = {
        "total": session.exec(select(func.count(MessageLog.id)).where(MessageLog.kind == "HPRIM")).one(),
        "received": session.exec(select(func.count(MessageLog.id)).where(
            and_(MessageLog.kind == "HPRIM", MessageLog.status == "received")
        )).one(),
        "error": session.exec(select(func.count(MessageLog.id)).where(
            and_(MessageLog.kind == "HPRIM", MessageLog.status == "error")
        )).one(),
    }
    
    return templates.TemplateResponse(
        "hprim/messages_dashboard.html",
        {
            "request": request,
            "messages": hprim_messages,
            "stats": stats,
            "current_status": status,
            "search_term": search
        }
    )


@router.get("/message/{message_id}", response_class=HTMLResponse)
async def view_hprim_message(
    message_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Affiche le détail d'un message HPRIM avec parsing des actes.
    """
    message = session.get(MessageLog, message_id)
    if not message or message.kind != "HPRIM":
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Message HPRIM introuvable"},
            status_code=404
        )
    
    # Parser le message HPRIM pour extraire les actes
    actes_info = None
    patient_info = None
    venue_info = None
    
    try:
        from app.services.hprim.hprim_xml import HprimXmlService
        hprim_service = HprimXmlService()
        parsed_message = hprim_service.parse_xml(message.payload)
        
        # Extraire les informations
        patient_info = {
            "nom": parsed_message.patient.nom if parsed_message.patient else None,
            "prenom": parsed_message.patient.prenom if parsed_message.patient else None,
            "naissance": parsed_message.patient.date_naissance if parsed_message.patient else None,
        }
        
        if parsed_message.venue:
            venue_info = {
                "numero": parsed_message.venue.numero_sejour,
                "date_entree": parsed_message.venue.date_entree,
            }
        
        # Actes CCAM
        ccam_actes = []
        if hasattr(parsed_message, 'actes_ccam') and parsed_message.actes_ccam:
            for acte in parsed_message.actes_ccam:
                ccam_actes.append({
                    "code": acte.code_acte,
                    "activite": acte.code_activite,
                    "phase": acte.code_phase,
                    "date": acte.execute_date.strftime("%d/%m/%Y") if acte.execute_date else None,
                    "quantite": acte.quantite,
                    "executant": f"{acte.executant.nom} {acte.executant.prenom}" if acte.executant else "N/A",
                    "modificateurs": ", ".join([m.code for m in acte.modificateurs]) if acte.modificateurs else "",
                    "montant": acte.montant.valeur if acte.montant else None
                })
        
        # Actes NGAP
        ngap_actes = []
        if hasattr(parsed_message, 'actes_ngap') and parsed_message.actes_ngap:
            for acte in parsed_message.actes_ngap:
                ngap_actes.append({
                    "lettre_cle": acte.lettre_cle,
                    "coefficient": acte.coefficient,
                    "date": acte.execute_date.strftime("%d/%m/%Y") if acte.execute_date else None,
                    "denombrement": acte.denombrement,
                    "executant": f"{acte.executant.nom} {acte.executant.prenom}" if hasattr(acte, 'executant') and acte.executant else "N/A",
                    "montant": acte.montant.valeur if hasattr(acte, 'montant') and acte.montant else None
                })
        
        actes_info = {
            "ccam": ccam_actes,
            "ngap": ngap_actes,
            "ucd": [],  # TODO: parser UCD
            "lpp": []   # TODO: parser LPP
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du parsing du message HPRIM {message_id}: {e}", exc_info=True)
        actes_info = {"error": str(e)}
    
    return templates.TemplateResponse(
        "hprim/message_detail.html",
        {
            "request": request,
            "message": message,
            "patient_info": patient_info,
            "venue_info": venue_info,
            "actes_info": actes_info
        }
    )


@router.get("/dossiers-avec-cotations", response_class=HTMLResponse)
async def dossiers_avec_cotations(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Liste des dossiers ayant reçu des messages HPRIM de cotation.
    """
    # Trouver les messages HPRIM avec NDA dans le payload
    hprim_messages = session.exec(
        select(MessageLog)
        .where(MessageLog.kind == "HPRIM")
        .where(MessageLog.status.in_(["received", "processed"]))
        .order_by(MessageLog.created_at.desc())
    ).all()
    
    # Extraire les NDA des messages et trouver les dossiers correspondants
    dossiers_info = []
    seen_ndas = set()
    
    for msg in hprim_messages:
        try:
            # Parser pour extraire le NDA
            from app.services.hprim.hprim_xml import HprimXmlService
            hprim_service = HprimXmlService()
            parsed = hprim_service.parse_xml(msg.payload)
            
            if parsed.venue and parsed.venue.numero_sejour:
                nda = parsed.venue.numero_sejour
                
                if nda not in seen_ndas:
                    seen_ndas.add(nda)
                    
                    # Chercher le dossier correspondant
                    dossier = session.exec(
                        select(Dossier).where(Dossier.numero_dossier == nda)
                    ).first()
                    
                    if dossier:
                        patient = session.get(Patient, dossier.patient_id) if dossier.patient_id else None
                        
                        # Compter les messages HPRIM pour ce dossier
                        nb_messages = session.exec(
                            select(func.count(MessageLog.id))
                            .where(MessageLog.kind == "HPRIM")
                            .where(MessageLog.payload.contains(nda))
                        ).one()
                        
                        dossiers_info.append({
                            "dossier": dossier,
                            "patient": patient,
                            "nda": nda,
                            "nb_messages": nb_messages,
                            "dernier_message": msg.created_at
                        })
        except Exception as e:
            logger.debug(f"Impossible de parser le message {msg.id}: {e}")
            continue
    
    return templates.TemplateResponse(
        "hprim/dossiers_cotations.html",
        {
            "request": request,
            "dossiers": dossiers_info
        }
    )


@router.post("/message/{message_id}/import-ccam")
async def import_ccam_acts(
    message_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Importe les actes CCAM d'un message HPRIM dans la table CCAMAct.
    """
    try:
        # Récupérer le message
        message = session.get(MessageLog, message_id)
        if not message or message.kind != "HPRIM":
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Message introuvable",
                status_code=303
            )
        
        # Parser le message HPRIM
        from app.services.hprim.hprim_xml import HprimXmlService
        hprim_service = HprimXmlService()
        parsed_message = hprim_service.parse_xml(message.payload)
        
        # Extraire le NDA pour trouver le dossier
        nda = None
        if hasattr(parsed_message, 'venue') and parsed_message.venue:
            nda = parsed_message.venue.numero_sejour
        
        if not nda:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=NDA introuvable dans le message",
                status_code=303
            )
        
        # Trouver le dossier correspondant
        dossier = session.exec(
            select(Dossier).where(Dossier.numero_dossier == nda)
        ).first()
        
        if not dossier:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Dossier introuvable pour NDA {nda}",
                status_code=303
            )
        
        # Importer les actes CCAM
        imported_count = 0
        if hasattr(parsed_message, 'actes_ccam') and parsed_message.actes_ccam:
            for acte in parsed_message.actes_ccam:
                # Vérifier si l'acte existe déjà (éviter les doublons)
                existing = session.exec(
                    select(CCAMAct)
                    .where(CCAMAct.dossier_id == dossier.id)
                    .where(CCAMAct.code_acte == acte.code_acte)
                    .where(CCAMAct.execute_date == acte.execute_date)
                ).first()
                
                if not existing:
                    # Créer un nouvel acte CCAM
                    new_act = CCAMAct(
                        dossier_id=dossier.id,
                        code_acte=acte.code_acte,
                        code_activite=acte.code_activite if hasattr(acte, 'code_activite') else None,
                        code_phase=acte.code_phase if hasattr(acte, 'code_phase') else None,
                        modificateurs=",".join([m.code for m in acte.modificateurs]) if hasattr(acte, 'modificateurs') and acte.modificateurs else None,
                        execute_date=acte.execute_date,
                        quantite=acte.quantite if hasattr(acte, 'quantite') else 1,
                        montant=float(acte.montant.valeur) if hasattr(acte, 'montant') and acte.montant and hasattr(acte.montant, 'valeur') else None,
                        facturable=True,
                        valide=False,
                        facture=False
                    )
                    session.add(new_act)
                    imported_count += 1
        
        session.commit()
        logger.info(f"Importé {imported_count} actes CCAM depuis le message HPRIM {message_id} vers le dossier {dossier.id}")
        
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?success=Import réussi: {imported_count} actes CCAM importés",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'import des actes CCAM: {e}", exc_info=True)
        session.rollback()
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?error=Erreur: {str(e)}",
            status_code=303
        )


@router.post("/message/{message_id}/import-ngap")
async def import_ngap_acts(
    message_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Importe les actes NGAP d'un message HPRIM dans la table NGAPAct.
    """
    try:
        # Récupérer le message
        message = session.get(MessageLog, message_id)
        if not message or message.kind != "HPRIM":
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Message introuvable",
                status_code=303
            )
        
        # Parser le message HPRIM
        from app.services.hprim.hprim_xml import HprimXmlService
        hprim_service = HprimXmlService()
        parsed_message = hprim_service.parse_xml(message.payload)
        
        # Extraire le NDA pour trouver le dossier
        nda = None
        if hasattr(parsed_message, 'venue') and parsed_message.venue:
            nda = parsed_message.venue.numero_sejour
        
        if not nda:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=NDA introuvable dans le message",
                status_code=303
            )
        
        # Trouver le dossier correspondant
        dossier = session.exec(
            select(Dossier).where(Dossier.numero_dossier == nda)
        ).first()
        
        if not dossier:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Dossier introuvable pour NDA {nda}",
                status_code=303
            )
        
        # Importer les actes NGAP
        imported_count = 0
        if hasattr(parsed_message, 'actes_ngap') and parsed_message.actes_ngap:
            for acte in parsed_message.actes_ngap:
                # Vérifier si l'acte existe déjà
                existing = session.exec(
                    select(NGAPAct)
                    .where(NGAPAct.dossier_id == dossier.id)
                    .where(NGAPAct.lettre_cle == acte.lettre_cle)
                    .where(NGAPAct.execute_date == acte.execute_date)
                ).first()
                
                if not existing:
                    # Créer un nouvel acte NGAP
                    new_act = NGAPAct(
                        dossier_id=dossier.id,
                        lettre_cle=acte.lettre_cle,
                        coefficient=float(acte.coefficient) if hasattr(acte, 'coefficient') else 1.0,
                        execute_date=acte.execute_date,
                        montant=float(acte.montant.valeur) if hasattr(acte, 'montant') and acte.montant and hasattr(acte.montant, 'valeur') else None,
                        facturable=True,
                        valide=False,
                        facture=False
                    )
                    session.add(new_act)
                    imported_count += 1
        
        session.commit()
        logger.info(f"Importé {imported_count} actes NGAP depuis le message HPRIM {message_id} vers le dossier {dossier.id}")
        
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?success=Import réussi: {imported_count} actes NGAP importés",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'import des actes NGAP: {e}", exc_info=True)
        session.rollback()
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?error=Erreur: {str(e)}",
            status_code=303
        )


@router.post("/message/{message_id}/import-ucd")
async def import_ucd_acts(
    message_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Importe les actes UCD d'un message HPRIM dans la table UCDAct.
    """
    try:
        # Récupérer le message
        message = session.get(MessageLog, message_id)
        if not message or message.kind != "HPRIM":
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Message introuvable",
                status_code=303
            )
        
        # Parser le message HPRIM
        from app.services.hprim.hprim_xml import HprimXmlService
        hprim_service = HprimXmlService()
        parsed_message = hprim_service.parse_xml(message.payload)
        
        # Extraire le NDA pour trouver le dossier
        nda = None
        if hasattr(parsed_message, 'venue') and parsed_message.venue:
            nda = parsed_message.venue.numero_sejour
        
        if not nda:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=NDA introuvable dans le message",
                status_code=303
            )
        
        # Trouver le dossier correspondant
        dossier = session.exec(
            select(Dossier).where(Dossier.numero_dossier == nda)
        ).first()
        
        if not dossier:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Dossier introuvable pour NDA {nda}",
                status_code=303
            )
        
        # Importer les actes UCD
        imported_count = 0
        if hasattr(parsed_message, 'actes_ucd') and parsed_message.actes_ucd:
            for acte in parsed_message.actes_ucd:
                # Vérifier si l'acte existe déjà
                existing = session.exec(
                    select(UCDAct)
                    .where(UCDAct.dossier_id == dossier.id)
                    .where(UCDAct.code_cip == acte.code_cip)
                    .where(UCDAct.execute_date == acte.execute_date)
                ).first()
                
                if not existing:
                    # Créer un nouvel acte UCD
                    new_act = UCDAct(
                        dossier_id=dossier.id,
                        code_cip=acte.code_cip,
                        designation=acte.designation if hasattr(acte, 'designation') else None,
                        quantite=float(acte.quantite) if hasattr(acte, 'quantite') else 1.0,
                        prix_unitaire=float(acte.prix_unitaire) if hasattr(acte, 'prix_unitaire') else None,
                        montant_total=float(acte.montant_total) if hasattr(acte, 'montant_total') else None,
                        execute_date=acte.execute_date
                    )
                    session.add(new_act)
                    imported_count += 1
        
        session.commit()
        logger.info(f"Importé {imported_count} actes UCD depuis le message HPRIM {message_id} vers le dossier {dossier.id}")
        
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?success=Import réussi: {imported_count} actes UCD importés",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'import des actes UCD: {e}", exc_info=True)
        session.rollback()
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?error=Erreur: {str(e)}",
            status_code=303
        )


@router.post("/message/{message_id}/import-lpp")
async def import_lpp_acts(
    message_id: int,
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Importe les actes LPP d'un message HPRIM dans la table LPPAct.
    """
    try:
        # Récupérer le message
        message = session.get(MessageLog, message_id)
        if not message or message.kind != "HPRIM":
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Message introuvable",
                status_code=303
            )
        
        # Parser le message HPRIM
        from app.services.hprim.hprim_xml import HprimXmlService
        hprim_service = HprimXmlService()
        parsed_message = hprim_service.parse_xml(message.payload)
        
        # Extraire le NDA pour trouver le dossier
        nda = None
        if hasattr(parsed_message, 'venue') and parsed_message.venue:
            nda = parsed_message.venue.numero_sejour
        
        if not nda:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=NDA introuvable dans le message",
                status_code=303
            )
        
        # Trouver le dossier correspondant
        dossier = session.exec(
            select(Dossier).where(Dossier.numero_dossier == nda)
        ).first()
        
        if not dossier:
            return RedirectResponse(
                url=f"/hprim-cotation/message/{message_id}?error=Dossier introuvable pour NDA {nda}",
                status_code=303
            )
        
        # Importer les actes LPP
        imported_count = 0
        if hasattr(parsed_message, 'actes_lpp') and parsed_message.actes_lpp:
            for acte in parsed_message.actes_lpp:
                # Vérifier si l'acte existe déjà
                existing = session.exec(
                    select(LPPAct)
                    .where(LPPAct.dossier_id == dossier.id)
                    .where(LPPAct.code_lpp == acte.code_lpp)
                    .where(LPPAct.execute_date == acte.execute_date)
                ).first()
                
                if not existing:
                    # Créer un nouvel acte LPP
                    new_act = LPPAct(
                        dossier_id=dossier.id,
                        code_lpp=acte.code_lpp,
                        libelle=acte.libelle if hasattr(acte, 'libelle') else None,
                        quantite=float(acte.quantite) if hasattr(acte, 'quantite') else 1.0,
                        prix_unitaire=float(acte.prix_unitaire) if hasattr(acte, 'prix_unitaire') else None,
                        montant_total=float(acte.montant_total) if hasattr(acte, 'montant_total') else None,
                        execute_date=acte.execute_date
                    )
                    session.add(new_act)
                    imported_count += 1
        
        session.commit()
        logger.info(f"Importé {imported_count} actes LPP depuis le message HPRIM {message_id} vers le dossier {dossier.id}")
        
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?success=Import réussi: {imported_count} actes LPP importés",
            status_code=303
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'import des actes LPP: {e}", exc_info=True)
        session.rollback()
        return RedirectResponse(
            url=f"/hprim-cotation/message/{message_id}?error=Erreur: {str(e)}",
            status_code=303
        )
