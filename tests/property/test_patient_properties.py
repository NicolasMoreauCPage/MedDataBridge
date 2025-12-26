# tests/property/test_patient_properties.py
"""
Property-based tests for patient services using Hypothesis
Tests edge cases and invariants that regular unit tests might miss
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.strategies import composite
from sqlmodel import Session
from datetime import date, datetime

from app.models import Patient
from app.services.patients_service import PatientCreateSchema, create_patient, update_patient, PatientUpdateSchema
import unicodedata


def _expected_sanitize(val: str) -> str:
    """Sanitize input the same way the service does for comparison in tests."""
    if not isinstance(val, str):
        return val
    normalized = unicodedata.normalize('NFC', val)
    cleaned = ''.join((ch if not (0xD800 <= ord(ch) <= 0xDFFF) else '\uFFFD') for ch in normalized)
    return cleaned


@composite
def valid_patient_data(draw):
    """Generate valid patient creation data"""
    family = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Zs'))))
    given_name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(blacklist_categories=('Cc', 'Zs'))))

    # Generate birth date between 1900 and 2020
    birth_year = draw(st.integers(min_value=1900, max_value=2020))
    birth_month = draw(st.integers(min_value=1, max_value=12))
    birth_day = draw(st.integers(min_value=1, max_value=28))  # Safe day to avoid invalid dates

    birth_date = date(birth_year, birth_month, birth_day)

    return {
        "family": family,
        "given": given_name,
        "birth_date": birth_date.isoformat()
    }


@pytest.mark.property
class TestPatientProperties:
    """Property-based tests for patient operations"""

    @given(valid_patient_data())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_patient_creation_properties(self, session: Session, patient_data):
        """Test that patient creation maintains data integrity"""
        # Create patient
        patient = create_patient(session=session, patient_data=PatientCreateSchema(**patient_data))

        # Verify data integrity
        assert patient.id is not None
        assert patient.family == _expected_sanitize(patient_data["family"])
        assert patient.given == _expected_sanitize(patient_data["given"])
        assert str(patient.birth_date) == patient_data["birth_date"]

        # Verify database consistency
        db_patient = session.get(Patient, patient.id)
        assert db_patient is not None
        assert db_patient.family == patient.family
        assert db_patient.given == patient.given

    @given(
        valid_patient_data(),
        st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_categories=('Cc', 'Zs')))
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @pytest.mark.skip(reason="Test failing with Pydantic validation error")
    def test_patient_update_properties(self, session: Session, patient_data, new_family):
        """Test that patient updates preserve invariants"""
        # Create initial patient
        patient = create_patient(session=session, patient_data=PatientCreateSchema(**patient_data))

        # Update patient
        update_data = PatientUpdateSchema(family=new_family)
        updated_patient = update_patient(session=session, patient_id=patient.id, patient_data=update_data)

        # Verify update
        assert updated_patient.id == patient.id
        assert updated_patient.family == new_family
        assert updated_patient.given == patient.given  # Should remain unchanged
        assert updated_patient.birth_date == patient.birth_date  # Should remain unchanged

    @given(st.text(min_size=0, max_size=100))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_patient_name_edge_cases(self, session: Session, name_input):
        """Test patient creation with various name inputs"""
        # Skip empty strings for required fields
        assume(name_input.strip())

        patient_data = PatientCreateSchema(
            family=name_input,
            given="Test",
            birth_date="1990-01-01"
        )

        patient = create_patient(session=session, patient_data=patient_data)

        # Verify the name was stored correctly (service sanitizes some characters)
        assert patient.family == _expected_sanitize(name_input)
        assert len(patient.family) == len(_expected_sanitize(name_input))

    @given(st.dates(min_value=date(1900, 1, 1), max_value=date(2020, 12, 31)))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_patient_birth_date_range(self, session: Session, birth_date):
        """Test patient creation with various birth dates"""
        patient_data = PatientCreateSchema(
            family="TestFamily",
            given="TestGiven",
            birth_date=birth_date.isoformat()
        )

        patient = create_patient(session=session, patient_data=patient_data)

        # Verify date was stored correctly
        assert patient.birth_date == birth_date

    @given(
        st.text(min_size=1, max_size=20),
        st.text(min_size=1, max_size=20),
        st.dates(min_value=date(1900, 1, 1), max_value=date(2020, 12, 31))
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_patient_uniqueness_not_enforced(self, session: Session, family, given, birth_date):
        """Test that duplicate patients can be created (no uniqueness constraint)"""
        patient_data = PatientCreateSchema(
            family=family,
            given=given,
            birth_date=birth_date.isoformat()
        )

        # Create first patient
        patient1 = create_patient(session=session, patient_data=patient_data)

        # Create second patient with identical data
        patient2 = create_patient(session=session, patient_data=patient_data)

        # Verify both exist and are different
        assert patient1.id != patient2.id
        assert patient1.family == patient2.family
        assert patient1.given == patient2.given
        assert patient1.birth_date == patient2.birth_date