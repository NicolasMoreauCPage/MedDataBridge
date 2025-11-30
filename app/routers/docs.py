"""Router pour la documentation des standards."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from ..db import get_session

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Additional resource pages for examples/tools used by the UI "Ressources" menu


@router.get("/examples/hl7v2", response_class=HTMLResponse)
async def examples_hl7v2(request: Request):
    return templates.TemplateResponse(
        "examples_hl7v2.html",
        {"request": request, "title": "Exemples HL7 v2"}
    )


@router.get("/examples/mfn", response_class=HTMLResponse)
async def examples_mfn(request: Request):
    return templates.TemplateResponse(
        "examples_mfn.html",
        {"request": request, "title": "Exemples MFN"}
    )


@router.get("/examples/fhir-bundles", response_class=HTMLResponse)
async def examples_fhir_bundles(request: Request):
    return templates.TemplateResponse(
        "examples_fhir_bundles.html",
        {"request": request, "title": "Bundles FHIR d'exemple"}
    )


@router.get("/tools/mllp", response_class=HTMLResponse)
async def tools_mllp(request: Request):
    return templates.TemplateResponse(
        "tools_mllp.html",
        {"request": request, "title": "Guide MLLP"}
    )


@router.get("/tools/endpoints-test", response_class=HTMLResponse)
async def endpoints_test_page(request: Request):
    return templates.TemplateResponse(
        "endpoints_test.html",
        {"request": request, "title": "Endpoints de test"}
    )


@router.get("/docs/{filename}", response_class=HTMLResponse)
async def docs_markdown(request: Request, filename: str):
    """Serve simple markdown files from the Doc/ folder (basic renderer)."""
    from pathlib import Path
    import markdown

    DOC_ROOT = Path(__file__).parent.parent.parent / "Doc"
    doc_path = DOC_ROOT / filename
    if not doc_path.exists():
        return templates.TemplateResponse(
            "documentation.html",
            {"request": request, "structure": {}, "error": f"Document non trouvé: {filename}", "current_doc": None}
        )
    content = doc_path.read_text(encoding="utf-8")
    html = markdown.markdown(content, extensions=["fenced_code", "tables", "toc"])
    return templates.TemplateResponse(
        "generic_doc.html",
        {"request": request, "doc_content": html, "doc_title": filename}
    )

@router.get("/standards", response_class=HTMLResponse)
async def standards_docs(
    request: Request,
    session: Session = Depends(get_session)
):
    """Page de documentation des standards supportés."""
    return templates.TemplateResponse(
        request,
        "standards_docs.html",
        {
            "title": "Documentation des standards"}
    )


@router.get("/standards-docs", response_class=HTMLResponse)
async def standards_docs_legacy(
    request: Request,
    session: Session = Depends(get_session)
):
    """Alias conservé pour compatibilité avec l'ancien chemin."""
    return await standards_docs(request, session)
