from fastapi import APIRouter, Request, Form, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional
from app.db import get_session
from app.models import Dossier, Patient
from sqlalchemy import func

router = APIRouter(prefix="/cotation-modern", tags=["cotation_selector"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/select", response_class=HTMLResponse)
def select_dossier(request: Request):
    """Renders the dossier selector UI."""
    return templates.TemplateResponse("cotation_selector.html", {"request": request})


@router.post("/select")
def submit_dossier(id: str = Form(...)):
    # Redirect to the real cotation page for the dossier
    return RedirectResponse(url=f"/cotation-modern/dossiers/{id}/cotation", status_code=303)


@router.get("/search", response_class=JSONResponse)
def search_dossiers(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    ght_id: Optional[int] = Query(None),
    session: Session = Depends(get_session),
) -> JSONResponse:
    """Search dossiers by patient family/given or birth_date (YYYY-MM-DD).

    Supports pagination and optional `ght_id` scoping. Results are returned as:
    {"results": [...], "meta": {"total": N, "page": P, "per_page": M}}
    """
    if not q or q.strip() == "":
        return JSONResponse({"results": [], "meta": {"total": 0, "page": page, "per_page": per_page}})
    q = q.strip()
    try:
        # Try exact date match first
        from datetime import date
        results = []
        total = 0

        try:
            date_val = date.fromisoformat(q)
            stmt_date_count = select(Dossier).join(Patient).where(Patient.birth_date == date_val)
            # apply ght scoping if provided
            if ght_id is not None:
                stmt_date_count = stmt_date_count.where(Patient.ght_context_id == ght_id)
            total_rows = session.exec(stmt_date_count).all()
            total = len(total_rows)
            stmt_date = select(Dossier, Patient).join(Patient).where(Patient.birth_date == date_val).offset((page - 1) * per_page).limit(per_page)
            if ght_id is not None:
                stmt_date = stmt_date.where(Patient.ght_context_id == ght_id)
            rows = session.exec(stmt_date).all()
            for d, p in rows:
                results.append({
                    "dossier_id": d.id,
                    "dossier_seq": getattr(d, 'dossier_seq', None),
                    "patient_id": d.patient_id,
                    "patient_family": getattr(p, 'family', ''),
                    "patient_given": getattr(p, 'given', ''),
                })
        except Exception:
            results = []

        # If date search returned enough results, return paginated response
        if len(results) >= per_page:
            return JSONResponse({"results": results, "meta": {"total": total, "page": page, "per_page": per_page}})

        # Otherwise search by name using case-insensitive LIKE on family/given
        pattern_lower = f"%{q.lower()}%"
        base_stmt = select(Dossier, Patient).join(Patient).where(
            (Patient.family != None) & (
                (func.lower(Patient.family).like(pattern_lower)) | (func.lower(Patient.given).like(pattern_lower))
            )
        )
        if ght_id is not None:
            base_stmt = base_stmt.where(Patient.ght_context_id == ght_id)

        # Count total matching
        count_rows = session.exec(select(Dossier).join(Patient).where(
            (Patient.family != None) & (
                (func.lower(Patient.family).like(pattern_lower)) | (func.lower(Patient.given).like(pattern_lower))
            )
        )).all()
        total = len(count_rows)

        stmt_page = base_stmt.offset((page - 1) * per_page).limit(per_page)
        rows2 = session.exec(stmt_page).all()
        for d, p in rows2:
            results.append({
                "dossier_id": d.id,
                "dossier_seq": getattr(d, 'dossier_seq', None),
                "patient_id": d.patient_id,
                "patient_family": getattr(p, 'family', ''),
                "patient_given": getattr(p, 'given', ''),
            })

        return JSONResponse({"results": results, "meta": {"total": total, "page": page, "per_page": per_page}})
    except Exception:
        return JSONResponse({"results": [], "meta": {"total": 0, "page": page, "per_page": per_page}})
