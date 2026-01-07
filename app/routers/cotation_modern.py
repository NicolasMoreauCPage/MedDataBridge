"""
Module moderne de cotation (stub).
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Cotation Modern"])

@router.get("/", response_class=HTMLResponse)
async def cotation_modern_dashboard(request: Request):
    """Page d'accueil du module de cotation moderne (stub)."""
    return """
    <html>
    <head>
        <title>Cotation Moderne - Placeholder</title>
        <style>
            body { font-family: sans-serif; padding: 20px; }
            .placeholder { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Module de Cotation Moderne</h1>
        <div class="placeholder">
            <p>Ce module est en cours de développement.</p>
            <p><a href="/">Retour à l'accueil</a></p>
        </div>
    </body>
    </html>
    """
