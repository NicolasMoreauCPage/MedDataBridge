"""
Tests de conformité FRCore 2.2.0 (https://hl7.fr/ig/fhir/core/2.2.0/) pour l'export
FHIR de la hiérarchie structurelle (endpoint /api/fhir/export/structure/{ej_id},
le seul chemin d'export réellement actif) et pour les extensions Patient.

Avant cette mise en conformité, aucun test ne vérifiait le contenu des ressources
Organization/Location produites — seul le statut 200 et la présence d'un Bundle
étaient contrôlés (voir tests/unit/test_fhir_export.py). Ces tests verrouillent le
nouveau mapping : EJ/EG -> FRCoreOrganizationEtablissementProfile, Pôle/Service ->
Organization générique (FRCore 2.2.0 a supprimé le profil Pôle dédié), UF ->
FRCoreOrganizationUFProfile, UAC -> FRCoreOrganizationUACProfile (nouveau en 2.2.0,
partOf UF), UH/Chambre/Lit -> FRCoreLocationProfile (Chambre/Lit avec extensions
typeChambre/positionLit).
"""
from datetime import datetime, timezone

from sqlmodel import select

from app.models import Patient, Dossier
from app.models_structure import (
    EntiteJuridique, EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteActivite, UniteHebergement, Chambre, Lit, GHTContext,
)


def _build_full_hierarchy(session):
    ght = session.exec(select(GHTContext)).first()
    if not ght:
        ght = GHTContext(name="TEST", code="TEST-FRCORE")
        session.add(ght)
        session.commit()

    ej = EntiteJuridique(
        name="CHU Test", code="CHU_TEST", ght_context_id=ght.id,
        finess_ej="750000010", siren="123456789", siret="12345678900012",
    )
    session.add(ej)
    session.commit()

    eg = EntiteGeographique(
        name="Site Central", identifier="EG-1", finess="750000028", entite_juridique_id=ej.id,
    )
    session.add(eg)
    session.commit()

    pole = Pole(name="Pôle Médecine", identifier="POLE-1", entite_geo_id=eg.id)
    session.add(pole)
    session.commit()

    service = Service(name="Cardiologie", identifier="SERV-1", pole_id=pole.id, service_type="MCO")
    session.add(service)
    session.commit()

    uf = UniteFonctionnelle(name="UF Cardio A", identifier="UF-1", service_id=service.id)
    session.add(uf)
    session.commit()

    uac = UniteActivite(
        name="UAC Cardio A", identifier="UAC-1", unite_fonctionnelle_id=uf.id,
        discipline_prestation_code="01", tarif_code="A",
    )
    session.add(uac)
    session.commit()

    uh = UniteHebergement(name="UH Cardio A", identifier="UH-1", unite_fonctionnelle_id=uf.id)
    session.add(uh)
    session.commit()

    chambre = Chambre(name="Chambre 101", identifier="CH-101", unite_hebergement_id=uh.id, type_chambre="SEUL")
    session.add(chambre)
    session.commit()

    lit = Lit(name="Lit 101-1", identifier="LIT-101-1", chambre_id=chambre.id)
    session.add(lit)
    session.commit()

    return ej


def _entries_by_type(bundle, resource_type):
    return [
        e["resource"] for e in bundle["entry"]
        if e["resource"].get("resourceType") == resource_type
    ]


def _find_by_identifier(resources, identifier_value):
    for r in resources:
        for ident in r.get("identifier", []) or []:
            if ident.get("value") == identifier_value:
                return r
    return None


