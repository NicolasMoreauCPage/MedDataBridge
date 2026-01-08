from sqlmodel import select
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any

from app.db import Session
from app.models import Dossier, Patient, DossierType
from app.models_structure import UniteFonctionnelle, Service, Pole, EntiteGeographique


def get_dossiers_for_list(
    session: Session, 
    ej_id: Optional[int] = None, 
    patient_id: Optional[int] = None,
    dossier_type: Optional[DossierType] = None,
    dossier_seq: Optional[int] = None
) -> List[Dossier]:
    """Builds the query and fetches dossiers based on filters."""
    stmt = select(Dossier).options(selectinload(Dossier.venues)).order_by(Dossier.admit_time.desc())
    if ej_id:
        stmt = stmt.join(Patient).where(Patient.entite_juridique_id == ej_id)
    if patient_id:
        stmt = stmt.where(Dossier.patient_id == patient_id)
    if dossier_type:
        stmt = stmt.where(Dossier.dossier_type == dossier_type)
    if dossier_seq:
        stmt = stmt.where(Dossier.dossier_seq == dossier_seq)
    
    return session.exec(stmt).all()

def format_dossiers_for_template(dossiers: List[Dossier]) -> List[Dict[str, Any]]:
    """Formats a list of Dossier objects for the list.html template."""
    rows = [
        {
            "cells": [
                d.dossier_seq, 
                d.id, 
                d.patient_id, 
                (d.venues[0].uf_responsabilite if d.venues and d.venues[0].uf_responsabilite else "N/A"),
                getattr(d, 'dossier_type', DossierType.HOSPITALISE).value.capitalize(),
                d.admit_time.strftime("%d/%m/%Y %H:%M") if d.admit_time else None,
                d.discharge_time.strftime("%d/%m/%Y %H:%M") if d.discharge_time else None
            ],
            "detail_url": f"/dossiers/{d.id}", 
            "edit_url": f"/dossiers/{d.id}/edit",
        } for d in dossiers
    ]
    return rows

def get_new_dossier_context(session: Session, ej_id: Optional[int]) -> Dict[str, Any]:
    """Gets the context (form fields and options) for the new dossier form."""
    uf_options = []
    if ej_id:
        ufs = session.exec(
            select(UniteFonctionnelle)
            .join(Service).join(Pole).join(EntiteGeographique)
            .where(EntiteGeographique.entite_juridique_id == ej_id)
            .where(UniteFonctionnelle.status == "active")
        ).all()
        uf_options = [{"value": uf.identifier, "label": f"{uf.identifier} - {uf.name}"} for uf in ufs]
    
    dossier_type_opts = [{"value": dt.value, "label": dt.name.replace('_', ' ').capitalize()} for dt in DossierType]
    
    return {
        "uf_options": uf_options,
        "dossier_type_opts": dossier_type_opts
    }
