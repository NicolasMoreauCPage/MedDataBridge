from app.db import session_factory
from app.services.mfn_structure import generate_mfn_message
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit
)
from sqlmodel import select


def test_generate_mfn_includes_all_types_and_lrl():
    s = session_factory()
    try:
        # Create a small hierarchy explicitly for the test
        eg = EntiteGeographique(identifier="TEST-EG-1", name="Test EG 1")
        s.add(eg)
        s.commit()
        s.refresh(eg)

        pole = Pole(identifier="TEST-POLE-1", entite_geo_id=eg.id, name="Pole 1")
        s.add(pole)
        s.commit()
        s.refresh(pole)

        service = Service(identifier="TEST-SVC-1", pole_id=pole.id, name="Service 1")
        s.add(service)
        s.commit()
        s.refresh(service)

        uf = UniteFonctionnelle(identifier="TEST-UF-1", service_id=service.id, name="UF 1")
        s.add(uf)
        s.commit()
        s.refresh(uf)

        uh = UniteHebergement(identifier="TEST-UH-1", unite_fonctionnelle_id=uf.id, name="UH 1")
        s.add(uh)
        s.commit()
        s.refresh(uh)

        chambre = Chambre(identifier="TEST-CH-1", unite_hebergement_id=uh.id, name="Chambre 1")
        s.add(chambre)
        s.commit()
        s.refresh(chambre)

        lit = Lit(identifier="TEST-LIT-1", chambre_id=chambre.id, name="Lit 1")
        s.add(lit)
        s.commit()
        s.refresh(lit)

        # Generate MFN for the EG
        mfn = generate_mfn_message(s, eg_identifier=eg.identifier)
        lines = [l.strip() for l in mfn.splitlines() if l.strip()]

        # Check MFE entries exist for each created entity
        assert any(f"^^^^^M^^^^{eg.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for EG"
        assert any(f"^^^^^P^^^^{pole.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for Pole"
        assert any(f"^^^^^D^^^^{service.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for Service"
        assert any(f"^^^^^UF^^^^{uf.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for UF"
        assert any(f"^^^^^UH^^^^{uh.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for UH"
        assert any(f"^^^^^CH^^^^{chambre.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for Chambre"
        assert any(f"^^^^^LIT^^^^{lit.identifier}" in l and l.startswith("MFE") for l in lines), "Missing MFE for Lit"

        # Check at least one LRL segment exists for relations
        assert any(l.startswith("LRL|") for l in lines), "No LRL segments emitted"

    finally:
        s.close()
