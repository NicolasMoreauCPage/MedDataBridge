from app.services.fhir_profile_validator import FHIRProfileValidator


def test_validate_bundle_strict_valid_patient_and_encounter():
    validator = FHIRProfileValidator()
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "identifier": [{"system": "urn:oid:1.2.250.1.213", "value": "PAT-001"}],
                    "name": [{"family": "DUPONT", "given": ["ALICE"]}],
                    "gender": "female",
                    "birthDate": "1990-01-01",
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "status": "in-progress",
                    "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "IMP"},
                    "subject": {"reference": "Patient/PAT-001"},
                    "period": {"start": "2026-03-28T09:00:00Z"},
                }
            },
        ],
    }

    report = validator.validate_bundle(bundle, strict=True, profile="fr-core")
    assert report.valid is True
    assert report.errors == []
    assert report.resource_count == 2


def test_validate_bundle_strict_rejects_missing_patient_identifier():
    validator = FHIRProfileValidator()
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "name": [{"family": "DOE", "given": ["JOHN"]}],
                    "gender": "male",
                }
            }
        ],
    }

    report = validator.validate_bundle(bundle, strict=True)
    assert report.valid is False
    assert any("identifier requis" in err for err in report.errors)


def test_validate_bundle_non_strict_downgrades_bundle_type_issue_to_warning():
    validator = FHIRProfileValidator()
    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "entry": [],
    }

    report = validator.validate_bundle(bundle, strict=False)
    assert report.valid is True
    assert any("Type de bundle 'document'" in w for w in report.warnings)


def test_validate_bundle_endpoint_uses_strict_profile_validator(client):
    payload = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "identifier": [{"system": "urn:oid:1.2.250.1.213", "value": "PAT-001"}],
                    "name": [{"family": "MARTIN", "given": ["LUC"]}],
                    "gender": "male",
                }
            }
        ],
    }

    response = client.post("/api/fhir/validate/bundle?strict=true&profile=fr-core", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["strict"] is True
    assert body["profile"] == "fr-core"
    assert body["valid"] is True
    assert body["resource_count"] == 1
