"""Router pour la documentation des standards."""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
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


@router.get("/docs/changelog", response_class=HTMLResponse)
async def changelog(request: Request):
    """Affiche le changelog de l'application (redirige vers /docs/CHANGELOG.md)."""
    return RedirectResponse(url="/docs/CHANGELOG.md")


@router.get("/docs/{filename}", response_class=HTMLResponse)
async def docs_markdown(request: Request, filename: str):
    """Serve simple markdown files from the docs/ folder.

    This endpoint now uses the shared `doc_wrapper.html` so that Markdown
    rendering is consistent with other documentation paths. It extracts the
    first ATX H1 ("# Title") as the document title and removes it from the
    rendered content to avoid duplicate titles in the banner.
    """
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

    # Prefer a pre-generated HTML file if present (same base name .html).
    # Only redirect when the original request is for a Markdown file
    # (avoid redirecting when the requested filename already is .html,
    # which caused a self-redirect loop).
    html_equiv = doc_path.with_suffix('.html')
    if filename.lower().endswith('.md') and html_equiv.exists():
        static_url = f"/docs/{html_equiv.name}"
        return RedirectResponse(url=static_url)

    # Read raw content and, for Markdown, extract first H1 as title
    raw = doc_path.read_text(encoding="utf-8")
    doc_title = None
    content_raw = raw
    if filename.lower().endswith('.md'):
        m = re.search(r'^[ \t]*#\s+(.+)$', raw, flags=re.MULTILINE)
        if m:
            doc_title = m.group(1).strip()
            # remove first H1 line and a following blank line if present
            content_raw = re.sub(r'^[ \t]*#\s+(.+)\n?', '', raw, count=1, flags=re.MULTILINE)
            content_raw = re.sub(r'^\n', '', content_raw, count=1)

    # Render markdown to HTML
    html = markdown.markdown(content_raw, extensions=["fenced_code", "tables", "toc", "nl2br", "extra"]) if filename.lower().endswith('.md') else raw

    # Fallback title if none extracted
    if not doc_title:
        doc_title = Path(filename).stem.replace('_', ' ').title()

    return get_templates_with_filters(request).TemplateResponse(
        "doc_wrapper.html",
        {"request": request, "doc_content": html, "doc_title": doc_title, "doc_filename": filename}
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