class TestFRCore220StructureExport:
    def test_full_hierarchy_export_uses_correct_resource_types(self, client, session):
        ej = _build_full_hierarchy(session)
        response = client.get(f"/api/fhir/export/structure/{ej.id}")
        assert response.status_code == 200
        bundle = response.json()

        organizations = _entries_by_type(bundle, "Organization")
        locations = _entries_by_type(bundle, "Location")

        # EJ, EG, Pôle, Service, UF, UAC -> Organization (6 niveaux)
        assert len(organizations) == 6, [o.get("name") for o in organizations]
        # UH, Chambre, Lit -> Location (3 niveaux)
        assert len(locations) == 3, [l.get("name") for l in locations]

    def test_no_legacy_or_placeholder_urls_in_structure_bundle(self, client, session):
        """Aucune URL des anciens domaines (interop-sante.fr/interopsante.org) ni des
        placeholders (example.org) ne doit apparaître dans le bundle de structure."""
        ej = _build_full_hierarchy(session)
        response = client.get(f"/api/fhir/export/structure/{ej.id}")
        bundle_text = response.text
        assert "interop-sante.fr" not in bundle_text
        assert "interopsante.org" not in bundle_text
        assert "example.org" not in bundle_text

    def test_ej_and_eg_use_etablissement_profile_with_finess(self, client, session):
        ej = _build_full_hierarchy(session)
        bundle = client.get(f"/api/fhir/export/structure/{ej.id}").json()
        organizations = _entries_by_type(bundle, "Organization")

        ej_org = next(o for o in organizations if o.get("name") == "CHU Test")
        assert ej_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization-etablissement"]
        finess_idents = [i for i in ej_org["identifier"] if i.get("system") == "https://finess.esante.gouv.fr"]
        assert finess_idents and finess_idents[0]["value"] == "750000010"
        siren_idents = [i for i in ej_org["identifier"] if i.get("system") == "https://sirene.fr" and i["type"]["coding"][0]["code"] == "SIREN"]
        assert siren_idents and siren_idents[0]["value"] == "123456789"

        eg_org = next(o for o in organizations if o.get("name") == "Site Central")
        assert eg_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization-etablissement"]
        assert eg_org["partOf"]["reference"] == f"Organization/{ej.finess_ej}"
        eg_finess_idents = [i for i in eg_org["identifier"] if i.get("system") == "https://finess.esante.gouv.fr"]
        assert eg_finess_idents and eg_finess_idents[0]["value"] == "750000028"

    def test_pole_and_service_are_generic_organization_without_dedicated_profile(self, client, session):
        """FRCore 2.2.0 a supprimé FRCoreOrganizationPoleProfile : Pôle et Service
        doivent utiliser le profil Organization de base, pas un profil spécifique."""
        ej = _build_full_hierarchy(session)
        bundle = client.get(f"/api/fhir/export/structure/{ej.id}").json()
        organizations = _entries_by_type(bundle, "Organization")

        pole_org = next(o for o in organizations if o.get("name") == "Pôle Médecine")
        assert pole_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization"]
        assert pole_org["partOf"]["reference"] == "Organization/EG-1"

        service_org = next(o for o in organizations if o.get("name") == "Cardiologie")
        assert service_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization"]
        assert service_org["partOf"]["reference"] == "Organization/POLE-1"

    def test_uf_uses_uf_profile_with_fixed_type(self, client, session):
        ej = _build_full_hierarchy(session)
        bundle = client.get(f"/api/fhir/export/structure/{ej.id}").json()
        organizations = _entries_by_type(bundle, "Organization")

        uf_org = next(o for o in organizations if o.get("name") == "UF Cardio A")
        assert uf_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization-uf"]
        assert uf_org["type"][0]["coding"][0]["code"] == "UF"
        assert uf_org["partOf"]["reference"] == "Organization/SERV-1"

    def test_uac_is_new_2_2_0_profile_child_of_uf(self, client, session):
        """L'UAC (Unité d'Activité) est un nouveau profil FRCore 2.2.0, absent de la
        2.1.0 — doit être exporté comme Organization partOf l'UF."""
        ej = _build_full_hierarchy(session)
        bundle = client.get(f"/api/fhir/export/structure/{ej.id}").json()
        organizations = _entries_by_type(bundle, "Organization")

        uac_org = next(o for o in organizations if o.get("name") == "UAC Cardio A")
        assert uac_org["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-organization-uac"]
        assert uac_org["type"][0]["coding"][0]["code"] == "UAC"
        assert uac_org["partOf"]["reference"] == "Organization/UF-1"
        discipline_ext = [e for e in uac_org["extension"] if e["url"].endswith("fr-core-organization-discipline-prestation")]
        assert discipline_ext and discipline_ext[0]["valueCoding"]["code"] == "01"

    def test_uh_chambre_lit_are_locations_with_correct_partof_chain(self, client, session):
        ej = _build_full_hierarchy(session)
        bundle = client.get(f"/api/fhir/export/structure/{ej.id}").json()
        locations = _entries_by_type(bundle, "Location")

        uh_loc = _find_by_identifier(locations, "UH-1")
        assert uh_loc is not None
        assert uh_loc["meta"]["profile"] == ["https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-location"]
        # UH est désormais partOf une Organization (UF), pas une autre Location
        assert uh_loc["partOf"]["reference"] == "Organization/UF-1"

        chambre_loc = _find_by_identifier(locations, "CH-101")
        assert chambre_loc is not None
        assert chambre_loc["type"][0]["coding"][0]["code"] == "CHAMB"
        assert chambre_loc["partOf"]["reference"] == "Location/UH-1"
        type_chambre_ext = [e for e in chambre_loc["extension"] if e["url"].endswith("fr-core-location-type-chambre")]
        assert type_chambre_ext and type_chambre_ext[0]["valueCoding"]["code"] == "SEUL"

        lit_loc = _find_by_identifier(locations, "LIT-101-1")
        assert lit_loc is not None
        assert lit_loc["type"][0]["coding"][0]["code"] == "LIT"
        assert lit_loc["partOf"]["reference"] == "Location/CH-101"


