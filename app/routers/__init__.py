# BUGFIX: Le module ght est exclu de __init__.py car il y a un problème d'import
# circulaire qui empêche le chargement complet de ses routes. Il est importé
# directement dans app/app.py à la place.
# TODO: Investiguer et résoudre la vraie cause de l'import circulaire

from app.routers.home import router as home_router
from app.routers.messages import router as messages_router
from app.routers.endpoints import router as endpoints_router
from app.routers.transport import router as transport_router
from app.routers.transport_views import router as transport_views_router
from app.routers.fhir_inbox import router as fhir_inbox_router
from app.routers.messages import router as messages_router
from app.routers.patients import router as patients_router
from app.routers.dossiers import router as dossiers_router
from app.routers.venues import router as venues_router
from app.routers.mouvements import router as mouvements_router
from app.routers.structure_hl7 import router as structure_hl7_router
from app.routers.fhir_structure import router as fhir_structure_router
from app.routers.structure import router as structure_router
from app.routers.workflow import router as workflow_router
from app.routers.generate import router as generate_router
from app.routers.interop import router as interop_router
from app.routers.vocabularies import router as vocabularies_router
# from app.routers.ght import router as ght_router  # DÉSACTIVÉ - voir commentaire ci-dessus
from app.routers.namespaces import router as namespaces_router
from app.routers.guide import router as guide_router
from app.routers.scenarios import router as scenarios_router
from app.routers.scenario_templates import router as scenario_templates_router
from app.routers.ihe import router as ihe_router
from app.routers.docs import router as docs_router
from app.routers.dossier_type import router as dossier_type_router
from app.routers.timeline import router as timeline_router
