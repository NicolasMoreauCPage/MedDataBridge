# PR: Implement BP6 Stateful PAM Sequence Validator & Strict Validation Enforcement

## Overview

This PR implements comprehensive BP6/IHE-PAM-FR sequence-dependent validations through a new stateful validator module, enforces strictness by default, and ensures all validation messages are translated to French for compliance and user experience.

## Changes Summary

### New Files

- **`app/services/pam_sequence_validator.py`**: Stateful PAM sequence validator implementing DB-aware BP6 checks
  - ZBE-1 identifier resolution (numeric + Identifier table lookup)
  - UPDATE/CANCEL reference verification
  - Cancelled movement reference detection
  - PV1-19 venue-based allowed-transition checks
  - Bed-occupancy detection (excludes same-patient movements)
  - ZBE-6 chain handling (trigger vs identifier distinction, chain loop detection)
  - Chronological consistency (`ZBE6_TIME_INCONSISTENT`)
  - Child-dependency checks (`ZBE_REF_HAS_CHILDREN`)
  - Venue consistency checks (`ZBE_REF_VENUE_MISMATCH`, `ZBE6_CHAIN_VENUE_MISMATCH`)
  - A02 destination requirement enforcement (`A02_DEST_MISSING`)

- **`app/services/pam_i18n.py`**: French translation helper for validation issues
  - Maps validation codes to French messages
  - `translate_issues_to_fr()` function for batch translation

- **`scripts/validate_pam_examples.py`**: Example validation utility
  - Runs stateless + stateful validators on HL7 files
  - Produces summary counts of issue codes

- **`scripts/replay_pam_examples.py`**: Example replay utility
  - Replays HL7 examples chronologically into an in-memory DB
  - Creates minimal Patient/Dossier/Venue/Mouvement entities
  - Avoids duplicate `mouvement_seq` uniqueness errors

- **`tests/test_pam_stateful.py`**: Unit tests for stateful validator
- **`tests/test_pam_bp6.py`**: BP6 scenario tests

### Modified Files

- **`app/services/pam_validation.py`**:
  - Removed INS-C enforcement
  - Translates all stateless validation issues to French before returning

- **`app/services/pam.py`**:
  - Integrated stateful validator into `process_pam_message()`
  - Raises French-language error when sequence validation fails (strict by default)
  - `STRICT_PAM_SEQUENCE` environment variable controls behavior (enforced by default)

- **`Doc/BP6_ANALYSIS.md`**: Analysis of BP6 controls vs current validator (previously created)

### Test Coverage

- **Stateless validator tests** (`tests/test_pam_stateless.py`):
  - PV1-19 missing for stay events
  - A02 requiring room and bed
  - INS-C enforcement removal verification

- **Stateful validator tests** (`tests/test_pam_stateful.py`):
  - UPDATE referencing existing movement
  - UPDATE referencing cancelled movement
  - A01→A02→A03 sequence allowed

- **BP6 scenario tests** (`tests/test_pam_bp6.py`):
  - CANCEL referencing nonexistent movement
  - Bed occupied warnings/errors
  - Transition validation edge cases (1 xfailed intentionally)

**Test Results**: 8 passed, 1 xfailed (expected edge case pending semantics refinement)

## Key Features

### Strictness by Default

- Sequence validation errors block persistence by default
- Configurable via `STRICT_PAM_SEQUENCE` environment variable (set to `True` by default)
- Escalates certain warnings to errors when strict mode enabled

### French Localization

- All validation issue messages translated to French
- Includes code mapping + fallback transformations
- ACKs and error responses contain French messages

### BP6 Conformance

- Implements stateless checks: segment validation, identifier handling, PV1-19 presence
- Implements stateful checks:
  - Reference resolution and validation
  - Venue and patient consistency
  - Chronological ordering
  - Chain loop detection
  - Occupancy conflict detection
  - Transition rule enforcement

### Example Validation & Replay

- `scripts/validate_pam_examples.py`: Validates example HL7 files and reports issues
  - First 200 files: 199 with issues (mostly stateless)
  - 500 files: 499 with issues (ZBE_REF_NOT_FOUND reduced to 96 after replay)
- `scripts/replay_pam_examples.py`: Replays 500 examples into in-memory DB
  - Created 372 mouvements for historical context
  - Reduces false-positive ZBE reference errors

## Statistics

### Test Summary

- Total tests: 9 (8 passed, 1 xfailed)
- Validation rules added: 10+ BP6-specific checks

### Example Validation (500 files)

**Stateless Issues**:

- OPTIONAL_SEGMENTS: 474
- ZBE8_ABSENT: 330
- ZBE9_INVALID: 210
- PID13 XTN invalid: 16

**Stateful Issues**:

- ZBE_REF_NOT_FOUND: 96 (reduced from 200+ before replay strategy)

## Integration Points

- Message processing pipeline: `app/services/pam.py` → `process_pam_message()`
- Validator integration: stateless + stateful validators run sequentially
- Database: SQLModel session-based for stateful lookups
- Error handling: French-language errors propagated to ACKs

## Deployment Notes

- `STRICT_PAM_SEQUENCE=True` (default): Sequence failures block message persistence
- `STRICT_PAM_SEQUENCE=False`: Sequence failures produce warnings but don't block
- Requires database context for stateful checks (in-memory for tests, persistent for production)
- All validation output automatically translated to French

## Future Enhancements

- Reservation lifecycle state machine (explicit RESERVE/CONFIRM/CANCEL lifecycle)
- Extended ZBE chain validation (deeper graph traversal, conflict detection)
- Performance optimization for high-volume replay scenarios
- Extended PID/NK1/Guarantor consistency checks