class TestFRCore220PatientExtensions:
    def _create_dossier(self, session, patient_kwargs):
        patient = Patient(
            patient_seq=1, identifier="IPP-FRCORE-1", family="Dupont", given="Jean",
            **patient_kwargs,
        )
        session.add(patient)
        session.flush()
        dossier = Dossier(
            dossier_seq=1, patient_id=patient.id, admit_time=datetime.now(timezone.utc),
        )
        session.add(dossier)
        session.commit()
        session.refresh(dossier)
        return dossier

    def test_identity_reliability_extension_uses_correct_url_and_is_actually_included(self, client, session):
        """Avant cette correction, l'extension de fiabilité d'identité était construite
        puis jamais ajoutée à la liste `extensions` (bug de longue date) : elle
        n'apparaissait donc jamais dans le Patient exporté."""
        dossier = self._create_dossier(session, {
            "identity_reliability_code": "VALI",
            "identity_reliability_date": "2026-01-15",
        })
        response = client.post(f"/generate/fhir/{dossier.id}")
        assert response.status_code == 200
        bundle = response.json()
        patients = _entries_by_type(bundle, "Patient")
        assert patients, "Aucun Patient dans le bundle"
        extensions = patients[0].get("extension", [])
        identity_ext = [e for e in extensions if e["url"] == "https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-identity-reliability"]
        assert identity_ext, f"Extension identity-reliability absente : {extensions}"
        sub_extensions = identity_ext[0]["extension"]
        status_ext = next(e for e in sub_extensions if e["url"] == "identityStatus")
        assert status_ext["valueCoding"]["code"] == "VALI"

    def test_birth_place_uses_standard_hl7_extension_not_custom_frcore_url(self, client, session):
        """FRCore n'a pas d'extension custom pour le lieu de naissance : c'est
        l'extension standard HL7 patient-birthPlace (Address), avec une extension
        FRCore imbriquée uniquement pour le code INSEE."""
        dossier = self._create_dossier(session, {
            "birth_city": "Lyon", "birth_country": "FR", "birth_insee_code": "69123",
        })
        response = client.post(f"/generate/fhir/{dossier.id}")
        bundle = response.json()
        patients = _entries_by_type(bundle, "Patient")
        extensions = patients[0].get("extension", [])
        birth_ext = [e for e in extensions if e["url"] == "http://hl7.org/fhir/StructureDefinition/patient-birthPlace"]
        assert birth_ext, f"Extension birthPlace absente ou mauvaise URL : {extensions}"
        assert birth_ext[0]["valueAddress"]["city"] == "Lyon"
        insee_ext = birth_ext[0]["valueAddress"]["extension"]
        assert insee_ext[0]["url"] == "https://hl7.fr/ig/fhir/core/StructureDefinition/fr-core-address-insee-code"
        assert insee_ext[0]["valueCoding"]["code"] == "69123"
