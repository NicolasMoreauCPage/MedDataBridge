"""Statistiques de validation exposées par le service HPRIM."""

from app.services.hprim.hprim_service import HprimService
from app.services.hprim.hprim_validator import HprimValidationError


def test_hprim_validation_statistics_track_successes_errors_and_codes() -> None:
    service = HprimService()
    outcomes = [
        [],
        [
            HprimValidationError("CCAM_INVALID", "Code CCAM invalide"),
            HprimValidationError("DATE_INVALID", "Date invalide"),
        ],
    ]
    service.validator.validate_message_complet = lambda _message: outcomes.pop(0)

    assert service.valider_message(object()) == []
    assert len(service.valider_message(object())) == 2

    statistics = service.get_statistiques_validation()
    assert statistics["validations_total"] == 2
    assert statistics["erreurs_total"] == 2
    assert statistics["types_erreur"] == {"CCAM_INVALID": 1, "DATE_INVALID": 1}
    assert statistics["performance_moyenne"] >= 0.0
