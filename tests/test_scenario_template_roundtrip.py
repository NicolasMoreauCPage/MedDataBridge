"""
Tests de roundtrip pour ScenarioTemplate : vérification conformité EJ

Objectifs :
1. Matérialiser un template → messages HL7/FHIR
2. Vérifier que les messages contiennent les données de l'EJ (namespace, OID, structures)
3. Vérifier que les identifiants générés sont corrects (préfixes, format)
4. Vérifier que les segments obligatoires sont présents et bien formatés
"""
import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, select

from app.models_scenarios import ScenarioTemplate, ScenarioTemplateStep
from app.models_structure_fhir import EntiteJuridique, EntiteGeographique
# UniteFonctionnelle non utilisé dans ces tests
from app.services.scenario_template_materializer import materialize_template, MaterializationOptions
from app.db import get_next_sequence


@pytest.fixture
def test_db():
    """Base de données en mémoire avec contexte GHT minimal."""
    engine = create_engine("sqlite:///:memory:")
    from app.models import SQLModel
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        # Créer GHT context
        from app.models_structure_fhir import GHTContext, IdentifierNamespace
        
        ght = GHTContext(
            name="GHT Test Roundtrip",
            code="GHT_TEST",
            description="Contexte GHT pour tests roundtrip",
        )
        session.add(ght)
        session.flush()
        
        # Créer EJ test avec namespace spécifique
        ej = EntiteJuridique(
            ght_context_id=ght.id,
            name="Hôpital Test Roundtrip",
            short_name="HopTest",
            finess_ej="123456789",
        )
        session.add(ej)
        session.flush()
        
        # Créer namespace
        ns = IdentifierNamespace(
            ght_context_id=ght.id,
            entite_juridique_id=ej.id,
            name="Namespace Test Roundtrip",
            system="urn:oid:1.2.250.1.999.TEST",
            oid="1.2.250.1.999.TEST",
            type="IPP",
            description="Namespace test",
            is_active=True,
        )
        session.add(ns)
        session.commit()
        session.refresh(ej)
        
        # Créer EG avec structure
        eg = EntiteGeographique(
            entite_juridique_id=ej.id,
            name="Établissement Test",
            finess_eg="987654321",
        )
        session.add(eg)
        session.commit()
        session.refresh(eg)
        
        yield session, ej, eg, ns


@pytest.fixture
def sample_template(test_db):
    """Template de test avec 3 steps : admission → transfer → discharge."""
    session, ej, eg, ns = test_db
    
    template = ScenarioTemplate(
        key="test.roundtrip.hospit_simple",
        name="Test Roundtrip Hospitalisation Simple",
        description="Template pour tester la génération conforme à l'EJ",
        category="test",
        protocols_supported="HL7v2,FHIR",
        tags=["test", "roundtrip"],
        is_active=True,
    )
    session.add(template)
    session.flush()
    
    # Step 1 : Admission
    step1 = ScenarioTemplateStep(
        template_id=template.id,
        order_index=1,
        semantic_event_code="ADMISSION_CONFIRMED",
        narrative="Admission en urgences",
        hl7_event_code="ADT^A01",
        fhir_profile_hint="Bundle",
        message_role="inbound",
        delay_suggested_seconds=0,
    )
    
    # Step 2 : Transfer
    step2 = ScenarioTemplateStep(
        template_id=template.id,
        order_index=2,
        semantic_event_code="TRANSFER",
        narrative="Transfert en réanimation",
        hl7_event_code="ADT^A02",
        fhir_profile_hint="Bundle",
        message_role="inbound",
        delay_suggested_seconds=3600,  # 1h après admission
    )
    
    # Step 3 : Discharge
    step3 = ScenarioTemplateStep(
        template_id=template.id,
        order_index=3,
        semantic_event_code="DISCHARGE",
        narrative="Sortie du patient",
        hl7_event_code="ADT^A03",
        fhir_profile_hint="Bundle",
        message_role="inbound",
        delay_suggested_seconds=86400,  # 24h après transfert
    )
    
    session.add_all([step1, step2, step3])
    session.commit()
    session.refresh(template)
    
    return template


