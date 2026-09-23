"""Façade de compatibilité des cas d'usage IHE PAM.

Les implémentations sont regroupées par cas d'usage dans des modules testables
indépendamment de FastAPI. Les imports ci-dessous préservent l'API historique.
"""

from app.services.pam_admission import handle_admission_message
from app.services.identifier_manager import create_identifiers_from_hl7_with_namespace_check
from app.services.medecin_extractor import extract_and_store_medecin_from_pv1
from app.services.pam_cancellations import (
    _handle_cancel_admission,
    _handle_cancel_discharge,
    _handle_cancel_transfer,
)
from app.services.pam_constants import MOVEMENT_KIND_BY_TRIGGER, MOVEMENT_STATUS_BY_TRIGGER
from app.services.pam_correlations import (
    _find_mouvement_by_movement_id,
    _identifier_tuple_for_classifier,
    validate_movement_timing,
)
from app.services.pam_discharge_handlers import (
    handle_discharge_message,
    handle_leave_message,
    handle_merge_movement_message,
)
from app.services.pam_extensions import (
    _apply_french_extension_segments_to_patient,
    _apply_zfv_to_mouvement,
)
from app.services.pam_intake import (
    _extract_pv1_segment,
    _parse_zbe_segment,
    generate_pam_messages_for_dossier,
    process_pam_message,
)
from app.services.pam_transfer_handlers import (
    handle_doctor_message,
    handle_move_account_message,
    handle_transfer_message,
)

__all__ = [
    "MOVEMENT_KIND_BY_TRIGGER",
    "MOVEMENT_STATUS_BY_TRIGGER",
    "_apply_french_extension_segments_to_patient",
    "_apply_zfv_to_mouvement",
    "_extract_pv1_segment",
    "_find_mouvement_by_movement_id",
    "_handle_cancel_admission",
    "_handle_cancel_discharge",
    "_handle_cancel_transfer",
    "_identifier_tuple_for_classifier",
    "_parse_zbe_segment",
    "generate_pam_messages_for_dossier",
    "handle_admission_message",
    "handle_discharge_message",
    "handle_doctor_message",
    "handle_leave_message",
    "handle_merge_movement_message",
    "handle_move_account_message",
    "handle_transfer_message",
    "process_pam_message",
    "validate_movement_timing",
    "create_identifiers_from_hl7_with_namespace_check",
    "extract_and_store_medecin_from_pv1",
]
