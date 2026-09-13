from app.models import Patient


def test_merge_form_renders(client, session):
    p1 = Patient(patient_seq=1, identifier="IPP001", family="DOE", given="JOHN")
    p2 = Patient(patient_seq=2, identifier="IPP002", family="DOE", given="JOHNNY")
    session.add(p1)
    session.add(p2)
    session.commit()

    resp = client.get("/patients/merge")
    assert resp.status_code == 200
    assert "Fusionner" in resp.text
    assert "IPP001" in resp.text
    assert "IPP002" in resp.text
    assert "MRG-1" in resp.text

    preselected = client.get(f"/patients/merge?source_patient_id={p2.id}")
    assert f'value="{p2.id}" data-identifier="IPP002" selected' in preselected.text


def test_merge_submit_redirects_to_survivor(client, session):
    p1 = Patient(patient_seq=3, identifier="IPP003", family="MARTIN", given="ALICE")
    p2 = Patient(patient_seq=4, identifier="IPP004", family="MARTIN", given="ALICIA")
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    resp = client.post(
        "/patients/merge",
        data={"source_patient_id": p2.id, "surviving_patient_id": p1.id},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/patients/{p1.id}"


def test_change_identifier_form_renders(client, session):
    p = Patient(patient_seq=5, identifier="IPP005", family="DUPONT", given="PAUL")
    session.add(p)
    session.commit()
    session.refresh(p)

    resp = client.get(f"/patients/{p.id}/change-identifier")
    assert resp.status_code == 200
    assert "IPP005" in resp.text
    assert "MRG-1" in resp.text
    assert "data-confirm" in resp.text


def test_patient_detail_exposes_a40_and_a47_actions(client, session):
    p = Patient(patient_seq=15, identifier="IPP015", family="DUPONT", given="Alice")
    session.add(p)
    session.commit()
    session.refresh(p)

    resp = client.get(f"/patients/{p.id}")

    assert resp.status_code == 200
    assert f"/patients/{p.id}/change-identifier" in resp.text
    assert f"/patients/merge?source_patient_id={p.id}" in resp.text


def test_change_identifier_submit_redirects(client, session):
    p = Patient(patient_seq=6, identifier="IPP006", family="DUPONT", given="PAULA")
    session.add(p)
    session.commit()
    session.refresh(p)

    resp = client.post(
        f"/patients/{p.id}/change-identifier",
        data={"new_value": "IPP006-NEW", "new_system": "HOSP"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/patients/{p.id}"
