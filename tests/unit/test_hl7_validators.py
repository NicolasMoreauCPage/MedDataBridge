"""Régressions du validateur HL7 historique."""

from app.validators.hl7_validators import PAMValidator


def test_pam_validator_accepts_french_zbe_action_in_field_four():
    """ZBE-3 est vide dans le profil IHE PAM France, l'action est en ZBE-4."""
    message = "\r".join(
        [
            "MSH|^~\\&|SRC|FAC|DST|FAC|20260914190000||ADT^A01^ADT_A01|1|P|2.5",
            "PID|1||P1^^^HOSP^PI||DOE^Jane",
            "PV1|1|I|WARD",
            "ZBE|MVT1^^^HOSP^MVT|20260914190000||INSERT|N|||^^^^^^^^^UF1|H",
        ]
    )

    validator = PAMValidator(message)
    validator.validate()
    assert "Code mouvement ZBE manquant" not in validator.errors
