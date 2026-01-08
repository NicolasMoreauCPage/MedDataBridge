from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/hprim", tags=["HPRIM Management"])

templates_dir = str(Path(__file__).parent.parent / "templates")
templates = Jinja2Templates(directory=templates_dir)

@router.get("/test-files", summary="Interface de gestion des fichiers HPRIM de test")
async def hprim_test_files_interface(request: Request):
    """
    Interface web pour explorer, analyser et importer les fichiers HPRIM de test.
    """
    return templates.TemplateResponse("hprim_test_files.html", {
        "request": request,
        "title": "Gestion HPRIM - Fichiers de Test"
    })

@router.get("/import", summary="Interface d'import HPRIM")
async def hprim_import_interface(request: Request):
    """
    Interface pour uploader et traiter des messages HPRIM entrants.
    """
    return templates.TemplateResponse("hprim_import.html", {
        "request": request,
        "title": "Import HPRIM"
    })