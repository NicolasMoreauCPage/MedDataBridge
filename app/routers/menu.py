from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get('/menu', response_class=HTMLResponse)
async def menu_page(request: Request):
    # Static mapping — keep in sync with docs/MENU_MAP.md
    menu = {
        'Structure': [
            {'label': 'Tableau structurel', 'url': '/structure'},
            {'label': 'Contexts GHT', 'url': '/admin/ght'},
            {'label': 'Recherche avancée', 'url': '/structure/search'},
        ],
        'Activités': [
            {'label': 'Patients', 'url': '/patients'},
            {'label': 'Dossiers & Cotation', 'url': '/dossiers'},
            {'label': 'Venues', 'url': '/venues'},
            {'label': 'Mouvements', 'url': '/mouvements'},
        ],
        'Interopérabilité': [
            {'label': 'Messages', 'url': '/messages'},
            {'label': 'Scénarios IHE PAM', 'url': '/scenarios'},
            {'label': 'Endpoints', 'url': '/endpoints'},
        ],
        'Ressources': [
            {'label': 'Guide utilisateur', 'url': '/guide'},
            {'label': 'Documentation API', 'url': '/api-docs'},
            {'label': 'FHIR (spec)', 'url': 'https://www.hl7.org/fhir/'},
        ],
        'Administration': [
            {'label': 'Administration', 'url': '/sqladmin'},
            {'label': 'Vocabularies', 'url': '/vocabularies'},
        ]
    }
    return request.app.state.templates.TemplateResponse('menu.html', {'request': request, 'menu': menu})
