"""
Module admin - Vues SQLAdmin organisées

Ce module expose toutes les vues admin SQLAdmin de manière organisée.
Import unique depuis app.py: from app.admin import register_admin_views
"""
from .clinical import PatientAdmin, DossierAdmin, VenueAdmin, MouvementAdmin
from .structure import (
    PoleAdmin, ServiceAdmin, UniteFonctionnelleAdmin, UFActivityAdmin,
    UniteHebergementAdmin, ChambreAdmin, LitAdmin
)
from .context import GHTContextAdmin, EntiteJuridiqueAdmin, EntiteGeographiqueAdmin
from .vocabulary import VocabularySystemAdmin, VocabularyValueAdmin
from .identifiers import IdentifierAdmin, NamespaceAdmin
from .connectivity import SystemEndpointAdmin, MessageLogAdmin
from .scenarios import InteropScenarioAdmin, InteropScenarioStepAdmin, ScenarioTemplateAdmin, ScenarioTemplateStepAdmin


def register_admin_views(admin):
    """
    Enregistre toutes les vues admin dans l'instance SQLAdmin.
    Ordre optimisé pour navigation logique par domaine métier.
    
    Args:
        admin: Instance sqladmin.Admin
    """
    # === 1. CONTEXTES ORGANISATIONNELS ===
    admin.add_view(GHTContextAdmin)
    admin.add_view(EntiteJuridiqueAdmin)
    admin.add_view(EntiteGeographiqueAdmin)

    # === 2. STRUCTURE ORGANISATIONNELLE (hiérarchie) ===
    admin.add_view(PoleAdmin)
    admin.add_view(ServiceAdmin)
    admin.add_view(UniteFonctionnelleAdmin)
    admin.add_view(UFActivityAdmin)
    admin.add_view(UniteHebergementAdmin)
    admin.add_view(ChambreAdmin)
    admin.add_view(LitAdmin)

    # === 3. CLINIQUE ===
    admin.add_view(PatientAdmin)
    admin.add_view(DossierAdmin)
    admin.add_view(VenueAdmin)
    admin.add_view(MouvementAdmin)

    # === 4. IDENTIFIANTS ===
    admin.add_view(IdentifierAdmin)
    admin.add_view(NamespaceAdmin)

    # === 5. VOCABULAIRES ===
    admin.add_view(VocabularySystemAdmin)
    admin.add_view(VocabularyValueAdmin)

    # === 6. CONNECTIVITÉ ===
    admin.add_view(SystemEndpointAdmin)
    admin.add_view(MessageLogAdmin)

    # === 7. SCÉNARIOS ===
    admin.add_view(InteropScenarioAdmin)
    admin.add_view(InteropScenarioStepAdmin)
    admin.add_view(ScenarioTemplateAdmin)
    admin.add_view(ScenarioTemplateStepAdmin)

__all__ = [
    'register_admin_views',
    'PatientAdmin', 'DossierAdmin', 'VenueAdmin', 'MouvementAdmin',
    'GHTContextAdmin', 'EntiteJuridiqueAdmin', 'EntiteGeographiqueAdmin',
    'PoleAdmin', 'ServiceAdmin', 'UniteFonctionnelleAdmin', 'UFActivityAdmin',
    'UniteHebergementAdmin', 'ChambreAdmin', 'LitAdmin',
    'SystemEndpointAdmin', 'MessageLogAdmin',
    'IdentifierAdmin', 'NamespaceAdmin',
    'VocabularySystemAdmin', 'VocabularyValueAdmin',
    'InteropScenarioAdmin', 'InteropScenarioStepAdmin',
    'ScenarioTemplateAdmin', 'ScenarioTemplateStepAdmin',
]
