# tests/unit/test_fhir_export.py
"""
Tests unitaires pour l'export FHIR.
"""

from sqlmodel import select
from sqlalchemy import event
from datetime import datetime
import inspect

from app.models import Patient, Dossier, Venue
from app.models_structure import EntiteGeographique, EntiteJuridique, GHTContext, Pole, Service, UniteFonctionnelle
from app.converters.fhir_converter import FHIRBundle
from app.routers import fhir_export
from app.services.fhir_export_service import FHIRExportService


class TestFHIRExport:
    """Tests pour l'export FHIR"""

    def test_sqlmodel_export_routes_are_sync(self):
        """FastAPI exécute ces exports SQL synchrones dans son pool de threads."""
        assert not inspect.iscoroutinefunction(fhir_export.export_structure)
        assert not inspect.iscoroutinefunction(fhir_export.export_patients)
        assert not inspect.iscoroutinefunction(fhir_export.export_venues)
        assert not inspect.iscoroutinefunction(fhir_export.export_all)
        assert not inspect.iscoroutinefunction(fhir_export.export_statistics)

    def test_export_structure_success(self, client, session):
        """Test export structure FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Exécution
        response = client.get(f"/api/fhir/export/structure/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "resourceType" in data
        assert data["resourceType"] == "Bundle"
        assert "entry" in data

    def test_export_structure_not_found(self, client, session):
        """Test export structure FHIR - EJ non trouvée"""
        # Exécution avec ID inexistant
        response = client.get("/api/fhir/export/structure/99999")

        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entité juridique non trouvée" in data["detail"]

    def test_export_patient_success(self, client, session):
        """Test export patients FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Créer un patient
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()

        # Exécution - export de tous les patients de l'EJ
        response = client.get(f"/api/fhir/export/patients/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "resourceType" in data
        assert data["resourceType"] == "Bundle"
        assert "entry" in data

    def test_export_patients_not_found(self, client, session):
        """Test export patients FHIR - EJ non trouvée"""
        # Exécution avec ID EJ inexistant
        response = client.get("/api/fhir/export/patients/99999")

        # Vérifications
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Entité juridique non trouvée" in data["detail"]

    def test_export_patients_applies_a_bounded_page_and_exposes_total(self, session):
        ght = GHTContext(name="Pagination GHT", code="PAGINATION")
        ej = EntiteJuridique(name="Pagination EJ", code="PAGINATION-EJ", ght_context=ght)
        session.add_all([ght, ej])
        session.flush()
        for index in range(3):
            patient = Patient(family=f"Pagination {index}", given="Patient")
            session.add(patient)
            session.flush()
            session.add(
                Dossier(
                    dossier_seq=78_000 + index,
                    patient_id=patient.id,
                    admit_time=datetime.utcnow(),
                )
            )
        session.commit()

        bundle = FHIRExportService(session, "http://localhost/fhir", enable_cache=False).export_patients(
            ej,
            limit=1,
            offset=1,
        )

        assert bundle.total >= 3
        assert len(bundle.entry) == 1
        assert bundle.meta["offset"] == 1
        assert bundle.meta["limit"] == 1

    def test_export_venues_forwards_a_bounded_page_to_the_service(self, client, session, monkeypatch):
        ght = GHTContext(name="Venues GHT", code="VENUES-PAGINATION")
        session.add(ght)
        session.flush()
        ej = EntiteJuridique(name="Venues EJ", code="VENUES-EJ", ght_context_id=ght.id)
        session.add(ej)
        session.commit()
        captured = {}

        def export_page(_self, _ej, *, limit, offset):
            captured.update(limit=limit, offset=offset)
            return FHIRBundle(type="collection", entry=[], total=0, meta={"offset": offset, "limit": limit})

        monkeypatch.setattr(FHIRExportService, "export_venues", export_page)

        response = client.get(f"/api/fhir/export/venues/{ej.id}?limit=25&offset=50")

        assert response.status_code == 200
        assert captured == {"limit": 25, "offset": 50}

    def test_export_venues_applies_a_page_to_a_real_ej_graph(self, session):
        ght = GHTContext(name="Venues service GHT", code="VENUES-SERVICE")
        session.add(ght)
        session.flush()
        ej = EntiteJuridique(name="Venues service EJ", code="VENUES-SERVICE-EJ", ght_context_id=ght.id)
        session.add(ej)
        session.flush()
        geography = EntiteGeographique(name="EG venues", entite_juridique_id=ej.id)
        session.add(geography)
        session.flush()
        pole = Pole(name="Pôle venues", entite_geo_id=geography.id)
        session.add(pole)
        session.flush()
        service = Service(name="Service venues", pole_id=pole.id)
        session.add(service)
        session.flush()
        unit = UniteFonctionnelle(name="UF venues", identifier="UF-VENUES", service_id=service.id)
        patient = Patient(family="Venue", given="Patient")
        session.add_all([unit, patient])
        session.flush()
        for index in range(3):
            dossier = Dossier(
                dossier_seq=79_001 + index,
                patient_id=patient.id,
                uf_responsabilite=unit.identifier,
                admit_time=datetime.utcnow(),
            )
            session.add(dossier)
            session.flush()
            session.add(
                Venue(
                    venue_seq=79_001 + index,
                    dossier_id=dossier.id,
                    uf_responsabilite=unit.identifier,
                    start_time=datetime.utcnow(),
                )
            )
        session.commit()

        # La taille de page ne doit pas multiplier les lectures de relations.
        # Sont attendus : total, page venues, trois relations préchargées et
        # les mouvements groupés, soit au plus sept SELECT.
        ej_id = ej.id
        session.expire_all()
        ej = session.get(EntiteJuridique, ej_id)
        statements = []

        def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(session.bind, "before_cursor_execute", count_selects)
        try:
            bundle = FHIRExportService(session, "http://localhost/fhir", enable_cache=False).export_venues(
                ej,
                limit=2,
                offset=1,
            )
        finally:
            event.remove(session.bind, "before_cursor_execute", count_selects)

        assert bundle.total == 3
        assert len(bundle.entry) == 2
        assert bundle.meta == {"offset": 1, "limit": 2}
        assert len(statements) <= 7

    def test_export_dossier_success(self, client, session):
        """Test export complet FHIR - succès"""
        # Créer des données de test
        ght = session.exec(select(GHTContext)).first()
        if not ght:
            ght = GHTContext(name="TEST", code="TEST")
            session.add(ght)
            session.commit()

        # Créer une EJ
        ej = EntiteJuridique(
            name="Test EJ",
            code="TEST_EJ",
            ght_context_id=ght.id
        )
        session.add(ej)
        session.commit()

        # Créer un patient et un dossier
        patient = Patient(family="Test", given="Patient")
        session.add(patient)
        session.commit()

        dossier = Dossier(patient_id=patient.id, admit_time=datetime.utcnow())
        session.add(dossier)
        session.commit()

        # Exécution - export complet de l'EJ
        response = client.get(f"/api/fhir/export/all/{ej.id}")

        # Vérifications
        assert response.status_code == 200
        data = response.json()
        assert "structure" in data
        assert "patients" in data
        assert "venues" in data
        assert data["patients"]["resourceType"] == "Bundle"
