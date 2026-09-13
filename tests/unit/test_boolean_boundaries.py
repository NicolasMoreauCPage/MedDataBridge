"""Contrat de représentation des booléens métier."""

from datetime import datetime
from types import SimpleNamespace

from sqlmodel import Session

from app.models import Dossier, Patient
from app.routers.hprim_messages import _import_one_lpp, _import_one_ucd
from app.services.scenario_import import validate_scenario_json
from app.utils.booleans import as_bool


def test_as_bool_accepts_supported_input_representations() -> None:
    assert all(as_bool(value) for value in (True, 1, "true", "TRUE", "oui", "on", "yes"))
    assert not any(as_bool(value) for value in (False, 0, None, "false", "non", "off", "trd", "ec"))


def test_scenario_import_keeps_boolean_and_event_list_types_distinct() -> None:
    scenario = {
        "key": "boolean-contract",
        "name": "Contrat booléen",
        "protocol": "HL7",
        "steps": [{"order_index": 1, "message_type": "ADT^A01", "payload": "MSH|^~\\&"}],
        "time_config": {"preserve_intervals": True, "jitter_events": ["A02", "A03"]},
    }

    assert validate_scenario_json(scenario) == (True, None)

    scenario["time_config"]["jitter_events"] = True
    valid, error = validate_scenario_json(scenario)
    assert not valid
    assert "jitter_events" in (error or "")


def test_hprim_ucd_and_lpp_import_preserve_boolean_statuses(session: Session) -> None:
    patient = Patient(identifier="BOOL-PATIENT", nom="TEST", prenom="BOOL", date_naissance="1980-01-01", sexe="F")
    session.add(patient)
    session.commit()
    session.refresh(patient)
    dossier = Dossier(patient_id=patient.id, dossier_seq=98001, admit_time=datetime.now(), current_state="OPEN")
    session.add(dossier)
    session.commit()
    session.refresh(dossier)

    ucd = _import_one_ucd(
        session,
        dossier,
        SimpleNamespace(
            code_ucd="3400935001324",
            denomination_libelle="Produit UCD",
            execute_date=datetime(2026, 1, 2, 10, 0),
            quantite=1,
            montant_unitaire_facture_ttc=12.5,
            valide="oui",
            facture="oui",
        ),
    )
    lpp = _import_one_lpp(
        session,
        dossier,
        SimpleNamespace(
            code_lpp="1234567890123",
            denomination_libelle="Produit LPP",
            execute_date=datetime(2026, 1, 3, 10, 0),
            quantite=1,
            montant_unitaire_facture_ttc=7.5,
            valide="oui",
            facture="oui",
        ),
    )

    assert ucd is not None and ucd.valide is True and ucd.facture is True
    assert lpp is not None and lpp.valide is True and lpp.facture is True
