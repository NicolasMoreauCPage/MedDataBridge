"""Test de round-trip scénario: capture → export JSON → reload → vérification."""
import json
from datetime import datetime, timedelta
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool

from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure_fhir import GHTContext, IdentifierNamespace
from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.services.scenario_capture import capture_dossier_as_scenario


def setup_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_scenario_roundtrip_basic():
    """Test round-trip: création manuelle → export → reload → vérification."""
    engine = setup_db()
    with Session(engine) as session:
        # Setup contexte
        ctx = GHTContext(name="Test Ctx", is_active=True)
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        
        # Étape 1: Créer scénario avec 3 steps manuellement
        scenario = InteropScenario(
            key="test-roundtrip",
            name="Test Roundtrip",
            description="Test de round-trip",
            protocol="HL7",
            ght_context_id=ctx.id,
            preserve_intervals=True
        )
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        
        # Créer 3 steps espacés (0h, 2h, 4h)
        base_time = datetime.utcnow()
        for i, (trigger, delay) in enumerate([("A01", 0), ("A02", 7200), ("A03", 14400)]):
            step = InteropScenarioStep(
                scenario_id=scenario.id,
                order_index=i,
                message_type=f"ADT^{trigger}",
                message_format="HL7",
                delay_seconds=delay,
                payload=f"MSH|^~\\&|TEST|FAC|REC|FAC|20251109120000||ADT^{trigger}|MSG{i:03d}|P|2.5\r"
                        f"EVN|{trigger}|20251109120000\r"
                        f"PID|1||IPP{i}^^^TEST&1.2.3&ISO^PI||Dupont^Jean\r"
                        f"PV1|1|I|SVC^ROOM{i}^BED{i}\r"
            )
            session.add(step)
        session.commit()
        
        # Charger steps
        steps = sorted(scenario.steps, key=lambda s: s.order_index)
        assert len(steps) == 3
        
        # Vérifier délais relatifs
        assert steps[0].delay_seconds == 0
        assert steps[1].delay_seconds == 7200  # 2h
        assert steps[2].delay_seconds == 14400  # 4h
        
        # Étape 2: Exporter en JSON (simulation endpoint)
        export_data = {
            "id": scenario.id,
            "key": scenario.key,
            "name": scenario.name,
            "description": scenario.description,
            "protocol": scenario.protocol,
            "tags": scenario.tags,
            "time_config": {
                "anchor_mode": scenario.time_anchor_mode,
                "anchor_days_offset": scenario.time_anchor_days_offset,
                "fixed_start_iso": scenario.time_fixed_start_iso,
                "preserve_intervals": scenario.preserve_intervals,
                "jitter_min": scenario.jitter_min_minutes,
                "jitter_max": scenario.jitter_max_minutes,
                "jitter_events": scenario.apply_jitter_on_events,
            },
            "steps": [
                {
                    "order_index": s.order_index,
                    "message_type": s.message_type,
                    "format": s.message_format,
                    "delay_seconds": s.delay_seconds,
                    "payload": s.payload,
                }
                for s in steps
            ],
        }
        
        # Sérialiser/désérialiser JSON
        json_str = json.dumps(export_data, indent=2)
        reloaded_data = json.loads(json_str)
        
        # Étape 3: Recréer scénario à partir du JSON
        reloaded_scenario = InteropScenario(
            key=reloaded_data["key"] + "-reload",  # Éviter collision clé unique
            name=reloaded_data["name"] + " (Reloaded)",
            description=reloaded_data["description"],
            protocol=reloaded_data["protocol"],
            tags=reloaded_data["tags"],
            ght_context_id=ctx.id,
            time_anchor_mode=reloaded_data["time_config"]["anchor_mode"],
            time_anchor_days_offset=reloaded_data["time_config"]["anchor_days_offset"],
            time_fixed_start_iso=reloaded_data["time_config"]["fixed_start_iso"],
            preserve_intervals=reloaded_data["time_config"]["preserve_intervals"],
            jitter_min_minutes=reloaded_data["time_config"]["jitter_min"],
            jitter_max_minutes=reloaded_data["time_config"]["jitter_max"],
            apply_jitter_on_events=reloaded_data["time_config"]["jitter_events"],
        )
        session.add(reloaded_scenario)
        session.commit()
        session.refresh(reloaded_scenario)
        
        # Recréer steps
        for step_data in reloaded_data["steps"]:
            reloaded_step = InteropScenarioStep(
                scenario_id=reloaded_scenario.id,
                order_index=step_data["order_index"],
                message_type=step_data["message_type"],
                message_format=step_data["format"],
                delay_seconds=step_data["delay_seconds"],
                payload=step_data["payload"],
            )
            session.add(reloaded_step)
        session.commit()
        
        # Étape 4: Vérifier identité
        reloaded_steps = session.exec(
            select(InteropScenarioStep)
            .where(InteropScenarioStep.scenario_id == reloaded_scenario.id)
            .order_by(InteropScenarioStep.order_index)
        ).all()
        
        assert len(reloaded_steps) == len(steps)
        
        for orig, reload in zip(steps, reloaded_steps):
            assert orig.order_index == reload.order_index
            assert orig.message_type == reload.message_type
            assert orig.message_format == reload.message_format
            assert orig.delay_seconds == reload.delay_seconds
            assert orig.payload == reload.payload
        
        # Vérifier config temporelle
        assert reloaded_scenario.preserve_intervals == scenario.preserve_intervals
        assert reloaded_scenario.time_anchor_mode == scenario.time_anchor_mode
        
        print(f"✓ Round-trip réussi: {len(steps)} steps préservés identiquement")
        print(f"✓ Délais: {[s.delay_seconds for s in reloaded_steps]}")
        print(f"✓ Types: {[s.message_type for s in reloaded_steps]}")


