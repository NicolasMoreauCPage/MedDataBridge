import os
import subprocess


def test_roundtrip_writes_outbox_files(tmp_path):
    # Run the roundtrip harness in testing mode (uses in-memory DB)
    env = os.environ.copy()
    env["TESTING"] = "1"
    env["RESET_DB"] = "1"
    cmd = [".venv/bin/python3", "scripts/mfn_roundtrip.py"]
    subprocess.check_call(cmd, env=env)

    base = "/tmp/medbridge_generated"
    assert os.path.isdir(base), f"Outbox base dir not found: {base}"

    pam_dir = os.path.join(base, "pam")
    mfn_dir = os.path.join(base, "mfn")
    fhir_dir = os.path.join(base, "fhir")

    pam_files = [f for f in os.listdir(pam_dir) if f.endswith('.hl7')]
    mfn_files = [f for f in os.listdir(mfn_dir) if f.endswith('.hl7')]
    fhir_files = [f for f in os.listdir(fhir_dir) if f.endswith('.json')]

    assert len(pam_files) > 0, "No PAM files generated"
    assert len(mfn_files) > 0, "No MFN files generated"
    assert len(fhir_files) > 0, "No FHIR files generated"
