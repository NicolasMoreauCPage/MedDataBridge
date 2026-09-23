"""Constructeurs des champs ZBE spécifiques au profil PAM France."""

from app.services.nature_mapping import derive_nature

_VALID_NATURES = {"S", "H", "M", "L", "D", "SM", "SH", "MH", "LD", "HMS", "C"}


def build_xon_unit(code: str | None, label: str | None = None) -> str:
    """Construit le XON ZBE-7/ZBE-8 avec le code en composante 10."""
    if not code:
        return ""
    components = [""] * 10
    components[0] = label or code
    components[9] = code
    return "^".join(components)


def derive_zbe_nature(event_code: str, nature: str | None) -> str:
    """Retourne une nature ZBE admise, avec repli hospitalisation."""
    result = derive_nature(event_code, nature)
    return result if result in _VALID_NATURES else "H"


def movement_action_and_code(entity, event_code: str) -> tuple[str, str]:
    """Détermine ZBE-3 et ZBE-4 sans dépendance au transport ou à la base."""
    action = getattr(entity, "action", None) or "INSERT"
    code = getattr(entity, "movement_code", None) or {
        "A01": "ADMIT", "A02": "TRANSFER", "A03": "DISCHARGE", "A06": "ADMIT", "A07": "TRANSFER",
        "A11": "TRANSFER", "A12": "DELETE", "A13": "DELETE", "A31": "UPDATE", "Z99": "UPDATE",
    }.get(event_code, action)
    return action, code
