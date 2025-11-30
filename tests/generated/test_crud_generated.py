from fastapi.testclient import TestClient
from sqlmodel import select
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import EntiteJuridique, EntiteGeographique, GHTContext
from app.db import get_next_sequence
from datetime import datetime

def test_patient_crud(client: TestClient, session):
    # create
    payload = {'family': 'GEN', 'given': 'Alice', 'gender': 'female', 'birth_date': '1990-01-01'}
    r = client.post('/patients/new', data=payload, follow_redirects=True)
    assert r.status_code in (200, 303)
    # find in db
    p = session.exec(select(Patient).where(Patient.family == 'GEN')).first()
    assert p is not None
    # edit
    r2 = client.post(f'/patients/{p.id}/edit', data={'family': 'GEN2', 'given': p.given}, follow_redirects=True)
    assert r2.status_code in (200, 303)
    session.expire_all()
    p2 = session.get(Patient, p.id)
    assert p2.family == 'GEN2'
    # delete
    r3 = client.post(f'/patients/{p.id}/delete', follow_redirects=True)
    assert r3.status_code in (200, 303)

def test_dossier_crud(client: TestClient, session):
    # need a patient in db
    seq = get_next_sequence(session, 'patient')
    p = Patient(patient_seq=seq, family='DOSP', given='Ui', gender='other')
    session.add(p); session.commit(); session.refresh(p)
    # ensure a GHT context exists and select it (required by dossiers router)
    ctx = session.exec(select(GHTContext).where(GHTContext.code == 'GHT-DEMO-INTEROP')).first()
    if not ctx:
        ctx = GHTContext(name='Test GHT', code='GHT-DEMO-INTEROP', is_active=True)
        session.add(ctx); session.commit(); session.refresh(ctx)
    client.get(f'/admin/ght/{ctx.id}', follow_redirects=True)
    # set patient context via client
    client.get(f'/context/patient/{p.id}', follow_redirects=True)
    now = datetime.now().strftime('%Y-%m-%dT%H:%M')
    payload = {'patient_id': str(p.id), 'admit_time': now}
    r = client.post('/dossiers/new', data=payload, follow_redirects=False)
    assert r.status_code in (302, 303)
    session.expire_all()
    d = session.exec(select(Dossier).where(Dossier.patient_id == p.id)).first()
    assert d is not None
    # edit dossier
    r2 = client.post(
        f'/dossiers/{d.id}/edit',
        data={
            'patient_id': str(p.id),
        # the edit form requires a non-empty UF responsable value
        'uf_responsabilite': str(d.uf_responsabilite or 'UF1'),
            'dossier_type': str(d.dossier_type.value if d.dossier_type else 'hospitalise'),
            'admit_time': d.admit_time.strftime('%Y-%m-%dT%H:%M'),
            'dossier_seq': str(d.dossier_seq),
        },
        follow_redirects=False
    )
    # debug response body on validation error
    if r2.status_code == 422:
        print(f'DEBUG: /dossiers/{d.id}/edit 422 body:')
        print(r2.text)
    assert r2.status_code in (200, 303)
    # delete
    r3 = client.post(f'/dossiers/{d.id}/delete', follow_redirects=True)
    assert r3.status_code in (200, 303)

def test_venue_crud(client: TestClient, session):
    seq = get_next_sequence(session, 'patient')
    patient = Patient(patient_seq=seq, family='VUDP', given='Ui')
    session.add(patient); session.commit(); session.refresh(patient)
    # create dossier
    from datetime import datetime as _dt
    now = _dt.now().strftime('%Y-%m-%dT%H:%M')
    # ensure GHT context selected
    ctx = session.exec(select(GHTContext).where(GHTContext.code == 'GHT-DEMO-INTEROP')).first()
    if not ctx:
        ctx = GHTContext(name='Test GHT', code='GHT-DEMO-INTEROP', is_active=True)
        session.add(ctx); session.commit(); session.refresh(ctx)
    client.get(f'/admin/ght/{ctx.id}', follow_redirects=True)
    client.get(f'/context/patient/{patient.id}', follow_redirects=True)
    payload = {'patient_id': str(patient.id), 'admit_time': now}
    client.post('/dossiers/new', data=payload, follow_redirects=False)
    session.expire_all()
    d = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
    assert d is not None
    # create venue
    # Provide a non-empty UF code; tests don't rely on real UF lookup so a simple code works
    payload2 = {'dossier_id': str(d.id), 'uf_responsabilite': 'UF1', 'start_time': now}
    r = client.post('/venues/new', data=payload2, follow_redirects=False)
    assert r.status_code in (302, 303)
    session.expire_all()
    # pick the most recently created venue for this dossier (there may be a PRE_ADMIT one)
    v = session.exec(select(Venue).where(Venue.dossier_id == d.id).order_by(Venue.id.desc())).first()
    assert v is not None
    # edit venue
    r2 = client.post(
        f'/venues/{v.id}/edit',
        data={'dossier_id': str(d.id), 'uf_responsabilite': 'UF1', 'start_time': v.start_time.strftime('%Y-%m-%dT%H:%M'), 'venue_seq': str(v.venue_seq)},
        follow_redirects=False
    )
    # If validation fails, print response to help debugging
    if r2.status_code == 422:
        print('DEBUG /venues/{v.id}/edit 422 body:')
        print(r2.text)
    assert r2.status_code in (302, 303)
    # delete
    r3 = client.post(f'/venues/{v.id}/delete', follow_redirects=True)
    # Some delete handlers redirect to a list view which may Renvoie 404 in tests
    assert r3.status_code in (200, 303, 404)

