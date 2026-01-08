"""Router pour la documentation des standards."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi import Request as FastAPIRequest
from sqlmodel import Session

from ..db import get_session


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter()

# Additional resource pages for Exemple/tools used by the UI "Ressources" menu


@router.get("/examples/hl7v2", response_class=HTMLResponse)
async def examples_hl7v2(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        "examples_hl7v2.html",
        {"request": request, "title": "Exemples HL7 v2"}
    )


@router.get("/examples/mfn", response_class=HTMLResponse)
async def examples_mfn(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        "examples_mfn.html",
        {"request": request, "title": "Exemples MFN"}
    )


@router.get("/examples/fhir-bundles", response_class=HTMLResponse)
async def examples_fhir_bundles(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        "examples_fhir_bundles.html",
        {"request": request, "title": "Bundles FHIR d'exemple"}
    )


@router.get("/tools/mllp", response_class=HTMLResponse)
async def tools_mllp(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        "tools_mllp.html",
        {"request": request, "title": "Guide MLLP"}
    )


@router.get("/tools/endpoints-test", response_class=HTMLResponse)
async def endpoints_test_page(request: Request):
    return get_templates_with_filters(request).TemplateResponse(
        "endpoints_test.html",
        {"request": request, "title": "Endpoints de test"}
    )


@router.get("/docs/{filename}", response_class=HTMLResponse)
async def docs_markdown(request: Request, filename: str):
    """Serve simple markdown files from the docs/ folder (basic renderer)."""
    from pathlib import Path
    import markdown
    import re

    DOC_ROOT = Path(__file__).parent.parent.parent / "docs"
    doc_path = DOC_ROOT / filename
    if not doc_path.exists():
        return get_templates_with_filters(request).TemplateResponse(
            "documentation.html",
            {"request": request, "structure": {}, "error": f"Document non trouvé: {filename}", "current_doc": None}
        )

    # Prefer a pre-generated HTML file if present (same base name .html)
    html_equiv = doc_path.with_suffix('.html')
    if html_equiv.exists():
        # If a static HTML exists, prefer to redirect to it so the static file
        # is served directly (preserves full HTML rendering produced by pandoc).
        from fastapi.responses import RedirectResponse
        static_url = request.url_for('doc') if False else f"/docs/{html_equiv.name}"
        return RedirectResponse(url=static_url)

    # Otherwise render markdown on the fly
    content = doc_path.read_text(encoding="utf-8")
    html = markdown.markdown(content, extensions=["fenced_code", "tables", "toc"])
    return get_templates_with_filters(request).TemplateResponse(
        "generic_doc.html",
        {"request": request, "doc_content": html, "doc_title": filename}
    )

@router.get("/standards", response_class=HTMLResponse)
async def standards_docs(
    request: Request,
    session: Session = Depends(get_session)
):
    """Page de documentation des standards supportés."""
    return get_templates_with_filters(request).TemplateResponse(
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
