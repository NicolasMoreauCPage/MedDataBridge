from fastapi import APIRouter, Request, Form, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.db import get_session
from app.models import Dossier, Patient

router = APIRouter(prefix="/cotation-modern", tags=["cotation_selector"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/select", response_class=HTMLResponse)
def select_dossier(request: Request):
    """Simple dossier selector placeholder.

    In a full implementation this would query dossiers and provide a
    search box. For now show instructions and a small form to enter an
    existing dossier id to jump to cotation.
    """
    return templates.TemplateResponse("cotation_selector.html", {"request": request})


@router.post("/select")
def submit_dossier(id: str = Form(...)):
    # Redirect to the real cotation page for the dossier
    return RedirectResponse(url=f"/cotation-modern/dossiers/{id}/cotation", status_code=303)


@router.get("/search", response_class=JSONResponse)
def search_dossiers(q: str = Query(None), session: Session = Depends(get_session)):
    """Search dossiers by patient family/given or birth_date (YYYY-MM-DD).

    Uses SQL-level filters for performance (ILIKE on family/given). Returns up to 50 results.
    """
    if not q or q.strip() == "":
        return []
    q = q.strip()
    # For sqlite use LIKE which is case-insensitive if configured; use lower() comparisons for portability
    pattern = f"%{q}%"
    # Try date exact match first (YYYY-MM-DD)
    results = []
    try:
        from datetime import date
        from sqlalchemy import func
        # First try to interpret q as ISO date YYYY-MM-DD
        rows = []
        try:
            date_val = date.fromisoformat(q)
            stmt_date = select(Dossier, Patient).join(Patient).where(Patient.birth_date == date_val).limit(50)
            rows = session.exec(stmt_date).all()
        except Exception:
            rows = []

        for d, p in rows:
            results.append({
                "dossier_id": d.id,
                "dossier_seq": getattr(d, 'dossier_seq', None),
                "patient_id": d.patient_id,
                "patient_family": getattr(p, 'family', ''),
                "patient_given": getattr(p, 'given', ''),
            })
        if len(results) >= 50:
            return results[:50]

        # Then search by family or given using case-insensitive LIKE (lower)
        pattern_lower = f"%{q.lower()}%"
        stmt_name = select(Dossier, Patient).join(Patient).where(
            (Patient.family != None) & ((func.lower(Patient.family).like(pattern_lower)) | (func.lower(Patient.given).like(pattern_lower)))
        ).limit(50 - len(results))
        rows2 = session.exec(stmt_name).all()
        for d, p in rows2:
            results.append({
                "dossier_id": d.id,
                "dossier_seq": getattr(d, 'dossier_seq', None),
                "patient_id": d.patient_id,
                "patient_family": getattr(p, 'family', ''),
                "patient_given": getattr(p, 'given', ''),
            })
    except Exception:
        # Fallback: return empty list on error to avoid exposing DB errors in UI
        return []
    return results[:50]
