#!/usr/bin/env python3
"""Import HL7 files missing PV1 by creating minimal Patient/Dossier/Venue and extracting ZBE movements.

Usage: python3 tools/import_pv1_fallback.py
"""
from pathlib import Path
import json
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine
from app.models import Patient, Dossier, Venue, Mouvement, Sequence

BASE = Path(__file__).parent.parent
PAM_DIR = BASE / 'tests' / 'exemples' / 'Fichier_test_pam'

def get_next_sequence(session: Session, name: str) -> int:
    seq = session.exec(select(Sequence).where(Sequence.name == name)).first()
    if not seq:
        seq = Sequence(name=name, value=1)
        session.add(seq)
        session.flush()
        return seq.value
    seq.value += 1
    session.add(seq)
    session.flush()
    return seq.value

def parse_hl7_ts(raw: str):
    if not raw:
        return None
    import re
    m = re.match(r"^(\d+)", raw)
    if not m:
        return None
    digits = m.group(1)
    fmts = [('%Y%m%d%H%M%S',14),('%Y%m%d%H%M',12),('%Y%m%d%H',10),('%Y%m%d',8)]
    from datetime import datetime as _dt
    for fmt, needed in fmts:
        s = digits
        if len(s) < needed:
            s = s.ljust(needed,'0')
        elif len(s) > needed:
            s = s[:needed]
        try:
            return _dt.strptime(s, fmt)
        except Exception:
            continue
    return None

def import_file(session: Session, path: Path):
    content = path.read_text(encoding='utf-8', errors='ignore')
    content = content.replace('\r\n','\r').replace('\n','\r')
    segments = content.split('\r')
    pid = None
    zbe = None
    for s in segments:
        if s.startswith('PID|'):
            pid = s
        if s.startswith('ZBE|'):
            zbe = s

    if not pid:
        return {'file': path.name, 'status':'no_pid'}

    pid_fields = pid.split('|')
    pid_id = pid_fields[3].split('^')[0] if len(pid_fields) > 3 and pid_fields[3] else None
    name = pid_fields[5].split('^') if len(pid_fields) > 5 and pid_fields[5] else []
    family = name[0] if name and name[0] else 'Inconnu'
    given = name[1] if len(name) > 1 and name[1] else None

    # create or find patient
    patient = session.exec(select(Patient).where(Patient.identifier == pid_id)).first()
    if not patient:
        patient = Patient(identifier=pid_id, family=family, given=given)
        session.add(patient)
        session.flush()

    # create dossier
    d_seq = get_next_sequence(session,'dossier')
    dossier = Dossier(dossier_seq=d_seq, patient_id=patient.id, admit_time=datetime.utcnow())
    session.add(dossier)
    session.flush()

    # create venue
    v = Venue(venue_seq=get_next_sequence(session,'venue'), dossier_id=dossier.id, patient_id=patient.id, start_time=datetime.utcnow(), entite_juridique_id=1)
    session.add(v)
    session.flush()

    mouvements = []
    if zbe:
        zf = zbe.split('|')
        # simple heuristic: try f2 or f6
        raw_dt = zf[2] if len(zf) > 2 and zf[2] else (zf[6] if len(zf) > 6 and zf[6] else None)
        action = None
        for idx in (3,4,5):
            if len(zf) > idx and zf[idx]:
                action = zf[idx]; break

        dt = parse_hl7_ts(raw_dt)
        if dt:
            m = Mouvement(mouvement_seq=get_next_sequence(session,'mouvement'), venue_id=v.id, when=dt, action=action)
            session.add(m)
            session.flush()
            mouvements.append(m.mouvement_seq)

    session.commit()
    return {'file': path.name, 'status':'imported', 'patient': patient.identifier, 'venue_seq': v.venue_seq, 'mouvements': mouvements}

def main():
    hl7_files = sorted(PAM_DIR.glob('*.hl7'))
    # detect files with PV1 missing by reusing our previous report: simple scan
    missing = []
    for p in hl7_files:
        txt = p.read_text(encoding='utf-8', errors='ignore').replace('\r\n','\r').replace('\n','\r')
        if '\rPV1|' not in txt and '\rPV1|' not in ('\r'+txt):
            # check if there is a PID and ZBE
            if '\rPID|' in txt:
                missing.append(p)

    results = []
    with Session(engine) as s:
        for p in missing:
            try:
                r = import_file(s,p)
                results.append(r)
            except Exception as e:
                s.rollback()
                results.append({'file':p.name,'status':'error','error':str(e)})

    out = {'checked': len(hl7_files), 'missing_pv1_count': len(missing), 'results': results}
    print(json.dumps(out, indent=2))
    # write report
    rp = Path('reports') / 'pam_pv1_fallback_report.json'
    rp.write_text(json.dumps(out, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
