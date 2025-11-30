import json
from sqlmodel import Session, select, SQLModel
from app.db import engine
from app.models_structure import EntiteJuridique
from app.converters.fhir_import_converter import FHIRToEncounterConverter, FHIRBundleImporter


def test_extract_id_from_reference_variants():
    shared_map = {
        'pat-1': 10,
        'Patient/pat-1': 10,
        'Encounter/enc-2': 20
    }

    conv = FHIRToEncounterConverter(Session(engine), resource_map=shared_map)

    # bare id
    assert conv._extract_id_from_reference('pat-1') == 10

    # type/id
    assert conv._extract_id_from_reference('Patient/pat-1') == 10

    # URL ending with type/id
    assert conv._extract_id_from_reference('http://example.org/fhir/Patient/pat-1') == 10

    # leading '#'
    assert conv._extract_id_from_reference('#pat-1') == 10

    # numeric id
    assert conv._extract_id_from_reference('123') == 123

    # missing -> None
    assert conv._extract_id_from_reference('unknown-id') is None


def test_import_debug_bundle_roundtrip(tmp_path):
    # ensure DB tables
    SQLModel.metadata.create_all(engine)

    # load debug bundle from tmp in repo
    bundle_path = 'tmp/fhir_bundle_for_import_debug.json'
    with open(bundle_path, 'r', encoding='utf-8') as f:
        bundle = json.load(f)

    with Session(engine) as s:
        # ensure EJ exists
        ej = s.exec(select(EntiteJuridique)).first()
        if not ej:
            ej = EntiteJuridique(name='TEST EJ', code='TEST', finess='000000')
            s.add(ej); s.commit(); s.refresh(ej)

        importer = FHIRBundleImporter(s, ej)
        results = importer.import_bundle(bundle)

        assert results['errors'] == []
        assert results['patients'] >= 1
        assert results['encounters'] >= 1
