from sqlmodel import Session, select
from app.db import engine
from app.models import Patient, Dossier, Venue, Mouvement
from app.models_structure import EntiteJuridique

with Session(engine) as session:
    print("--- Entités Juridiques (EJ) ---")
    for ej in session.exec(select(EntiteJuridique)).all():
        print(f"EJ: {ej.id} | {ej.name} | FINESS: {ej.finess_ej}")
        nb_patients = len(list(session.exec(select(Patient).where(Patient.entite_juridique_id == ej.id))))
        nb_dossiers = len(list(session.exec(select(Dossier).where(Dossier.entite_juridique_id == ej.id))))
        nb_venues = len(list(session.exec(select(Venue).where(Venue.entite_juridique_id == ej.id))))
        nb_mouvements = len(list(session.exec(select(Mouvement).join(Venue, Mouvement.venue_id == Venue.id).where(Venue.entite_juridique_id == ej.id))))
        print(f"  Patients: {nb_patients}")
        print(f"  Dossiers: {nb_dossiers}")
        print(f"  Séjours (Venues): {nb_venues}")
        print(f"  Mouvements: {nb_mouvements}")
    print("\n--- Patients sans EJ ---")
    nb_patients_noej = len(list(session.exec(select(Patient).where(Patient.entite_juridique_id == None))))
    print(f"Patients sans EJ: {nb_patients_noej}")
    print("--- Dossiers sans EJ ---")
    nb_dossiers_noej = len(list(session.exec(select(Dossier).where(Dossier.entite_juridique_id == None))))
    print(f"Dossiers sans EJ: {nb_dossiers_noej}")
