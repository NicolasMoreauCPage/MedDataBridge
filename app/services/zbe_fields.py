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
