"""Router pour envelopper les docs HTML statiques du dossier /Doc avec le template base.html

Ce routeur intercepte les fichiers HTML du dossier /Doc et les enveloppe dans
le template base.html pour qu'ils aient le bandeau, le menu et le style du programme.

Les fichiers non-HTML (images, etc.) sont servis directement sans enveloppe.
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi import Request as FastAPIRequest
from pathlib import Path
import logging
import mimetypes


def get_templates_with_filters(request: FastAPIRequest):
    """Retourne l'instance templates globale avec les filtres enregistrés"""
    return request.app.state.templates

router = APIRouter()
logger = logging.getLogger(__name__)

DOC_ROOT = Path(__file__).parent.parent.parent / "Doc"


@router.get("/Doc/{file_path:path}", response_class=HTMLResponse)
async def serve_wrapped_doc(request: Request, file_path: str):
    """
    Enveloppe les fichiers HTML du dossier /Doc avec le template base.html.
    Fichiers non-HTML sont servis directement.
    
    Cela garantit que tous les documents HTML ont:
    - Le bandeau avec le logo et le contexte
    - Le menu de navigation complet
    - Le style cohérent du programme (Tailwind, thème, etc.)
    
    Args:
        request: Requête FastAPI
        file_path: Chemin du fichier depuis /Doc
    
    Returns:
        HTMLResponse avec le fichier HTML enveloppé dans base.html,
        ou FileResponse pour les fichiers non-HTML
    """
    # Sécurité: éviter les path traversal
    if ".." in file_path:
        return HTMLResponse(content="<p>Accès non autorisé</p>", status_code=403)
    
    doc_file = DOC_ROOT / file_path
    
    # Vérifier que le fichier existe et est dans le répertoire /Doc
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
    
    # Fichiers non-HTML: servir directement (images, CSS, JS, etc.)
    if not file_path.lower().endswith('.html'):
        return FileResponse(doc_file)
    
    # Fichiers HTML: envelopper dans le template
    try:
        content = doc_file.read_text(encoding="utf-8")
        
        # Extraire le titre du fichier HTML s'il existe
        import re
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
        title = title_match.group(1) if title_match else file_path
        
        # Envelopper le contenu HTML dans le template base.html
        return get_templates_with_filters(request).TemplateResponse(
            "doc_wrapper.html",
            {
                "request": request,
                "doc_title": title,
                "doc_content": content,
                "doc_filename": file_path
            }
        )
    except Exception as e:
        logger.error(f"Error serving doc {file_path}: {e}")
        return HTMLResponse(
            content=f"<p>Erreur de lecture: {e}</p>",
            status_code=500
        )
