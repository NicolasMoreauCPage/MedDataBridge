from datetime import date

import pytest

from app.services.hprim_coding import (
    HprimCodingService,
    HprimMessage,
    HprimMessageType,
    HprimPatient,
)


def test_hprim_patient_state_is_explicitly_not_supported():
    message = HprimMessage(
        id="state-not-supported",
        type_message=HprimMessageType.ETAT_PATIENT,
        etablissement="TEST",
        patient=HprimPatient(numero_sejour="SEJ-1", date_naissance=date(2000, 1, 1)),
    )

    with pytest.raises(NotImplementedError, match="n'est pas pris en charge"):
        HprimCodingService().generate_xml(message)