def test_materialize_hl7_with_ej_namespace(test_db, sample_template):
    """
    Test 1 : Vérifier que les messages HL7 contiennent le namespace OID de l'EJ.
    """
    session, ej, eg, ns = test_db
    
    # Matérialiser en HL7v2
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        ipp_prefix="9",
        nda_prefix="501",
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    # Vérifier qu'on a 3 steps
    assert len(scenario.steps) == 3
    
    # Vérifier chaque message HL7
    for step in scenario.steps:
        payload = step.payload
        assert payload is not None, f"Step {step.order_index} sans payload"
        
        # Vérifier présence namespace OID dans les identifiants
        assert ej.namespace_oid in payload, f"Step {step.order_index} : namespace OID {ej.namespace_oid} absent"
        
        # Vérifier présence namespace code
        assert ns.code in payload, f"Step {step.order_index} : namespace code {ns.code} absent"
        
        # Vérifier segments obligatoires
        assert "MSH|" in payload, f"Step {step.order_index} : segment MSH absent"
        assert "EVN|" in payload, f"Step {step.order_index} : segment EVN absent"
        assert "PID|" in payload, f"Step {step.order_index} : segment PID absent"
        assert "PV1|" in payload, f"Step {step.order_index} : segment PV1 absent"


def test_materialize_hl7_with_identifier_prefixes(test_db, sample_template):
    """
    Test 2 : Vérifier que les identifiants générés respectent les préfixes IPP/NDA.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        ipp_prefix="9",
        nda_prefix="501",
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    # Récupérer les identifiants générés
    ipp_generated = None
    nda_generated = None
    
    for step in scenario.steps:
        payload = step.payload
        
        # Extraire IPP depuis PID-3 (format: IPP^^^NS&OID&ISO^PI)
        if "PID|" in payload:
            lines = payload.split("\r")
            for line in lines:
                if line.startswith("PID|"):
                    fields = line.split("|")
                    if len(fields) > 3:
                        pid_3 = fields[3]  # PID-3 Patient Identifier List
                        if "^^^" in pid_3:
                            ipp_value = pid_3.split("^^^")[0]
                            if ipp_generated is None:
                                ipp_generated = ipp_value
                            assert ipp_value == ipp_generated, "IPP change entre steps"
                            assert ipp_value.startswith("9"), f"IPP {ipp_value} ne commence pas par '9'"
        
        # Extraire NDA depuis PV1-19 (format: NDA^^^NS&OID&ISO^VN)
        if "PV1|" in payload:
            lines = payload.split("\r")
            for line in lines:
                if line.startswith("PV1|"):
                    fields = line.split("|")
                    if len(fields) > 19:
                        pv1_19 = fields[19]  # PV1-19 Visit Number
                        if "^^^" in pv1_19:
                            nda_value = pv1_19.split("^^^")[0]
                            if nda_generated is None:
                                nda_generated = nda_value
                            assert nda_value == nda_generated, "NDA change entre steps"
                            assert nda_value.startswith("501"), f"NDA {nda_value} ne commence pas par '501'"
    
    # Vérifier qu'on a bien généré des identifiants
    assert ipp_generated is not None, "Aucun IPP généré"
    assert nda_generated is not None, "Aucun NDA généré"
    
    print(f"✅ IPP généré : {ipp_generated}")
    print(f"✅ NDA généré : {nda_generated}")


def test_materialize_hl7_event_codes(test_db, sample_template):
    """
    Test 3 : Vérifier que les codes événements HL7 sont corrects dans MSH-9 et EVN-1.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    expected_events = ["ADT^A01", "ADT^A02", "ADT^A03"]
    
    for idx, step in enumerate(scenario.steps):
        payload = step.payload
        expected_event = expected_events[idx]
        
        # Vérifier MSH-9 (Message Type)
        lines = payload.split("\r")
        msh_line = [l for l in lines if l.startswith("MSH|")][0]
        msh_fields = msh_line.split("|")
        msh_9 = msh_fields[8] if len(msh_fields) > 8 else ""
        
        assert expected_event in msh_9, f"Step {idx+1} : MSH-9 devrait contenir {expected_event}, trouvé {msh_9}"
        
        # Vérifier EVN-1 (Event Type Code)
        evn_line = [l for l in lines if l.startswith("EVN|")][0]
        evn_fields = evn_line.split("|")
        evn_1 = evn_fields[1] if len(evn_fields) > 1 else ""
        
        expected_trigger = expected_event.split("^")[1]  # A01, A02, A03
        assert expected_trigger in evn_1, f"Step {idx+1} : EVN-1 devrait contenir {expected_trigger}, trouvé {evn_1}"


