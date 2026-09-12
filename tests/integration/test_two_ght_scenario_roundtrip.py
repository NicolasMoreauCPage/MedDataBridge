"""Roundtrip de scénario mixte entre deux GHT et deux BDD isolées.

Le GHT source prépare et émet un jeu PAM + HPRIM. Les messages exactement
compilés sont intégrés dans les BDD source et cible par les pipelines métiers,
puis les projections persistées sont comparées. Cette double intégration évite
de confondre la seule présence d'un fichier sortant avec un vrai roundtrip.
"""

import asyncio
import json

from sqlmodel import SQLModel, Session, create_engine, select

# Enregistre tous les modèles SQLModel avant la création des BDD isolées.
import app.db  # noqa: F401
from app.models import Dossier, Patient, Venue
from app.models.hprim_models import HprimExchangeAct
from app.models_identifiers import Identifier
from app.models_endpoints import SystemEndpoint
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_structure import GHTContext, IdentifierNamespace
from app.routers.roundtrip_hprim import _build_message, _persist_exchange_acts, _store_roundtrip_message
from app.services.adt_parser import import_adt_into_ght
from app.services.hprim import HprimService
from app.services.scenario_play_service import execute_scenario_play, prepare_scenario_play


def _new_ght_database(path, code: str) -> tuple[object, int]:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        ght = GHTContext(name=f"GHT {code}", code=code)
        session.add(ght)
        session.commit()
        session.refresh(ght)
        session.add_all([
            IdentifierNamespace(name="IPP recette", type="IPP", system="urn:test:ipp", ght_context_id=ght.id),
            IdentifierNamespace(name="NDA recette", type="NDA", system="urn:test:nda", ght_context_id=ght.id),
            IdentifierNamespace(name="Venue recette", type="VN", system="urn:test:venue", prefix_pattern="9...", ght_context_id=ght.id),
        ])
        session.commit()
        return engine, ght.id


def _hl7_template() -> str:
    pv1 = ["PV1", "", "I", "MED"] + [""] * 15 + ["{{dossier.nda}}"]
    return "\r".join([
        "MSH|^~\\&|GHTA|SOURCE|GHTB|CIBLE|20260912090000||ADT^A01|OLD|P|2.5",
        "PID|||{{patient.ipp}}^^^GHTA&1.2.250.1.213.1.1.4&ISO^PI||{{patient.family}}^{{patient.given}}||19800101|M",
        "|".join(pv1),
        "ZBE|{{movement.id}}|20260912090000||INSERT",
    ])


def _hprim_template() -> str:
    message, _ = _build_message({
        "type_acte": "CCAM",
        "message_id": "RTGHT000001",
        "code": "ZZQK900",
        "code_activite": "01",
        "code_phase": "00",
        "patient": {
            "identifiant_id": "{{patient.ipp}}",
            "nom": "{{patient.family}}",
            "prenom": "{{patient.given}}",
            "date_naissance": "1980-01-01",
            "sexe": "M",
        },
    })
    return HprimService().generer_xml(message, valider=False)


def _integrate_hprim(session: Session, xml_content: str) -> None:
    result = HprimService().traiter_message_xml(xml_content)
    assert result.get("succes"), result
    message = result["message"]
    _store_roundtrip_message(
        session,
        message_id=message.entete.message_id,
        type_message=message.entete.message_type.value,
        xml_content=xml_content,
        status="received",
        source="two-ght-roundtrip",
    )
    _persist_exchange_acts(session, message)
    session.commit()


def _snapshot(session: Session, ipp: str, nda: str) -> dict:
    patient_identifier = session.exec(select(Identifier).where(Identifier.value == ipp)).one()
    dossier_identifier = session.exec(select(Identifier).where(Identifier.value == nda)).one()
    patient = session.get(Patient, patient_identifier.patient_id)
    dossier = session.get(Dossier, dossier_identifier.dossier_id)
    venue = session.exec(select(Venue).where(Venue.dossier_id == dossier.id)).one()
    acts = session.exec(
        select(HprimExchangeAct)
        .where(HprimExchangeAct.patient_id == ipp)
        .order_by(HprimExchangeAct.id)
    ).all()
    return {
        "patient": (patient.family, patient.given, patient.birth_date, patient.gender),
        "patient_identifiers": sorted(item.value for item in session.exec(select(Identifier).where(Identifier.patient_id == patient.id)).all()),
        "dossier_identifier": dossier_identifier.value,
        "venue": (venue.code, venue.uf_responsabilite),
        "acts": [(item.patient_id, item.act_type, item.code, item.action, item.payload_json) for item in acts],
    }


def test_scenario_roundtrip_between_two_ght_databases(tmp_path):
    source_engine, source_ght_id = _new_ght_database(tmp_path / "ght_a.sqlite", "A")
    target_engine, target_ght_id = _new_ght_database(tmp_path / "ght_b.sqlite", "B")
    pam_outbox, hprim_outbox = tmp_path / "mllp-to-ght-b", tmp_path / "hprim-to-ght-b"

    with Session(source_engine) as source:
        scenario = InteropScenario(key="two-ght-pam-hprim", name="Admission + CCAM", protocol="MIXED", ght_context_id=source_ght_id)
        source.add(scenario)
        source.commit()
        source.add_all([
            InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", message_type="ADT^A01", payload=_hl7_template()),
            InteropScenarioStep(scenario_id=scenario.id, order_index=2, message_format="xml", message_type="HPRIM-CCAM", payload=_hprim_template()),
        ])
        pam_endpoint = SystemEndpoint(name="GHT B PAM", kind="FILE", role="sender", outbox_path=str(pam_outbox), target_system_key="GHT-B")
        hprim_endpoint = SystemEndpoint(name="GHT B HPRIM", kind="HPRIM", role="sender", outbox_path=str(hprim_outbox), target_system_key="GHT-B")
        source.add_all([pam_endpoint, hprim_endpoint])
        source.commit()

        play = prepare_scenario_play(source, scenario, [pam_endpoint, hprim_endpoint])
        identifiers = json.loads(play.identity_json)["identifiers"]
        play = asyncio.run(execute_scenario_play(source, play.id))
        assert play.status == "success"

    pam_payload = next(pam_outbox.glob("*.hl7")).read_text(encoding="utf-8")
    hprim_payload = next(hprim_outbox.glob("*.xml")).read_text(encoding="utf-8")

    with Session(source_engine) as source, Session(target_engine) as target:
        assert import_adt_into_ght(pam_payload, source, source_ght_id)["status"] == "success"
        _integrate_hprim(source, hprim_payload)
        assert import_adt_into_ght(pam_payload, target, target_ght_id)["status"] == "success"
        _integrate_hprim(target, hprim_payload)

        assert _snapshot(source, identifiers["ipp"], identifiers["nda"]) == _snapshot(target, identifiers["ipp"], identifiers["nda"])

    source_engine.dispose()
    target_engine.dispose()
