"""Résolution des autorités d'identifiants pour les messages PAM."""

import logging

from sqlmodel import Session, select

from app.models_structure import IdentifierNamespace

logger = logging.getLogger(__name__)


def resolve_namespace_authority(
    session: Session,
    entite_juridique_id: int | None,
    namespace_type: str,
    forced_system: str | None = None,
    forced_oid: str | None = None,
) -> tuple[str, str]:
    """Retourne l'autorité HL7 et le type de namespace demandés.

    Les valeurs forcées de l'endpoint priment comme solution de repli lorsque
    l'établissement ne possède pas de namespace actif.
    """
    def authority(system: str | None, oid: str | None) -> str:
        system = (system or "").strip()
        oid = (oid or "").strip()
        return f"{system}&{oid}&ISO" if system and oid else system or ""

    if entite_juridique_id:
        try:
            namespace = session.exec(
                select(IdentifierNamespace)
                .where(IdentifierNamespace.entite_juridique_id == entite_juridique_id)
                .where(IdentifierNamespace.type == namespace_type)
                .where(IdentifierNamespace.is_active.is_(True))
            ).first()
            if namespace:
                return authority(namespace.system, namespace.oid), namespace.type or namespace_type
        except Exception:
            logger.exception(
                "Erreur de résolution du namespace %s pour EJ %s", namespace_type, entite_juridique_id
            )

    return authority(forced_system, forced_oid) or (forced_system or "HOSP"), namespace_type
