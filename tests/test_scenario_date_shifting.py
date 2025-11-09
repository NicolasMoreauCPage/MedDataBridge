import re
from datetime import datetime, timedelta
from app.services.scenario_timeplan import TimeShiftConfig, shift_hl7_scenario

def _make_msg(ts: str, ev: str) -> str:
    return f"MSH|^~\\&|SRC|FAC|DST|FAC|{ts}||ADT^{ev}|123|P|2.5\rEVN|{ev}|{ts}\rPID|1||123456^^^SYS^PI\rPV1|1|||||||||||||||||VIS123^VN"

def extract_ts(msg: str) -> str:
    m = re.search(r"MSH\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|([0-9]{14})", msg)
    return m.group(1) if m else ""

def test_preserve_interval_basic():
    base = datetime(2024, 11, 1, 8, 0, 0)
    msg1_ts = base.strftime("%Y%m%d%H%M%S")
    msg2_ts = (base + timedelta(hours=2)).strftime("%Y%m%d%H%M%S")
    messages = [
        _make_msg(msg1_ts, "A01"),
        _make_msg(msg2_ts, "A02"),
    ]
    cfg = TimeShiftConfig(anchor_mode="now", preserve_intervals=True)
    shifted = shift_hl7_scenario(messages, cfg)
    ts1 = extract_ts(shifted[0])
    ts2 = extract_ts(shifted[1])
    dt1 = datetime.strptime(ts1, "%Y%m%d%H%M%S")
    dt2 = datetime.strptime(ts2, "%Y%m%d%H%M%S")
    assert (dt2 - dt1).total_seconds() in {7200, 7199, 7201}  # ~2h interval preserved

def test_jitter_applied_on_transfer():
    base = datetime(2024, 11, 1, 8, 0, 0)
    msg1_ts = base.strftime("%Y%m%d%H%M%S")
    msg2_ts = (base + timedelta(hours=1)).strftime("%Y%m%d%H%M%S")
    messages = [
        _make_msg(msg1_ts, "A01"),
        _make_msg(msg2_ts, "A02"),  # eligible to jitter
    ]
    cfg = TimeShiftConfig(anchor_mode="now", jitter_min_minutes=5, jitter_max_minutes=15)
    shifted = shift_hl7_scenario(messages, cfg)
    ts1 = extract_ts(shifted[0])
    ts2 = extract_ts(shifted[1])
    dt1 = datetime.strptime(ts1, "%Y%m%d%H%M%S")
    dt2 = datetime.strptime(ts2, "%Y%m%d%H%M%S")
    # Interval should be roughly 60min ± 15min
    diff_min = (dt2 - dt1).total_seconds() / 60
    assert 45 <= diff_min <= 75
