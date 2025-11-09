import re
from datetime import datetime, timedelta
from sqlmodel import SQLModel, Session, create_engine

from app.models_scenarios import InteropScenario, InteropScenarioStep
from app.models_endpoints import SystemEndpoint
from app.services.scenario_runner import send_scenario

# Monkeypatch send_mllp used internally
import app.services.scenario_runner as runner_mod

def fake_send_mllp(host, port, payload):
    return "MSA|AA|123"

runner_mod.send_mllp = fake_send_mllp  # type: ignore

def _make_msg(ts: str, ev: str) -> str:
    return f"MSH|^~\\&|SRC|FAC|DST|FAC|{ts}||ADT^{ev}|123|P|2.5\rEVN|{ev}|{ts}\rPID|1||123456^^^SYS^PI\rPV1|1|||||||||||||||||VIS123^VN"

def extract_msh_ts(msg: str) -> str:
    m = re.search(r"MSH\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|([0-9]{14})", msg)
    return m.group(1) if m else ""

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine

def test_send_scenario_preserves_interval_advanced_timeplan():
    engine = setup_db()
    with Session(engine) as session:
        base = datetime(2024, 5, 1, 8, 0, 0)
        msg1_ts = base.strftime("%Y%m%d%H%M%S")
        msg2_ts = (base + timedelta(hours=3)).strftime("%Y%m%d%H%M%S")
        scenario = InteropScenario(key="test/timeplan", name="Timeplan Test")
        session.add(scenario); session.commit(); session.refresh(scenario)
        step1 = InteropScenarioStep(scenario_id=scenario.id, order_index=1, message_format="hl7", payload=_make_msg(msg1_ts, "A01"))
        step2 = InteropScenarioStep(scenario_id=scenario.id, order_index=2, message_format="hl7", payload=_make_msg(msg2_ts, "A02"))
        session.add(step1); session.add(step2); session.commit(); session.refresh(step1); session.refresh(step2)
        endpoint = SystemEndpoint(name="Dummy", kind="MLLP", host="dummy", port=1234)
        session.add(endpoint); session.commit(); session.refresh(endpoint)
        logs = runner_mod.send_scenario.__wrapped__ if hasattr(runner_mod.send_scenario, "__wrapped__") else None
        # Execute async send_scenario via event loop
        import asyncio
        async def _run():
            return await send_scenario(session, scenario, endpoint, update_dates=True, use_advanced_timeplan=True)
        result_logs = asyncio.run(_run())
        assert len(result_logs) == 2
        ts1 = extract_msh_ts(result_logs[0].payload)
        ts2 = extract_msh_ts(result_logs[1].payload)
        dt1 = datetime.strptime(ts1, "%Y%m%d%H%M%S")
        dt2 = datetime.strptime(ts2, "%Y%m%d%H%M%S")
        diff = dt2 - dt1
        # Interval ≈ 3h preserved (allow jitter tolerance if default jitter off)
        assert 3*3600 - 2 <= diff.total_seconds() <= 3*3600 + 120