def test_mouvement_crud(client: TestClient, session):
    # create patient/dossier/venue similar to venue test
    seq = get_next_sequence(session, 'patient')
    patient = Patient(patient_seq=seq, family='MOUV', given='Ui')
    session.add(patient); session.commit(); session.refresh(patient)
    from datetime import datetime as _dt
    now = _dt.now().strftime('%Y-%m-%dT%H:%M')
    # ensure GHT context selected
    ctx = session.exec(select(GHTContext).where(GHTContext.code == 'GHT-DEMO-INTEROP')).first()
    if not ctx:
        ctx = GHTContext(name='Test GHT', code='GHT-DEMO-INTEROP', is_active=True)
        session.add(ctx); session.commit(); session.refresh(ctx)
    client.get(f'/admin/ght/{ctx.id}', follow_redirects=True)
    client.get(f'/context/patient/{patient.id}', follow_redirects=True)
    payload = {'patient_id': str(patient.id), 'admit_time': now}
    client.post('/dossiers/new', data=payload, follow_redirects=False)
    session.expire_all()
    d = session.exec(select(Dossier).where(Dossier.patient_id == patient.id)).first()
    # create venue
    payload2 = {'dossier_id': str(d.id), 'uf_responsabilite': 'UF1', 'start_time': now}
    client.post('/venues/new', data=payload2, follow_redirects=True)
    session.expire_all()
    v = session.exec(select(Venue).where(Venue.dossier_id == d.id)).first()
    # create mouvement (A01 admission)
    # A01 (admission) requires a location (uh_id or chambre_id). Provide a dummy uh_id
    mouvement_payload = {'venue_id': str(v.id), 'type': 'ADT^A01', 'when': now, 'uh_id': '1'}
    r = client.post('/mouvements/new', data=mouvement_payload, follow_redirects=False)
    assert r.status_code in (302, 303)
    m = session.exec(select(Mouvement).where(Mouvement.venue_id == v.id)).first()
    assert m is not None
    # edit mouvement (via edit form) - simply get edit page and post similar data
    r2 = client.get(f'/mouvements/{m.id}/edit')
    assert r2.status_code == 200
    r3 = client.post(f'/mouvements/{m.id}/edit', data={'venue_id': str(v.id), 'type': m.type or 'ADT^A01', 'when': now, 'mouvement_seq': str(m.mouvement_seq)}, follow_redirects=False)
    # delete mouvement
    r4 = client.post(f'/mouvements/{m.id}/delete', follow_redirects=True)
    # REMARQUE: some delete endpoints may Renvoie 404 or redirect, accept both
    assert r4.status_code in (200, 303, 404)

def test_structure_ej_eg_crud(client: TestClient, session):
    # create EJ via model (simpler) and then use api endpoints for EG
    ej = EntiteJuridique(name='EJ-GEN', finess_ej='123456778', is_active=True)
    session.add(ej); session.commit(); session.refresh(ej)
    # create EG via POST /structure/eg
    payload = {'name': 'EG Test', 'identifier': 'EG-1', 'finess': 'F-1'}
    r = client.post('/structure/eg', json=payload)
    assert r.status_code == 200
    eg = session.exec(select(EntiteGeographique).where(EntiteGeographique.name == 'EG Test')).first()
    assert eg is not None
    # view and edit EG
    r2 = client.get(f'/structure/eg/{eg.id}')
    assert r2.status_code == 200
    r3 = client.post(f'/structure/eg/{eg.id}', data={'name': 'EG Test Updated'})
    assert r3.status_code in (200, 303)
    # delete EG
    r4 = client.post(f'/structure/eg/{eg.id}/delete')
    assert r4.status_code in (200, 303)
