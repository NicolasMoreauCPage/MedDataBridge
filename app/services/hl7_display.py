"""Projection sûre et lisible d'un message HL7 v2 pour les IHM.

Le validateur conserve toujours le message source. Cette projection ne le
modifie pas : elle fournit seulement une arborescence segments/champs/
répétitions/composants, afin qu'un intégrateur puisse relier un diagnostic à
la donnée qui l'a déclenché.
"""
from __future__ import annotations

from typing import Any


FIELD_LABELS: dict[str, dict[int, str]] = {
    "MSH": {
        1: "Séparateur de champ", 2: "Caractères d'encodage", 3: "Application émettrice",
        4: "Établissement émetteur", 5: "Application destinataire", 6: "Établissement destinataire",
        7: "Date/heure", 9: "Type de message", 10: "Identifiant de contrôle", 11: "Mode de traitement",
        12: "Version/profil", 17: "Pays", 18: "Jeu de caractères",
    },
    "EVN": {1: "Code événement", 2: "Date/heure de l'événement"},
    "PID": {3: "Liste des identifiants", 5: "Nom", 7: "Date de naissance", 8: "Sexe", 11: "Adresse", 13: "Téléphone", 19: "NIR", 32: "Fiabilité de l'identité"},
    "PV1": {2: "Classe patient", 3: "Localisation", 7: "Médecin responsable", 19: "Numéro de venue", 44: "Date/heure d'admission", 45: "Date/heure de sortie"},
    "MRG": {1: "Identifiant patient antérieur"},
    "ZBE": {1: "Identifiant mouvement", 2: "Date/heure mouvement", 3: "Champ interdit", 4: "Action", 5: "Historique", 6: "Événement d'origine", 7: "UF médicale", 8: "UF soins", 9: "Nature de venue"},
    "NK1": {2: "Nom", 3: "Lien", 4: "Adresse", 5: "Téléphone", 6: "Téléphone professionnel", 7: "Rôle"},
}


def _component_view(value: str) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "value": component,
            "subcomponents": [
                {"index": sub_index, "value": subcomponent}
                for sub_index, subcomponent in enumerate(component.split("&"), start=1)
            ] if "&" in component else [],
        }
        for index, component in enumerate(value.split("^"), start=1)
    ]


def build_hl7_view(message: str) -> list[dict[str, Any]]:
    """Construit une vue complète des champs non vides d'un message HL7 v2."""
    lines = [line for line in (message or "").replace("\r\n", "\r").replace("\n", "\r").split("\r") if line]
    view: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        segment, *raw_fields = line.split("|")
        if not segment:
            continue
        fields: list[dict[str, Any]] = []
        if segment == "MSH":
            raw_fields.insert(0, "|")
        labels = FIELD_LABELS.get(segment, {})
        for field_number, value in enumerate(raw_fields, start=1):
            if not value:
                continue
            repetitions = [
                {"index": repeat_index, "value": repeat, "components": _component_view(repeat)}
                for repeat_index, repeat in enumerate(value.split("~"), start=1)
            ]
            fields.append({
                "number": field_number,
                "location": f"{segment}-{field_number}",
                "label": labels.get(field_number, "Champ HL7"),
                "value": value,
                "repetitions": repetitions,
            })
        view.append({"name": segment, "line": line_number, "raw": line, "fields": fields})
    return view