def test_materialize_fhir_with_ej_data(test_db, sample_template):
    """
    Test 4 : Vérifier que les Bundles FHIR contiennent les ressources avec données de l'EJ.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="FHIR",
        generate_identifiers=True,
        ipp_prefix="9",
        nda_prefix="501",
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    import json
    
    for step in scenario.steps:
        payload = step.payload
        assert payload is not None
        
        # Parser le Bundle FHIR
        bundle = json.loads(payload)
        assert bundle["resourceType"] == "Bundle"
        assert "entry" in bundle
        
        # Vérifier présence des ressources
        resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
        assert "Patient" in resource_types, f"Step {step.order_index} : Patient absent"
        assert "Encounter" in resource_types, f"Step {step.order_index} : Encounter absent"
        assert "Organization" in resource_types, f"Step {step.order_index} : Organization absent"
        
        # Vérifier Organization contient les données de l'EJ
        org_entry = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Organization"][0]
        org = org_entry["resource"]
        
        assert org["name"] == ej.name, f"Organization.name devrait être '{ej.name}'"
        
        # Vérifier identifiant FINESS
        finess_id = [id for id in org.get("identifier", []) if id.get("system") == "urn:oid:1.2.250.1.71.4.2.2"]
        assert len(finess_id) > 0, "Organization devrait avoir identifiant FINESS"
        assert finess_id[0]["value"] == ej.finess, f"FINESS devrait être {ej.finess}"


def test_materialize_fhir_patient_identifiers(test_db, sample_template):
    """
    Test 5 : Vérifier que le Patient FHIR contient les identifiants avec bon namespace.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="FHIR",
        generate_identifiers=True,
        ipp_prefix="9",
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    import json
    
    # Vérifier le premier step (admission)
    first_step = scenario.steps[0]
    bundle = json.loads(first_step.payload)
    
    patient_entry = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"][0]
    patient = patient_entry["resource"]
    
    # Vérifier identifiants
    assert "identifier" in patient
    assert len(patient["identifier"]) > 0
    
    # Chercher l'identifiant IPP (type MR ou PI)
    ipp_ids = [id for id in patient["identifier"] if id.get("type", {}).get("coding", [{}])[0].get("code") in ["MR", "PI"]]
    assert len(ipp_ids) > 0, "Patient devrait avoir au moins un identifiant IPP"
    
    ipp_id = ipp_ids[0]
    assert "system" in ipp_id
    assert ej.namespace_oid in ipp_id["system"], f"IPP system devrait contenir {ej.namespace_oid}"
    assert "value" in ipp_id
    assert ipp_id["value"].startswith("9"), f"IPP value devrait commencer par '9', trouvé {ipp_id['value']}"


def test_materialize_consistency_across_steps(test_db, sample_template):
    """
    Test 6 : Vérifier que les identifiants restent cohérents entre les steps d'un même scénario.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        ipp_prefix="8",
        nda_prefix="400",
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    # Extraire IPP et NDA de chaque step
    identifiers = []
    for step in scenario.steps:
        payload = step.payload
        lines = payload.split("\r")
        
        ipp = None
        nda = None
        
        # Extraire PID-3
        for line in lines:
            if line.startswith("PID|"):
                fields = line.split("|")
                if len(fields) > 3 and "^^^" in fields[3]:
                    ipp = fields[3].split("^^^")[0]
        
        # Extraire PV1-19
        for line in lines:
            if line.startswith("PV1|"):
                fields = line.split("|")
                if len(fields) > 19 and "^^^" in fields[19]:
                    nda = fields[19].split("^^^")[0]
        
        identifiers.append((ipp, nda))
    
    # Vérifier que tous les steps ont les mêmes identifiants
    first_ipp, first_nda = identifiers[0]
    
    for idx, (ipp, nda) in enumerate(identifiers[1:], start=2):
        assert ipp == first_ipp, f"Step {idx} : IPP {ipp} différent de step 1 ({first_ipp})"
        assert nda == first_nda, f"Step {idx} : NDA {nda} différent de step 1 ({first_nda})"
    
    print(f"✅ Cohérence des identifiants : IPP={first_ipp}, NDA={first_nda} sur {len(identifiers)} steps")


def test_materialize_without_identifiers(test_db, sample_template):
    """
    Test 7 : Vérifier que la matérialisation fonctionne même sans génération d'identifiants.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=False,  # Pas de génération
        namespace_oid=ns.oid,
    )
    
    scenario = materialize_template(session, sample_template, ej.id, options)
    
    # Vérifier qu'on a les steps
    assert len(scenario.steps) == 3
    
    # Les messages doivent toujours contenir le namespace
    for step in scenario.steps:
        payload = step.payload
        assert ej.namespace_oid in payload
        assert "MSH|" in payload
        assert "PID|" in payload


def test_materialize_invalid_ej_id(test_db, sample_template):
    """
    Test 8 : Vérifier que la matérialisation échoue proprement avec un EJ invalide.
    """
    session, ej, eg, ns = test_db
    
    options = MaterializationOptions(
        protocol="HL7v2",
        generate_identifiers=True,
        namespace_oid="1.2.3.4.5.INVALID",
    )
    
    with pytest.raises(ValueError, match="EJ.*introuvable"):
        materialize_template(session, sample_template, 99999, options)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
