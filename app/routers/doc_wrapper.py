"""Router pour envelopper les docs HTML et Markdown statiques du dossier /docs avec le template base.html.

Ce routeur intercepte les fichiers HTML et Markdown du dossier /docs et les enveloppe dans
le template base.html pour qu'ils aient le bandeau, le menu et le style du programme.

Les fichiers non-HTML/Markdown (images, etc.) sont servis directement sans enveloppe.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi import Request as FastAPIRequest
from pathlib import Path
import logging
import mimetypes
import markdown


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates


router = APIRouter()
logger = logging.getLogger(__name__)

DOC_ROOT = Path(__file__).parent.parent.parent / "docs"


@router.get("/docs/{file_path:path}", response_class=HTMLResponse)
async def serve_wrapped_doc(request: Request, file_path: str):
    """
    Enveloppe les fichiers HTML et Markdown du dossier /docs avec le template base.html.
    Fichiers non-HTML/Markdown sont servis directement.

    Pour les fichiers Markdown, on extrait le premier H1 (ligne commençant par "# ")
    et l'utilise comme titre (`doc_title`). Cette ligne est retirée du contenu rendu
    pour éviter la duplication (titre en bandeau + H1 dans le contenu).
    """
    # Sécurité: éviter les path traversal
    if ".." in file_path:
        return HTMLResponse(content="<p>Accès non autorisé</p>", status_code=403)

    doc_file = DOC_ROOT / file_path

    # Vérifier que le fichier existe et est dans le répertoire /docs
    try:
        doc_file = doc_file.resolve()
        DOC_ROOT_resolved = DOC_ROOT.resolve()
        if not str(doc_file).startswith(str(DOC_ROOT_resolved)):
            return HTMLResponse(content="<p>Fichier non trouvé</p>", status_code=404)
    except Exception as e:
        logger.error(f"Path resolution error for {file_path}: {e}")
        return HTMLResponse(content="<p>Fichier non trouvé</p>", status_code=404)

    # Vérifier l'existence du fichier
    if not doc_file.exists():
        return HTMLResponse(content="<p>Fichier non trouvé</p>", status_code=404)

    # Fichiers non-HTML/Markdown: servir directement (images, CSS, JS, etc.)
    if not (file_path.lower().endswith('.html') or file_path.lower().endswith('.md')):
        return FileResponse(doc_file)

    # Fichiers HTML ou Markdown: envelopper dans le template
    try:
        raw = doc_file.read_text(encoding="utf-8")

        # Si Markdown: extraire le premier H1 du texte source et le retirer
        doc_title = None
        content_html = raw
        if file_path.lower().endswith('.md'):
            import re
            # Cherche un titre ATX (# Title) au début du document (première occurrence)
            m = re.search(r'^[ \t]*#\s+(.+)$', raw, flags=re.MULTILINE)
            if m:
                doc_title = m.group(1).strip()
                # Enlever la ligne de titre et une éventuelle ligne vide suivante
                content_without_title = re.sub(r'^[ \t]*#\s+(.+)\n?', '', raw, count=1, flags=re.MULTILINE)
                # retirer une seule ligne vide immédiatement après si présente
                content_without_title = re.sub(r'^\n', '', content_without_title, count=1)
                raw = content_without_title

            # Configuration Markdown avec extensions utiles
            md_extensions = [
                'toc', 'fenced_code', 'codehilite', 'tables', 'nl2br', 'extra'
            ]
            content_html = markdown.markdown(raw, extensions=md_extensions)
            content_html = f'<div class="prose prose-slate max-w-none">{content_html}</div>'
        else:
            # HTML file: use content as is and try to extract <title>
            content_html = raw
            import re
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', content_html, re.IGNORECASE)
            if title_match:
                doc_title = title_match.group(1).strip()

        # Fallback title: nicest form of file name
        if not doc_title:
            doc_title = Path(file_path).stem.replace('_', ' ').title()

        # Envelopper le contenu HTML dans le template base.html
        return get_templates_with_filters(request).TemplateResponse(
            "doc_wrapper.html",
            {
                "request": request,
                "doc_title": doc_title,
                "doc_content": content_html,
                "doc_filename": file_path
            }
        )
    except Exception as e:
        logger.error(f"Error serving doc {file_path}: {e}")
        return HTMLResponse(
            content=f"<p>Erreur de lecture: {e}</p>",
            status_code=500
        )
