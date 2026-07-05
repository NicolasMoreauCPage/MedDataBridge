"""
Verification harness (not a strict pass/fail regression test): runs every real-world
production IHE PAM France message sample under data/pam/ through the actual inbound
pipeline to measure real-world compatibility. Prints a coverage report.
"""
import glob
import re
import pytest

from app.services.transport_inbound import on_message_inbound_async


def _read_message(path):
    with open(path, encoding="latin-1", errors="replace") as f:
        content = f.read()
    # Normalize to CR-only segment separators, matching MLLP framing convention.
    lines = [l for l in re.split(r"\r\n|\r|\n", content) if l]
    return "\r".join(lines)


@pytest.mark.asyncio
async def test_real_world_pam_sample_coverage(session):
    # Exclude data/pam/ADT_*.hl7: those are self-generated fixtures produced by an
    # old (since-fixed) version of adapters.hl7_pam_fr.build_message_for_movement
    # that doubled the MSH-9 trigger (ADT^ADT^A28 instead of ADT^A28). Only the
    # numerically-named files are genuine production captures (CPAGE -> ANTARES).
    files = sorted(f for f in glob.glob("data/pam/*.hl7") if not f.split("/")[-1].startswith("ADT_"))
    assert files, "no sample files found under data/pam/"

    ack_codes = {}
    exceptions = []
    error_reasons = []
    trigger_outcomes = {}

    for path in files:
        msg = _read_message(path)
        trigger = None
        m = re.search(r"\|ADT\^([A-Z0-9]+)", msg)
        if m:
            trigger = m.group(1)

        try:
            ack = await on_message_inbound_async(msg, session, None)
            session.commit()
        except Exception as e:
            session.rollback()
            exceptions.append((path, trigger, repr(e)))
            continue

        code_m = re.search(r"MSA\|([A-Z]{2})\|", ack)
        code = code_m.group(1) if code_m else "NO_MSA"
        ack_codes[code] = ack_codes.get(code, 0) + 1
        trigger_outcomes.setdefault(trigger, {}).setdefault(code, 0)
        trigger_outcomes[trigger][code] += 1
        if code in ("AE", "AR"):
            err_m = re.search(r"ERR\|([^\r]*)", ack)
            err_text = err_m.group(1) if err_m else "(no ERR segment)"
            error_reasons.append((path, trigger, f"{code}: {err_text}"))

    print("\n=== ACK code distribution ===")
    for code, count in sorted(ack_codes.items(), key=lambda x: -x[1]):
        print(f"  {code}: {count}")

    print("\n=== Outcome by trigger event ===")
    for trigger, codes in sorted(trigger_outcomes.items()):
        print(f"  {trigger}: {codes}")

    print(f"\n=== Unhandled exceptions: {len(exceptions)} ===")
    for path, trigger, err in exceptions[:30]:
        print(f"  {path} (trigger={trigger}): {err}")

    print(f"\n=== AE/AR reasons (first 60) ===")
    for path, trigger, err in error_reasons[:60]:
        print(f"  {path} (trigger={trigger}): {err}")

    # Soft assertion: this is a diagnostic run, not a hard gate. Still fail loudly if
    # literally nothing was processed (would indicate a harness bug, not data issue).
    assert sum(ack_codes.values()) + len(exceptions) == len(files)