def test_scenario_export_import_with_timeconfig():
    """Test export/import avec configuration temporelle avancée."""
    engine = setup_db()
    with Session(engine) as session:
        ctx = GHTContext(name="Test Ctx", is_active=True)
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        
        # Créer scénario avec config temporelle complexe
        scenario = InteropScenario(
            key="time-test",
            name="Time Config Test",
            protocol="HL7",
            ght_context_id=ctx.id,
            time_anchor_mode="admission",
            time_anchor_days_offset=-2,
            preserve_intervals=True,
            jitter_min_minutes=5,
            jitter_max_minutes=15,
            apply_jitter_on_events="A02,A06"
        )
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        
        # Ajouter steps
        for i in range(3):
            step = InteropScenarioStep(
                scenario_id=scenario.id,
                order_index=i,
                message_type=f"ADT^A0{i+1}",
                message_format="HL7",
                delay_seconds=i * 3600,  # 0h, 1h, 2h
                payload=f"MSH|test|step{i}\r"
            )
            session.add(step)
        session.commit()
        
        # Export
        export_data = {
            "key": scenario.key,
            "name": scenario.name,
            "protocol": scenario.protocol,
            "time_config": {
                "anchor_mode": scenario.time_anchor_mode,
                "anchor_days_offset": scenario.time_anchor_days_offset,
                "preserve_intervals": scenario.preserve_intervals,
                "jitter_min": scenario.jitter_min_minutes,
                "jitter_max": scenario.jitter_max_minutes,
                "jitter_events": scenario.apply_jitter_on_events,
            },
            "steps": [
                {
                    "order_index": s.order_index,
                    "message_type": s.message_type,
                    "format": s.message_format,
                    "delay_seconds": s.delay_seconds,
                    "payload": s.payload,
                }
                for s in sorted(scenario.steps, key=lambda x: x.order_index)
            ],
        }
        
        json_str = json.dumps(export_data)
        reloaded = json.loads(json_str)
        
        # Vérifier time_config préservé
        assert reloaded["time_config"]["anchor_mode"] == "admission"
        assert reloaded["time_config"]["anchor_days_offset"] == -2
        assert reloaded["time_config"]["preserve_intervals"] is True
        assert reloaded["time_config"]["jitter_min"] == 5
        assert reloaded["time_config"]["jitter_max"] == 15
        assert reloaded["time_config"]["jitter_events"] == "A02,A06"
        
        # Vérifier steps
        assert len(reloaded["steps"]) == 3
        assert reloaded["steps"][0]["delay_seconds"] == 0
        assert reloaded["steps"][1]["delay_seconds"] == 3600
        assert reloaded["steps"][2]["delay_seconds"] == 7200
        
        print("✓ Time config préservée correctement dans export/import")


def test_scenario_payload_integrity():
    """Test intégrité des payloads HL7 après round-trip."""
    engine = setup_db()
    with Session(engine) as session:
        ctx = GHTContext(name="Test Ctx", is_active=True)
        session.add(ctx)
        session.commit()
        session.refresh(ctx)
        
        # Payload HL7 complexe avec caractères spéciaux
        hl7_payload = (
            "MSH|^~\\&|SENDING|FACILITY|RECEIVING|FACILITY|20251109120000||ADT^A01|MSG001|P|2.5\r"
            "EVN|A01|20251109120000\r"
            "PID|1||12345^^^TEST&1.2.3&ISO^PI||Dupont^Jean^Marie||19800101|M|||123 Rue de la Paix^^Paris^^75001^FRA\r"
            "PV1|1|I|SVC^ROOM^BED^FACILITY^^^^DEPT|||DOC123^Smith^John^Dr.\r"
            "ZBE|1|ADMISSION|20251109120000|UF001|SERVICE001\r"
        )
        
        scenario = InteropScenario(
            key="payload-test",
            name="Payload Integrity Test",
            protocol="HL7",
            ght_context_id=ctx.id
        )
        session.add(scenario)
        session.commit()
        session.refresh(scenario)
        
        step = InteropScenarioStep(
            scenario_id=scenario.id,
            order_index=0,
            message_type="ADT^A01",
            message_format="HL7",
            delay_seconds=0,
            payload=hl7_payload
        )
        session.add(step)
        session.commit()
        
        # Export
        export_data = {
            "steps": [
                {
                    "order_index": step.order_index,
                    "message_type": step.message_type,
                    "format": step.message_format,
                    "delay_seconds": step.delay_seconds,
                    "payload": step.payload,
                }
            ]
        }
        
        json_str = json.dumps(export_data)
        reloaded = json.loads(json_str)
        
        # Vérifier payload identique
        assert reloaded["steps"][0]["payload"] == hl7_payload
        
        # Vérifier segments préservés
        reloaded_payload = reloaded["steps"][0]["payload"]
        assert "MSH|^~\\&|" in reloaded_payload
        assert "PID|1||12345^^^TEST&1.2.3&ISO^PI||" in reloaded_payload
        assert "ZBE|1|ADMISSION|" in reloaded_payload
        
        print("✓ Payload HL7 préservé intégralement (segments, délimiteurs, encodage)")
