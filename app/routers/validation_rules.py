from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session
import json
from pathlib import Path
from typing import Optional

from app.db import get_session

router = APIRouter(prefix="/api/validation-rules", tags=["Validation Rules"])
ui_router = APIRouter(tags=["Validation Rules UI"])  # will mount at /validation/rules
templates = Jinja2Templates(directory="app/templates")

DATA_DIR = Path(__file__).parent.parent / "data"
RULES_FILE = DATA_DIR / "pam_custom_rules.json"


def _read_rules() -> dict:
    if not RULES_FILE.exists():
        return {}
    try:
        return json.loads(RULES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_rules(payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("", response_class=JSONResponse)
async def get_validation_rules():
    return _read_rules()


@router.post("", response_class=JSONResponse)
async def save_validation_rules(payload: dict):
    try:
        _write_rules(payload)
        # Try to reload in-memory rules if module available
        try:
            from app.services import pam_validation
            if hasattr(pam_validation, "load_custom_segment_rules"):
                pam_validation.load_custom_segment_rules()
        except Exception:
            pass
        return {"message": "Règles sauvegardées"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@ui_router.get("/validation/rules", response_class=HTMLResponse)
async def validation_rules_page(request: Request):
    rules = _read_rules()
    return templates.TemplateResponse("validation_rules.html", {"request": request, "rules_json": json.dumps(rules, ensure_ascii=False, indent=2)})
