"""Règles partagées du profil IHE PAM France.

Ce module est volontairement sans dépendance applicative. Il évite que le
générateur, le validateur et les interfaces utilisent des listes d'événements
ou des structures MSH-9 différentes.
"""

from __future__ import annotations

from typing import Final


# Structures ADT HL7 v2.5 employées par l'extension nationale et l'interface
# CPage. A55 appartient à la famille des annulations de changement de médecin.
MESSAGE_STRUCTURES: Final[dict[str, str]] = {
    "A01": "ADT_A01",
    "A02": "ADT_A02",
    "A03": "ADT_A03",
    "A04": "ADT_A01",
    "A05": "ADT_A05",
    "A06": "ADT_A06",
    "A07": "ADT_A06",
    "A11": "ADT_A09",
    "A12": "ADT_A12",
    "A13": "ADT_A01",
    "A15": "ADT_A15",
    "A21": "ADT_A21",
    "A22": "ADT_A21",
    "A26": "ADT_A26",
    "A28": "ADT_A05",
    "A31": "ADT_A05",
    "A38": "ADT_A38",
    "A40": "ADT_A39",
    "A44": "ADT_A43",
    "A47": "ADT_A30",
    "A52": "ADT_A52",
    "A53": "ADT_A52",
    "A54": "ADT_A54",
    "A55": "ADT_A52",
    "Z99": "ADT_A01",
}

IDENTITY_EVENTS: Final[frozenset[str]] = frozenset({"A28", "A31", "A40", "A47"})
MERGE_EVENTS: Final[frozenset[str]] = frozenset({"A40", "A47", "A44"})

# A44 est une réaffectation de compte patient : ce n'est pas un mouvement ZBE.
ZBE_FREE_EVENTS: Final[frozenset[str]] = IDENTITY_EVENTS | frozenset({"A44"})
MOVEMENT_EVENTS: Final[frozenset[str]] = frozenset(MESSAGE_STRUCTURES) - ZBE_FREE_EVENTS

# Les messages d'identité CPage les plus anciens peuvent ne pas contenir EVN.
EVN_OPTIONAL_EVENTS: Final[frozenset[str]] = IDENTITY_EVENTS

# L'extension nationale ajoute ces valeurs à la nature de mouvement.
ZBE9_NATURES: Final[frozenset[str]] = frozenset({
    "S", "H", "M", "L", "D", "SM", "SH", "MH", "LD", "HMS", "C",
})

# ZBE-9=C est réservé à la correction Z99 d'un statut de venue, sans nouveau
# mouvement, portant sur l'un des événements suivants.
ZBE9_C_ORIGINAL_EVENTS: Final[frozenset[str]] = frozenset({"A01", "A04", "A05"})

PID32_CODES: Final[frozenset[str]] = frozenset({
    "VIDE", "PROV", "VALI", "DOUB", "DESA", "DPOT", "DOUA", "COLP",
    "COLV", "FILI", "CACH", "ANOM", "IDVER", "RECD", "IDRA", "USUR",
    "HOMD", "HOMA", "INVA", "FICT", "DOUT",
})

# Segments explicitement prévus par le profil France ou HL7 v2.5 dans les
# structures ADT PAM. Cette liste sert uniquement à signaler les segments
# inconnus : elle ne rend pas les segments optionnels obligatoires.
ALLOWED_SEGMENTS: Final[frozenset[str]] = frozenset({
    "MSH", "SFT", "EVN", "PID", "PD1", "NK1", "PV1", "PV2", "MRG",
    "ROL", "ACC", "OBX", "IN1", "IN2", "IN3", "GT1", "DG1", "AL1",
    "ZBE", "ZFA", "ZFP", "ZFV", "ZFM", "ZFD", "ZFS",
    # Extensions historiques tolérées pour la compatibilité, sans les confondre
    # avec les extensions nationales actuelles.
    "ZPD", "ZIS", "ZAD",
})


def expected_structure(trigger: str) -> str | None:
    """Retourne la troisième composante MSH-9 attendue pour *trigger*."""
    return MESSAGE_STRUCTURES.get((trigger or "").upper())


def is_movement_event(trigger: str) -> bool:
    return (trigger or "").upper() in MOVEMENT_EVENTS


def format_xtn(*, number: str | None = None, use: str | None = None, equipment: str | None = None, email: str | None = None) -> str:
    """Construit un XTN HL7 v2.5 sans inverser les composants.

    Le numéro non formaté est XTN-12 ; l'adresse e-mail est XTN-4 quand
    XTN-2 vaut NET.
    """
    components = [""] * 12
    components[1] = use or ""
    components[2] = equipment or ""
    if email:
        components[3] = email
        while components and not components[-1]:
            components.pop()
    else:
        components[11] = number or ""
    return "^".join(components)


def normalize_generated_message(message: str) -> str:
    """Applique les invariants de sortie PAM France à un message ADT généré.

    Cette fonction ne fabrique pas de donnée métier : elle aligne les structures
    MSH-9, le profil/codage MSH et la représentation EI de ZBE-1, puis garantit
    que ZBE-3 reste vide comme l'impose l'annexe nationale.
    """
    if not message:
        return message
    lines = [line for line in message.replace("\r\n", "\r").replace("\n", "\r").split("\r") if line]
    trigger = ""
    for index, line in enumerate(lines):
        if line.startswith("MSH|"):
            parts = line.split("|")
            message_type = parts[8].split("^") if len(parts) > 8 else []
            trigger = message_type[1].upper() if len(message_type) > 1 else ""
            structure = expected_structure(trigger)
            if structure:
                parts[8] = f"ADT^{trigger}^{structure}"
            while len(parts) <= 17:
                parts.append("")
            parts[11] = "2.5^FRA^2.11"
            parts[16] = "FRA"  # MSH-17 (MSH-1 is the field separator)
            parts[17] = "UNICODE UTF-8"  # MSH-18
            lines[index] = "|".join(parts)
        elif line.startswith("ZBE|"):
            parts = line.split("|")
            while len(parts) <= 9:
                parts.append("")
            normalized_identifiers: list[str] = []
            for raw_identifier in filter(None, parts[1].split("~")):
                components = raw_identifier.split("^")
                # Ancien format CX : ID^^^namespace&OID&ISO^MVT.
                if len(components) > 3 and not (components[1] or components[2]) and "&" in components[3]:
                    authority = components[3].split("&")
                    namespace = authority[0] if authority else ""
                    oid = authority[1] if len(authority) > 1 else ""
                    universal_type = authority[2] if len(authority) > 2 else "ISO"
                    normalized_identifiers.append("^".join([components[0], namespace, oid, universal_type]))
                elif len(components) == 1:
                    normalized_identifiers.append(f"{components[0]}^HOSP^^")
                else:
                    normalized_identifiers.append("^".join((components + ["", "", "", ""])[:4]))
            if normalized_identifiers:
                parts[1] = "~".join(normalized_identifiers)
            parts[3] = ""  # ZBE-3 is forbidden in the national extension.
            if parts[9].upper() not in ZBE9_NATURES:
                parts[9] = "H"
            lines[index] = "|".join(parts)
    return "\r".join(lines)
