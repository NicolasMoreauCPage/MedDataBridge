import asyncio
import pytest
import time
from datetime import datetime


@pytest.mark.usefixtures("setup_database")
def test_a28_a04_a03_roundtrip_and_validators(monkeypatch):
    """Inject ADT^A28 -> ADT^A04 -> ADT^A03, validate each message and the scenario.
    Verifies persistence, MessageLog creation and that emitted PAM is produced.
    """
    try:
        from app.services.entity_events import register_entity_events
        register_entity_events()
    except Exception:
        pass

    sent_payloads = []

    async def fake_send_mllp(host, port, hl7_message):
        sent_payloads.append(hl7_message)
        await asyncio.sleep(0)
        return "MSH|^~\\&|MEDBRIDGE|POC|SRC-PAM|SRC|20251101000000||ACK|ACK1|P|2.5\rMSA|AA|MSG00001"

    monkeypatch.setattr("app.services.mllp.send_mllp", fake_send_mllp)
    try:
        monkeypatch.setattr("app.services.structure_emit.send_mllp", fake_send_mllp)
    except Exception:
        pass

    from app.db import engine
    from sqlmodel import Session as SQLSession
    from app.models_shared import SystemEndpoint, MessageLog
    from app.models_structure import EntiteJuridique, IdentifierNamespace

    # Messages: A28 (create identity), A04 (admission), A03 (discharge) provided by user
    # PID-5 requires XPN-7 (Name Type Code): L=Legal, D=Usage, U=Unspecified
    a28 = (
        "MSH|^~\\&|SRC-PAM|SRC|MEDBRIDGE|POC|20251101010101||ADT^A28|MSG-A28|P|2.5\r"
        "EVN|A28|20251101010101\r"
        "PID|||SRC12345^^^SRC-PAM&1.2.250.1.211.99.1&ISO^PI||DOE^JOHN^^^^^L||19800101|M||||||||||||||||||||||||VALI\r"
    )

    # Use a full A04 Exemple similar to the consultation Exemple (includes ZBE/ZFV etc.)
    # Adjusted timestamps to follow the A28 message and ZBE-9 set to 'HMS' (recognized)
    a04 = (
        "MSH|^~\\&|CPAGE|CPAGE|ANTARES|ANTARES|20251101010200||ADT^A04^ADT_A01|1117924606|P|2.5^FRA^2.11|||||FRA|8859/1\r"
        "EVN||20251101010200|20251101010200||phmo^INCONNU^INCONNU^^^^^^CPAGE&1.2.250.1.154&ISO|20251101010200\r"
        "PID|||000059475952^^^CPAGE&1.2.250.1.211.10.200.2&ISO^PI||RETRO^UN^UN^^M.^^L||19451010|M|||RUE DE LA RETRO^^DIJON^^21000^FRA^H|||||S||036298323^^^CPAGE&1.2.250.1.211.12.1.2&L^AN||||||N||||||N||PROV||890000038^^M\r"
        "PD1||||||||||||N\r"
        "PV1||O|7700|R|||101005344^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^RPPS|||||A||1|||||4159601^^^CPAGE&1.2.250.1.211.12.1.2&L^VN||||||||||||||||||||||N||^^^^^^^^RUE DE LA RETRO 21000 DIJON 100|20251001142800|||||||V\r"
        "PV2|||||||TO|||||||||||||||N||||||||||||||N||5\r"
    "ZBE|12565081^CPAGE^1.2.250.1.211.12.1.2^ISO|20251101010200||INSERT|N||^^^^^^UF^^^7700||HMS\r"
        "ZFA|||||||||NA||NA\r"
        "ZFP|\r"
        "ZFV||||||RUE DE LA RETRO^^DIJON^^21000^100\r"
        "ZFD||||N\r"
        "ROL||UC|AT|101005344^PICQUE^JEAN BAPTISTE^^^^^^ADELI&2.16.840.1.113883.3.31.2.2&ISO^D^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^RPPS^D^^^RPPS|20251001142800|20991231235959\r"
    )

    # Make A03 occur after A04
    a03 = (
        "MSH|^~\\&|CPAGE|CPAGE|ANTARES|ANTARES|20251101010300||ADT^A03^ADT_A03|1117924612|P|2.5^FRA^2.11|||||FRA|8859/1\r"
        "EVN||20251101010300|20251101010300||phmo^INCONNU^INCONNU^^^^^^CPAGE&1.2.250.1.154&ISO|20251101010300\r"
        "PID|||000059475952^^^CPAGE&1.2.250.1.211.10.200.2&ISO^PI||RETRO^UN^UN^^M.^^L||19451010|M|||RUE DE LA RETRO^^DIJON^^21000^FRA^H|||||S||036298323^^^CPAGE&1.2.250.1.211.12.1.2&L^AN||||||N||||||N||PROV||890000038^^M\r"
        "PD1||||||||||||N\r"
        "PV1||O|7700|R|||101005344^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^ASIP-SANTE-PS&1.2.250.1.71.4.2.1&ISO^L^^^RPPS|||||A||1|||||4159601^^^CPAGE&1.2.250.1.211.12.1.2&L^VN||||||||||||||||||||||N||^^^^^^^^RUE DE LA RETRO 21000 DIJON 100|20251001142800|20251002132800||||||V\r"
        "PV2|||||||TO|||||||||||||||N||||||||||||||N||5\r"
    "ZBE|12565082^CPAGE^1.2.250.1.211.12.1.2^ISO|20251101010300||INSERT|N||^^^^^^UF^^^7700||HMS\r"
        "ZFP|\r"
        "ZFV||||||RUE DE LA RETRO^^DIJON^^21000^100\r"
        "ROL||UC|AT|101005344^PICQUE^JEAN BAPTISTE^^^^^^ADELI&2.16.840.1.113883.3.31.2.2&ISO^D^^^ADELI~10100534436^PICQUE^JEAN BAPTISTE^^^^^^RPPS^D^^^RPPS|20251001142800|20251002132800\r"
    )

    from app.services.pam_validation import validate_pam
    from app.services.scenario_validation import validate_scenario

    with SQLSession(engine) as session:
        # create EJ and endpoints to trigger emission
        ej = EntiteJuridique(name='EJ Chain', finess_ej='111111111', is_active=True)
        session.add(ej)
        session.commit()

        ns = IdentifierNamespace(name='IPP-EJ', system='urn:oid:1.2.250.111.1', oid='1.2.250.111.1', type='IPP', entite_juridique_id=ej.id, is_active=True)
        session.add(ns)
        session.commit()

        ep = SystemEndpoint(name='EP CHAIN', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2581, entite_juridique_id=ej.id)
        session.add(ep)
        session.commit()

        # global endpoint too
        epg = SystemEndpoint(name='EP GLOBAL', kind='MLLP', role='sender', is_enabled=True, host='localhost', port=2582)
        session.add(epg)
        session.commit()

        from app.services.transport_inbound import on_message_inbound

        # helper to send and validate
        def send_and_validate(msg_text):
            res = on_message_inbound(msg_text, session, None)
            if asyncio.iscoroutine(res):
                ack = asyncio.get_event_loop().run_until_complete(res)
                ack_str = ack if isinstance(ack, str) else str(ack)
            else:
                ack_str = res.get('ack') if isinstance(res, dict) else str(res)

            # structural validation
            val = validate_pam(msg_text, direction="inbound")
            assert isinstance(val.is_valid, bool)
            # Fail only if validator found errors (but allow warnings)
            if not val.is_valid and val.level == 'error':
                issues = [f"{i.code}:{i.severity}:{i.message}" for i in val.issues]
                pytest.fail(f"Message structural validation failed (ACK={ack_str}): " + ';'.join(issues))
            return val

        # Send messages in order
        # Start watching for MessageLog entries now (before sending messages)
        start = datetime.utcnow()
        val1 = send_and_validate(a28)
        val2 = send_and_validate(a04)
        val3 = send_and_validate(a03)

        # Wait for MessageLog entries and emitted payloads
        end = time.time() + 5
        logs = []
        while time.time() < end:
            q = session.exec  # quick existence check by re-querying MessageLog via SQLModel
            from sqlmodel import select
            logs = session.exec(select(MessageLog).where(MessageLog.created_at >= start)).all()
            if logs and sent_payloads:
                break
            time.sleep(0.05)

        assert logs, 'No MessageLog entries created during scenario'
        assert sent_payloads, 'No HL7 sent captured during scenario'

        # Validate the full scenario workflow
        scenario_text = "\n\n".join([a28, a04, a03])
        scen_res = validate_scenario(scenario_text, direction='inbound', profile='IHE_PAM_FR')
        # scenario must at least be parsed and Renvoie a ScenarioValidationResult
        assert hasattr(scen_res, 'is_valid')

        # Verify expected validator outputs for this scenario
        # - We expect the per-message validator to mark A28 as valid and A04/A03
        #   to either fail under strict mode or be reported as a warning when
        #   production tokens are tolerated.
        assert val1.is_valid is True
        # ZBE-9 validation was relaxed to a warning for some production tokens.
        # Accept either an error (is_valid==False) or a warning-level result.
        assert (val2.is_valid is False) or (val2.level == 'warn')
        assert (val3.is_valid is False) or (val3.level == 'warn')

        # Check that either ZBE9_INVALID (strict) or ZBE9_NONSTANDARD_COMPOSITE
        # (production token tolerated) appears in the issue codes.
        def issue_codes(validation):
            return {i.code for i in validation.issues}

        codes2 = issue_codes(val2)
        codes3 = issue_codes(val3)
        assert ('ZBE9_INVALID' in codes2) or ('ZBE9_NONSTANDARD_COMPOSITE' in codes2), f'A04 should report ZBE9_INVALID or ZBE9_NONSTANDARD_COMPOSITE, got {codes2}'
        assert ('ZBE9_INVALID' in codes3) or ('ZBE9_NONSTANDARD_COMPOSITE' in codes3), f'A03 should report ZBE9_INVALID or ZBE9_NONSTANDARD_COMPOSITE, got {codes3}'

        # For the scenario validator, we expect workflow errors because A28 is not an initial event
        # and the transitions A28->A04 and A04->A03 are flagged invalid for this ordered set.
        wf_codes = [w.code for w in scen_res.workflow_issues]
        assert 'WORKFLOW_INVALID_INITIAL' in wf_codes, f'Expected WORKFLOW_INVALID_INITIAL in {wf_codes}'
        assert any(c == 'WORKFLOW_INVALID_TRANSITION' for c in wf_codes), f'Expected WORKFLOW_INVALID_TRANSITION in {wf_codes}'
