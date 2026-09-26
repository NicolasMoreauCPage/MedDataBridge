from fastapi import APIRouter, Request, Form, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlmodel import Session, select
from typing import Optional
import os
from app.db import get_session
from app.models import Dossier, Patient
from sqlalchemy import func
from fastapi import HTTPException, status
from app.templates import templates

router = APIRouter(prefix="/cotation-modern", tags=["cotation_selector"])


@router.get("/select", response_class=HTMLResponse)
def select_dossier(request: Request):
    """Renders the dossier selector UI."""
    return templates.TemplateResponse(request, "cotation_selector.html")


@router.post("/select")
def submit_dossier(id: str = Form(...)):
    # Redirect to the real cotation page for the dossier
    return RedirectResponse(url=f"/cotation-modern/dossiers/{id}/cotation", status_code=303)


@router.get("/search", response_class=JSONResponse)
def search_dossiers(
    request: Request,
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
    # If PUBLIC_SEARCH is disabled, enforce authentication
    public_search = os.getenv("PUBLIC_SEARCH", "true").lower() in ("1", "true", "yes")
    if not public_search:
        from app.auth import decode_token
        # enforce auth manually: expect Authorization: Bearer <token>
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")
        token = auth.split(None, 1)[1].strip()
        try:
            # decode_token will raise HTTPException if invalid
            decode_token(
                token,
                runtime_settings=request.app.state.settings,
                cache=request.app.state.cache,
                fallback_blacklist=request.app.state.token_blacklist,
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

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
            stmt_date_count = select(func.count(Dossier.id)).join(Patient).where(Patient.birth_date == date_val)
            # apply ght scoping if provided
            if ght_id is not None:
                stmt_date_count = stmt_date_count.where(Patient.ght_context_id == ght_id)
            total = session.exec(stmt_date_count).one()
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
            Patient.family.is_not(None) & (
                (func.lower(Patient.family).like(pattern_lower)) | (func.lower(Patient.given).like(pattern_lower))
            )
        )
        if ght_id is not None:
            base_stmt = base_stmt.where(Patient.ght_context_id == ght_id)

        # Count total matching
        count_stmt = select(func.count(Dossier.id)).join(Patient).where(
            Patient.family.is_not(None) & (
                (func.lower(Patient.family).like(pattern_lower)) | (func.lower(Patient.given).like(pattern_lower))
            )
        )
        if ght_id is not None:
            count_stmt = count_stmt.where(Patient.ght_context_id == ght_id)
        total = session.exec(count_stmt).one()

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
