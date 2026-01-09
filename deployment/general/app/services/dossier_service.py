from sqlmodel import Session
from app.models import Dossier, DossierType

def update_dossier_type(dossier: Dossier, new_type: DossierType, session: Session) -> None:
    """
    Met à jour le type de dossier avec validation et synchronisation de la classe.
    Lève une ValueError si le changement est invalide.
    """
    if new_type == dossier.dossier_type:
        return

    _validate_and_update_type(dossier, new_type, session)

def _validate_and_update_type(dossier: Dossier, new_type: DossierType, session: Session) -> None:
    from app.utils.dossier_validators import validate_dossier_type_change
    from app.utils.dossier_helpers import sync_dossier_class
    
    can_change, warnings = validate_dossier_type_change(session, dossier, new_type)
    if not can_change:
        raise ValueError("\n".join(warnings))
        
    dossier.dossier_type = new_type
    sync_dossier_class(dossier)
    # La session est gérée par l'appelant (la route)
