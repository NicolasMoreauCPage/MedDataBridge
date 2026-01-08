"""Generate a compliance matrix for ZBE segment fields based on pam_validation rules.

Scans pam_validation.py for validation issue codes and outputs a markdown table summarizing
implementation status.
"""
from pathlib import Path
import re

VALIDATION_FILE = Path("app/services/pam_validation.py")
OUTPUT_FILE = Path("program_docs/COMPLIANCE_MATRIX.md")

ZBE_FIELDS = [
    ("ZBE-1", "Identifiant mouvement", ["ZBE1_MISSING"], "error"),
    ("ZBE-2", "Date/heure mouvement", ["ZBE2_MISSING"], "error"),
    ("ZBE-4", "Action", ["ZBE4_MISSING", "ZBE4_ACTION_INVALID"], "error"),
    ("ZBE-5", "Historique", ["ZBE5_MISSING"], "warning"),
    ("ZBE-6", "Trigger original", ["ZBE6_REQUIRED"], "error"),
    ("ZBE-7", "UF médicale code", ["ZBE7_CODE_MISSING"], "error"),
    ("ZBE-8", "UF soins code", ["ZBE8_CODE_MISSING"], "warning"),
    ("ZBE-9", "Nature", ["ZBE9_MISSING", "ZBE9_INVALID"], "error"),
]

def extract_issue_codes(text: str) -> set:
    pattern = re.compile(r"ValidationIssue\(\s*\"(.*?)\"", re.MULTILINE)
    return set(pattern.findall(text))

def classify_coverage(expected_codes: list[str], found_codes: set[str]) -> str:
    present = [c for c in expected_codes if c in found_codes]
    if not present:
        return "Missing"
    if len(present) < len(expected_codes):
        return "Partial"
    return "Full"

def main() -> None:
    if not VALIDATION_FILE.exists():
        raise SystemExit("pam_validation.py introuvable")
    content = VALIDATION_FILE.read_text(encoding="utf-8")
    codes = extract_issue_codes(content)
    lines = [
        "# Compliance Matrix (Auto-generated)",
        "",
        "Champ | Description | Expected Codes | Severity | Coverage",
        "---|---|---|---|---",
    ]
    for field, desc, expected_codes, severity in ZBE_FIELDS:
        coverage = classify_coverage(expected_codes, codes)
        joined = ",".join(expected_codes)
        lines.append(f"{field} | {desc} | {joined} | {severity} | {coverage}")
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()