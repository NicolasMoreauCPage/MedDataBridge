"""Régressions sur les exports HPRIM historiques rejoués en scénario."""

from types import SimpleNamespace

from app.routers.roundtrip_hprim import _act_projection
from app.services.hprim import HprimService
from app.services.hprim.hprim_validator import HprimValidator


def test_legacy_hprim_without_namespace_and_receiver_patient_id_is_integrable():
    """La variante 1.x non namespacée ne doit pas créer d'objet fictif."""
    xml = """<evenementsServeurActes version="1.06">
      <enteteMessage><identifiantMessage>LEGACY001</identifiantMessage>
        <dateHeureProduction>2026-09-12T10:00:00</dateHeureProduction>
        <emetteur><agents><agent categorie="application"><code>SOURCE</code></agent></agents></emetteur>
        <destinataire><agents><agent categorie="application"><code>CIBLE</code></agent></agents></destinataire>
      </enteteMessage>
      <evenementServeurActe><patient><identifiant><recepteur><valeur>IPP-LEGACY</valeur></recepteur></identifiant>
        <personnePhysique sexe="M"><nomUsuel>DUPONT</nomUsuel><prenoms><prenom>Jean</prenom></prenoms><dateNaissance><date>1980-01-01</date></dateNaissance></personnePhysique>
      </patient><acteur><personne><nomUsuel>MARTIN</nomUsuel><prenoms><prenom>Marie</prenom></prenoms></personne></acteur>
      </evenementServeurActe>
    </evenementsServeurActes>"""

    result = HprimService().traiter_message_xml(xml)

    assert result["succes"] is True
    assert result["message"].entete.message_type.value == "evenementsServeurActes"
    assert result["message"].patient.identifiant_id == "IPP-LEGACY"


def test_hprim_malformed_xml_returns_the_syntax_error_without_masking_it():
    valid, errors = HprimValidator().validate_xml_string("<evenementsServeurActes>", "evenements_serveur_actes")

    assert valid is False
    assert errors and errors[0].startswith("XML Syntax Error:")
    assert "object has no attribute" not in errors[0]


def test_hprim_legacy_ucd_commercial_code_can_be_persisted():
    act_id, code, _ = _act_projection(
        "UCD", SimpleNamespace(identifiant="UCD-1", code_commercial="3400930000000", action="creation")
    )

    assert (act_id, code) == ("UCD-1", "3400930000000")
