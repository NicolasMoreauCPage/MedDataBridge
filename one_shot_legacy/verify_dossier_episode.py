"""Script de vérification dossier complet.

Crée un Patient + Dossier, génère les messages HL7 & FHIR (via services existants)
Puis vérifie la continuité des valeurs clés:
  - HL7: Trigger ADT^A05, PID-18 (account number = dossier_seq), PV1-3 (UF), ZBE-8/7 (UF XON miniature), email présent dans PID-13
  - FHIR Bundle: Patient.telecom email, Encounter.period.start = admit_time, EpisodeOfCare.status, EpisodeOfCare.managingOrganization

Ce script n'effectue PAS d'envoi réseau: il utilise generate_pam_hl7 et generate_fhir directement.
Exécution:
  python -m one_shot_legacy.verify_dossier_episode
"""
from datetime import datetime
from sqlmodel import Session

from app.db import session_factory, init_db
from app.models import Patient, Dossier
from app.services.emit_on_create import generate_pam_hl7, generate_fhir
from app.services.fhir import generate_fhir_bundle_for_dossier


def _extract_segment(message: str, seg_id: str):
    return next((line for line in message.split('\r') if line.startswith(seg_id + '|')), '')


def run():
    init_db()
    # Ouverture session DB
    with session_factory() as session:
        # 1. Créer Patient complet
        patient = Patient(
            family="DUPONT",
            given="Alice",
            birth_date="1985-07-21",
            gender="F",
            address="12 rue des Fleurs",
            city="Paris",
            postal_code="75001",
            country="FR",
            phone="0102030405",
            email="alice.dupont@example.org",
            marital_status="M",
            identity_reliability_code="QUAL",
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        # 2. Créer Dossier (pré-admission A05)
        dossier = Dossier(
            patient_id=patient.id,
            admit_time=datetime.utcnow(),
            dossier_type="hospitalise",  # Enum handled by SQLModel
            uf_responsabilite="UF1234",
            admission_type="ELECT",
            admission_source="DOMICILE",
            attending_provider="Dr Martin",
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)

        # 3. Générer HL7 & FHIR
        hl7_msg = generate_pam_hl7(dossier, "dossier", session)
        fhir_bundle = generate_fhir_bundle_for_dossier(dossier, session)

        # 4. Analyse HL7
        msh = _extract_segment(hl7_msg, "MSH")
        pid = _extract_segment(hl7_msg, "PID")
        pv1 = _extract_segment(hl7_msg, "PV1")
        zbe = _extract_segment(hl7_msg, "ZBE")

        issues = []
        if "ADT^A05" not in msh:
            issues.append("MSH trigger n'est pas ADT^A05")
        # PID-18 account number check
        pid_fields = pid.split('|')
        account_number = pid_fields[18] if len(pid_fields) > 18 else ''
        if account_number != str(dossier.dossier_seq):
            issues.append(f"PID-18 attendu {dossier.dossier_seq} trouvé '{account_number}'")
        # Email presence (PID-13) -> field index 13 contains XTN repetitions
        # We already rely on emission logic: just verify substring
        if patient.email and patient.email not in pid:
            issues.append("Email patient absent du segment PID")
        # Gender continuity (PID-8)
        if patient.gender:
            gender_map_hl7 = {
                "m": "M", "male": "M",
                "f": "F", "female": "F",
                "o": "O", "other": "O",
                "u": "U", "unknown": "U", "undifferentiated": "U", "n": "U"
            }
            expected_hl7_gender = gender_map_hl7.get(patient.gender.lower(), patient.gender.upper())
            pid_gender = pid_fields[8] if len(pid_fields) > 8 else ''
            if pid_gender != expected_hl7_gender:
                issues.append(f"PID-8 sexe attendu {expected_hl7_gender} trouvé '{pid_gender}'")
        # PV1-3 location
        pv1_fields = pv1.split('|')
        pv1_location = pv1_fields[3] if len(pv1_fields) > 3 else ''
        if pv1_location != dossier.uf_responsabilite:
            issues.append(f"PV1-3 location attendu {dossier.uf_responsabilite} trouvé '{pv1_location}'")
        # ZBE UF repetition minimal: last field should contain UF^^^{location}
        if dossier.uf_responsabilite and dossier.uf_responsabilite not in zbe:
            issues.append("UF responsabilité absente du segment ZBE")

        # 5. Analyse FHIR Bundle
        entries = {e['resource']['resourceType']: e['resource'] for e in fhir_bundle.get('entry', [])}
        patient_res = entries.get('Patient')
        enc_res = entries.get('Encounter')
        eoc_res = entries.get('EpisodeOfCare')

        if not eoc_res:
            issues.append("EpisodeOfCare manquant dans le Bundle")
        else:
            # Status continuity
            if dossier.discharge_time is None and eoc_res.get('status') not in ('active', 'planned'):
                issues.append(f"Status EpisodeOfCare incohérent: {eoc_res.get('status')}")
            # Admit time continuity
            start = eoc_res.get('period', {}).get('start')
            if not start or start[:19] != dossier.admit_time.isoformat()[:19]:  # compare up to seconds
                issues.append("EpisodeOfCare.period.start ne correspond pas à admit_time dossier")
            # managingOrganization continuity
            if dossier.uf_responsabilite and dossier.uf_responsabilite not in str(eoc_res.get('managingOrganization', {})):
                issues.append("managingOrganization ne contient pas l'UF responsabilité")

        if patient_res and patient.email:
            telecom_emails = [t.get('value') for t in patient_res.get('telecom', []) if t.get('system') == 'email']
            if patient.email not in telecom_emails:
                issues.append("Email patient absent de Patient.telecom")
        # FHIR gender continuity (Patient.gender) mapping already handled; ensure lower case values
        if patient_res and patient.gender:
            gender_val = patient_res.get('gender')
            # Accept legacy uppercase single-letter codes (M/F/O/U) for transitional data
            allowed = {'male','female','other','unknown','M','F','O','U'}
            if gender_val not in allowed:
                issues.append(f"Patient.gender valeur non conforme '{gender_val}'")

        if enc_res:
            enc_start = enc_res.get('period', {}).get('start')
            if not enc_start or enc_start[:19] != dossier.admit_time.isoformat()[:19]:
                issues.append("Encounter.period.start ne correspond pas à admit_time dossier")

        print("HL7 MESSAGE:\n" + hl7_msg.replace('\r', '\n'))
        print("\nFHIR BUNDLE:")
        import json as _json
        print(_json.dumps(fhir_bundle, indent=2, ensure_ascii=False))

        if issues:
            print("\nRESULTAT: ECHEC - incohérences détectées:")
            for i in issues:
                print(" -", i)
        else:
            print("\nRESULTAT: SUCCES - toutes les vérifications de continuité passent.")

if __name__ == "__main__":
    run()
