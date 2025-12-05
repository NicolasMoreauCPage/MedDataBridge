#!/usr/bin/env python3
"""Idempotent helper: create FILE endpoints pointing to repo tmp/generated

Usage:
  .venv/bin/python3 scripts/setup_file_endpoints.py

This script is safe to run multiple times and will print created/updated rows.
"""
from app.db import session_factory
from app.models_shared import SystemEndpoint


def main():
    s = session_factory()
    path = __import__('pathlib').Path(__file__).resolve().parents[1] / 'tmp' / 'generated'
    path.mkdir(parents=True, exist_ok=True)
    created = []
    updated = []
    with s as session:
        def ensure(name, emit_pam=False, emit_mfn=False, emit_fhir=False):
            ep = session.query(SystemEndpoint).filter(SystemEndpoint.name == name).one_or_none()
            if ep:
                changed = False
                if ep.kind != 'FILE':
                    ep.kind = 'FILE'
                    changed = True
                if ep.outbox_path != str(path):
                    ep.outbox_path = str(path)
                    changed = True
                ep.is_enabled = True
                ep.emit_hl7_pam = emit_pam
                ep.emit_hl7_mfn = emit_mfn
                ep.emit_fhir_structure = emit_fhir
                session.add(ep)
                if changed:
                    updated.append(ep.name)
                return ep
            else:
                ep = SystemEndpoint(
                    name=name,
                    kind='FILE',
                    outbox_path=str(path),
                    is_enabled=True,
                    emit_hl7_pam=emit_pam,
                    emit_hl7_mfn=emit_mfn,
                    emit_fhir_structure=emit_fhir,
                )
                session.add(ep)
                session.commit()
                created.append(ep.name)
                return ep

        ensure('FILE PAM', emit_pam=True)
        ensure('FILE MFN', emit_mfn=True)
        ensure('FILE FHIR', emit_fhir=True)
        session.commit()

    print('Created endpoints:', created)
    print('Updated endpoints:', updated)
    print('Outbox directory:', path)


if __name__ == '__main__':
    main()
