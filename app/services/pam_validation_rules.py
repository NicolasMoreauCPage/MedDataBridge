"""Configuration des règles structurelles du validateur IHE PAM."""
from __future__ import annotations

import logging
import os
from typing import Set

from app.services.pam_profile_fr import IDENTITY_EVENTS, MOVEMENT_EVENTS

logger = logging.getLogger(__name__)

# Les listes optionnelles ne sont pas exhaustives : elles servent à l'information
# et à l'ordre, jamais à interdire les segments HL7 v2.5 prévus par le profil.
EXTENDED_MODE = os.getenv("ENABLE_PAM_EXT", "0") in {"1", "true", "True"}

SEGMENT_RULES = {
    **{
        event: {"required": ["MSH", "EVN", "PID", "PV1"], "optional": ["PD1", "NK1", "PV2", "ROL", "ACC", "OBX", "IN1", "IN2", "IN3", "GT1", "ZFA", "ZFP", "ZFV", "ZFM", "ZFD", "ZFS", "ZBE"]}
        for event in MOVEMENT_EVENTS
        if event != "A44"
    },
    "A28": {"required": ["MSH", "PID"], "optional": ["EVN", "PD1", "NK1", "PV1", "PV2", "ROL", "ZFA", "ZFP", "ZFD"]},
    "A31": {"required": ["MSH", "PID"], "optional": ["EVN", "PD1", "NK1", "PV1", "PV2", "ROL", "ZFA", "ZFP", "ZFD"]},
    "A40": {"required": ["MSH", "PID", "MRG"], "optional": ["EVN", "PD1", "NK1", "ROL", "ZFA", "ZFP", "ZFD"]},
    "A47": {"required": ["MSH", "PID", "MRG"], "optional": ["EVN", "PD1", "ROL", "ZFA", "ZFP", "ZFD"]},
    "A44": {"required": ["MSH", "EVN", "PID", "MRG"], "optional": ["PD1", "PV1", "PV2", "ROL", "ZFA", "ZFP", "ZFD"]},
}

# Events that are identity-only in IHE PAM; PV1 is optional
IDENTITY_ONLY = set(IDENTITY_EVENTS)

# Events which normally require a PV1 (visit context)
REQUIRE_PV1 = {
    event for event in MOVEMENT_EVENTS if event != "A44"
}

# Exception d'interopérabilité limitée aux messages entrants CPage observés
# dans le corpus. Certaines versions concatènent à tort le marqueur ``C`` à
# ZBE-9 (ex. MHC, MC, HMSC). Cette donnée reste non conforme sur le fil ; elle
# est normalisée pour appliquer les règles métier, avec un avertissement
# traçable plutôt qu'un rejet technique de tout le message.
CPAGE_ZBE9_SUFFIX_BUG_VALUES = frozenset({"MC", "MHC", "HMSC"})


def _normalize_cpage_zbe9(value: str, *, sending_app: str, trigger: str) -> str:
    """Retourne l'interprétation nationale d'une variante CPage connue."""
    normalized = (value or "").strip().upper()
    if sending_app == "CPAGE" and normalized in CPAGE_ZBE9_SUFFIX_BUG_VALUES:
        return "C" if trigger == "Z99" else normalized[:-1]
    return normalized
if os.getenv("STRICT_PAM_FR", "0") in {"1", "true", "True"}:
    REQUIRE_PV1 = {e for e in REQUIRE_PV1 if e != "A08"}

# PID-13 XTN validation configuration
# - PID13_STRICT=1 enables stricter validation for PID-13 fields (non-default)
# - PID13_ALLOW_USES / PID13_ALLOW_EQUIP can list comma-separated exceptions to accept
PID13_STRICT = os.getenv("PID13_STRICT", "1") in {"1", "true", "True"}
_pid13_allow_uses_env = os.getenv("PID13_ALLOW_USES", "")
_pid13_allow_equip_env = os.getenv("PID13_ALLOW_EQUIP", "")
PID13_ALLOW_USES = {v.strip() for v in _pid13_allow_uses_env.split(",") if v.strip()}
PID13_ALLOW_EQUIP = {v.strip() for v in _pid13_allow_equip_env.split(",") if v.strip()}

# Ordre attendu des segments principaux selon HAPI structures
# Format: liste ordonnée des segments (requis et optionnels)
SEGMENT_ORDER = {
    "A01": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A03": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A04": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A05": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A06": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A07": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A08": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A11": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "Z99": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A12": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A13": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A21": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A22": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A23": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A52": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A53": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A28": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A31": ["MSH", "EVN", "PID", "PD1", "NK1", "PV1", "PV2"],
    "A40": ["MSH", "EVN", "PID", "PD1", "NK1", "MRG"],
    "A47": ["MSH", "EVN", "PID", "PD1", "MRG"],
}

# Aucun segment HL7 v2.5 standard n'est interdit globalement : son autorisation
# dépend de l'événement et de sa cardinalité. Les champs interdits sont contrôlés
# à leur emplacement (PID-19, ZBE-3, ZFV-3, ...).
FORBIDDEN_PAM_SEGMENTS: Set[str] = set()


def load_custom_segment_rules(file_path: str | None = None) -> None:
    """Charge des règles personnalisées depuis un fichier JSON et fusionne
    avec les règles par défaut en mémoire. Le fichier attendu est un objet JSON
    dont les clés sont les triggers (ex: "A01") et les valeurs des maps similaires
    à SEGMENT_RULES (required/optional) et/ou une clé "segment_order".
    """
    import json
    from pathlib import Path

    data_dir = Path(__file__).parent.parent / "data"
    path = Path(file_path) if file_path else data_dir / "pam_custom_rules.json"
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return
        for trigger, rules in payload.items():
            try:
                if not isinstance(rules, dict):
                    continue
                # Merge required/optional lists
                req = rules.get("required")
                opt = rules.get("optional")
                if req or opt:
                    SEGMENT_RULES[trigger] = {
                        "required": list(req) if isinstance(req, list) else SEGMENT_RULES.get(trigger, {}).get("required", []),
                        "optional": list(opt) if isinstance(opt, list) else SEGMENT_RULES.get(trigger, {}).get("optional", []),
                    }
                # Merge segment order if provided
                seg_order = rules.get("segment_order") or rules.get("order")
                if seg_order and isinstance(seg_order, list):
                    SEGMENT_ORDER[trigger] = list(seg_order)
            except Exception:
                continue
    except Exception:
        return


# Attempt to load custom rules at import time if file exists
try:
    load_custom_segment_rules()
except Exception as exc:
    logger.debug("Optional operation skipped", exc_info=exc)
