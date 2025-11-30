#!/usr/bin/env python3
"""
Simple validator for EI values used in PL-10 (Entity Identifier).
Usage: python scripts/validate_ei.py <ei>...
Example EI: 123456^APP_EMETTEUR^950003806^FINEJ
Checks:
 - EI-1 (first component) length <= 16 characters
 - EI consists of components separated by '^' (at least one)
 - Reports PASS/WARN/FAIL
"""
import sys
import re

MAX_EI1 = 16

EI_RE = re.compile(r"^[^\^]+(\^[^\^]*)*$")


def validate_ei(ei: str):
    # basic shape
    if not EI_RE.match(ei):
        return False, "MALFORMED", "EI must be one or more components separated by '^'"
    parts = ei.split('^')
    ei1 = parts[0]
    if len(ei1) == 0:
        return False, "MALFORMED", "EI-1 is empty"
    if len(ei1) > MAX_EI1:
        return False, "TOO_LONG", f"EI-1 length={len(ei1)} > {MAX_EI1}"
    # optionally, you could restrict characters; we'll permit printable non-control chars
    return True, "OK", f"EI-1 length={len(ei1)}"


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_ei.py <ei> [ei2 ...]")
        sys.exit(2)
    for ei in sys.argv[1:]:
        ok, code, msg = validate_ei(ei)
        status = "PASS" if ok else "FAIL"
        print(f"{ei} -> {status} ({code}) - {msg}")
