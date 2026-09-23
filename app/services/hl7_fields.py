"""Constructeurs purs de champs composites HL7 v2."""

from app.services.pam_emission_primitives import clean_hl7_value


def build_xpn(
    family: str | None,
    given: str | None,
    middle: str | None = None,
    suffix: str | None = None,
    prefix: str | None = None,
    name_type: str | None = None,
) -> str:
    """Construit un XPN et retire uniquement ses composants finaux vides."""
    components = [family or "", given or "", middle or "", suffix or "", prefix or "", "", name_type or ""]
    while components and not components[-1]:
        components.pop()
    return "^".join(components)


def build_patient_name(
    family: str | None,
    given: str | None,
    middle: str | None = None,
    suffix: str | None = None,
    prefix: str | None = None,
    birth_family: str | None = None,
) -> str:
    """Construit PID-5, avec un nom de naissance légal distinct si nécessaire."""
    birth_family = clean_hl7_value(birth_family) or None
    legal_current_name = bool(birth_family and birth_family == family)
    current_type = "L" if legal_current_name else "D" if birth_family else None
    names = []
    if any((family, given, middle, suffix, prefix)):
        names.append(build_xpn(family, given, middle, suffix, prefix, current_type))
    if birth_family and not legal_current_name:
        names.append(build_xpn(birth_family, given, middle, suffix, prefix, "L"))
    return "~".join(names)


def build_xad(
    street: str | None,
    other: str | None,
    city: str | None,
    state: str | None,
    postal_code: str | None,
    country: str | None,
    address_type: str | None = None,
) -> str:
    """Construit une adresse XAD sans composants finaux inutiles."""
    components = [street or "", other or "", city or "", state or "", postal_code or "", country or ""]
    if address_type:
        components.append(address_type)
    while components and not components[-1]:
        components.pop()
    return "^".join(components)
