"""Generate a compliance matrix for ZBE segment fields based on pam_validation rules.

Scans pam_validation.py for validation issue codes and outputs a markdown table summarizing
implementation status.
"""
from pathlib import Path
import re

VALIDATION_FILE = Path("app/services/pam_validation.py")
OUTPUT_FILE = Path("program_docs/COMPLIANCE_MATRIX.md")

ZBE_FIELDS = [
    ("ZBE-1", "Identifiant mouvement", "ZBE1_MISSING"),
    ("ZBE-2", "Date/heure mouvement", "ZBE2_MISSING"),
    ("ZBE-4", "Action", "ZBE4_MISSING"),
    ("ZBE-5", "Historique", "ZBE5_MISSING"),
    ("ZBE-6", "Trigger original", "ZBE6_REQUIRED"),
    ("ZBE-7", "UF médicale code", "ZBE7_CODE_MISSING"),
    ("ZBE-8", "UF soins code", "ZBE8_CODE_MISSING"),
    ("ZBE-9", "Nature", "ZBE9_MISSING"),
]

def extract_issue_codes(text: str) -> set:
    pattern = re.compile(r"ValidationIssue\(\s*\"(.*?)\"", re.MULTILINE)
    return set(pattern.findall(text))

def main() -> None:
    if not VALIDATION_FILE.exists():
        raise SystemExit("pam_validation.py introuvable")
    content = VALIDATION_FILE.read_text(encoding="utf-8")
    codes = extract_issue_codes(content)
    lines = ["# Compliance Matrix (Auto-generated)", "", "Champ | Description | Validation Code | Status", "---|---|---|---"]
    for field, desc, code in ZBE_FIELDS:
        status = "Pass" if code in codes else "Missing"
        lines.append(f"{field} | {desc} | {code} | {status}")
    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()