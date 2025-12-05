# Outbox configuration for generated artifacts

The repository provides a small harness which writes generated MFN/PAM/FHIR
artifacts to disk. The harness will choose the output directory in the
following order of preference:

1. `MEDBRIDGE_OUT_DIR` environment variable (if set)

2. repository-local `tmp/generated` (created automatically)

3. `/tmp/medbridge_generated` (fallback)

To force a repo-local outbox, simply run the harness without setting
`MEDBRIDGE_OUT_DIR`. To override and use a custom path, set `MEDBRIDGE_OUT_DIR`
to an absolute path before running the scripts.

# Helper script
We include a helper script to create three idempotent FILE endpoints in the
application database (useful for development):

.venv/bin/python3 scripts/setup_file_endpoints.py

It will ensure these endpoints exist and point to `ROOT/tmp/generated`:

- `FILE PAM` (emit_hl7_pam)

- `FILE MFN` (emit_hl7_mfn)

- `FILE FHIR` (emit_fhir_structure)

# Permissions
Make sure the user running the FastAPI service or these scripts has write
permissions on the chosen outbox directory.
