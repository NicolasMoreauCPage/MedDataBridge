"""Classification fonctionnelle des scénarios HL7 v2.

IHE PAM France couvre les messages ADT de gestion administrative du patient.
Les messages SIU^Sxx relèvent, eux, du domaine *Scheduling* de HL7 v2 et ne
doivent jamais être présentés ou qualifiés comme des scénarios PAM.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


def is_siu_message(message_type: str | None, payload: str | None = None) -> bool:
    """Indique si un message HL7 v2 appartient à la famille SIU.

    Les exports historiques renseignent parfois ``S12`` au lieu de
    ``SIU^S12`` dans le type de message. Le MSH-9 reste la source de vérité,
    avec ce second format comme compatibilité d'import.
    """
    value = (message_type or "").strip().upper()
    if value.startswith("SIU^") or value == "SIU":
        return True
    if re.fullmatch(r"S\d{2}", value):
        return True

    msh = (payload or "").replace("\\r", "\r").replace("\n", "\r").split("\r", 1)[0]
    fields = msh.split("|")
    return bool(fields and fields[0] == "MSH" and len(fields) > 8 and fields[8].upper().startswith("SIU^"))


def classify_hl7_scenario(steps: Iterable[Any]) -> str | None:
    """Retourne ``siu`` ou ``mixed_siu`` si le scénario contient du SIU.

    ``None`` signifie qu'aucun message SIU n'est présent. Les objets fournis
    peuvent être des dictionnaires d'import ou des modèles SQLModel.
    """
    hl7_steps: list[Any] = []
    siu_steps: list[Any] = []
    for step in steps:
        fmt = step.get("message_format") if isinstance(step, dict) else getattr(step, "message_format", None)
        if (fmt or "hl7").lower() != "hl7":
            continue
        hl7_steps.append(step)
        message_type = step.get("message_type") if isinstance(step, dict) else getattr(step, "message_type", None)
        payload = step.get("payload") if isinstance(step, dict) else getattr(step, "payload", None)
        if is_siu_message(message_type, payload):
            siu_steps.append(step)
    if not siu_steps:
        return None
    return "siu" if len(siu_steps) == len(hl7_steps) else "mixed_siu"
