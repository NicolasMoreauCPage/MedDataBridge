"""Module UCD - Unité Commune de Dispensation."""
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select, func

from app.db import get_session
from app.models import UCDAct, Dossier

router = APIRouter(prefix="/ucd", tags=["UCD"])


@router.get("/", response_class=HTMLResponse)
async def ucd_dashboard(request: Request, session: Session = Depends(get_session)):
    """Dashboard UCD avec statistiques réelles."""
    templates = request.app.state.templates

    total_acts = session.exec(select(func.count()).select_from(UCDAct)).one()

    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    acts_this_month = session.exec(
        select(func.count()).select_from(UCDAct).where(UCDAct.execute_date >= month_start)
    ).one()

    active_dossiers = session.exec(
        select(func.count(func.distinct(UCDAct.dossier_id)))
        .select_from(UCDAct)
        .join(Dossier, Dossier.id == UCDAct.dossier_id)
        .where(Dossier.discharge_time.is_(None))
    ).one()

    valid_acts = session.exec(
        select(func.count()).select_from(UCDAct).where(UCDAct.valide == True)  # noqa: E712
    ).one()
    conformity_rate = round(100 * valid_acts / total_acts) if total_acts else 0

    return templates.TemplateResponse(
        request,
        "ucd/dashboard.html",
        {
            "request": request,
            "total_acts": total_acts,
            "acts_this_month": acts_this_month,
            "active_dossiers": active_dossiers,
            "conformity_rate": conformity_rate,
        },
    )
