"""Générateur de scénarios de test pour les interfaces.

Ce service permet de générer des scénarios de test avec injection
d'erreurs contrôlées pour valider les interfaces d'interopérabilité.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import random
import uuid
from dataclasses import dataclass


class ErrorType(Enum):
    """Types d'erreurs injectables."""
    MISSING_SEGMENT = "missing_segment"
    INVALID_FIELD = "invalid_field"
    WRONG_FORMAT = "wrong_format"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_REFERENCE = "invalid_reference"
    TIMEOUT_SIMULATION = "timeout_simulation"
    DUPLICATE_MESSAGE = "duplicate_message"


class TestScenarioType(Enum):
    """Types de scénarios de test."""
    ADMISSION_COMPLETE = "admission_complete"
    TRANSFER_PATIENT = "transfer_patient"
    DISCHARGE_PATIENT = "discharge_patient"
    UPDATE_PATIENT = "update_patient"
    BULK_ADMISSION = "bulk_admission"
    ERROR_RECOVERY = "error_recovery"
    LOAD_TEST = "load_test"


@dataclass
class TestScenario:
    """Scénario de test généré."""
    id: str
    name: str
    description: str
    scenario_type: TestScenarioType
    protocol: str  # "HL7" ou "FHIR"
    messages: List[Dict[str, Any]]
    expected_errors: List[str]
    success_criteria: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class ErrorInjection:
    """Configuration d'injection d'erreur."""
    error_type: ErrorType
    probability: float  # 0.0 à 1.0
    target_field: Optional[str] = None
    custom_value: Optional[Any] = None


class TestScenarioGenerator:
    """Générateur de scénarios de test avec injection d'erreurs."""

    def __init__(self):
        self.specialties = [
            "Médecine interne", "Chirurgie", "Pédiatrie", "Gynécologie",
            "Ophtalmologie", "Dermatologie", "Psychiatrie", "Urgences"
        ]

        self.room_types = ["Chambre", "Box", "Salle", "Lit"]
        self.patient_classes = ["I", "O", "E", "P"]  # Inpatient, Outpatient, Emergency, Preadmit

    def generate_scenario(self, scenario_type: TestScenarioType,
                         specialty: Optional[str] = None,
                         error_injections: Optional[List[ErrorInjection]] = None,
                         patient_count: int = 1) -> TestScenario:
        """
        Génère un scénario de test complet.

        Args:
            scenario_type: Type de scénario à générer
            specialty: Spécialité médicale (optionnel)
            error_injections: Liste des erreurs à injecter
            patient_count: Nombre de patients pour les scénarios bulk

        Returns:
            Scénario de test généré
        """
        scenario_id = str(uuid.uuid4())
        specialty = specialty or random.choice(self.specialties)

        if scenario_type == TestScenarioType.ADMISSION_COMPLETE:
            return self._generate_admission_scenario(scenario_id, specialty, error_injections)
        elif scenario_type == TestScenarioType.TRANSFER_PATIENT:
            return self._generate_transfer_scenario(scenario_id, specialty, error_injections)
        elif scenario_type == TestScenarioType.DISCHARGE_PATIENT:
            return self._generate_discharge_scenario(scenario_id, specialty, error_injections)
        elif scenario_type == TestScenarioType.BULK_ADMISSION:
            return self._generate_bulk_admission_scenario(scenario_id, specialty, patient_count, error_injections)
        elif scenario_type == TestScenarioType.ERROR_RECOVERY:
            return self._generate_error_recovery_scenario(scenario_id, specialty)
        elif scenario_type == TestScenarioType.LOAD_TEST:
            return self._generate_load_test_scenario(scenario_id, specialty, patient_count)
        else:
            return self._generate_admission_scenario(scenario_id, specialty, error_injections)

    def _generate_admission_scenario(self, scenario_id: str, specialty: str,
                                   error_injections: Optional[List[ErrorInjection]] = None) -> TestScenario:
        """Génère un scénario d'admission complète."""
        patient_id = self._generate_patient_id()
        visit_id = self._generate_visit_id()

        # Message ADT A01 (Admission)
        message = self._create_adt_message("A01", patient_id, visit_id, specialty)

        # Appliquer les injections d'erreurs
        if error_injections:
            message = self._apply_error_injections(message, error_injections)

        return TestScenario(
            id=scenario_id,
            name=f"Admission {specialty} - {patient_id}",
            description=f"Scénario d'admission complète en {specialty}",
            scenario_type=TestScenarioType.ADMISSION_COMPLETE,
            protocol="HL7",
            messages=[message],
            expected_errors=self._get_expected_errors(error_injections or []),
            success_criteria={
                "message_accepted": True,
                "patient_created": True,
                "visit_created": True,
                "max_response_time": 5000  # 5 secondes
            },
            metadata={
                "specialty": specialty,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "message_type": "ADT^A01"
            }
        )

    def _generate_transfer_scenario(self, scenario_id: str, specialty: str,
                                  error_injections: Optional[List[ErrorInjection]] = None) -> TestScenario:
        """Génère un scénario de transfert de patient."""
        patient_id = self._generate_patient_id()
        visit_id = self._generate_visit_id()

        # Message ADT A02 (Transfert)
        message = self._create_adt_message("A02", patient_id, visit_id, specialty)

        # Modifier pour transfert (changement de chambre/service)
        message["PV1"]["3.1"] = "CHAMBRE-002"  # Nouvelle chambre
        message["PV1"]["3.4"] = "SERVICE-002"  # Nouveau service

        if error_injections:
            message = self._apply_error_injections(message, error_injections)

        return TestScenario(
            id=scenario_id,
            name=f"Transfert {specialty} - {patient_id}",
            description=f"Scénario de transfert de patient en {specialty}",
            scenario_type=TestScenarioType.TRANSFER_PATIENT,
            protocol="HL7",
            messages=[message],
            expected_errors=self._get_expected_errors(error_injections or []),
            success_criteria={
                "message_accepted": True,
                "transfer_completed": True,
                "location_updated": True,
                "max_response_time": 3000
            },
            metadata={
                "specialty": specialty,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "message_type": "ADT^A02",
                "from_location": "CHAMBRE-001",
                "to_location": "CHAMBRE-002"
            }
        )

    def _generate_discharge_scenario(self, scenario_id: str, specialty: str,
                                   error_injections: Optional[List[ErrorInjection]] = None) -> TestScenario:
        """Génère un scénario de sortie de patient."""
        patient_id = self._generate_patient_id()
        visit_id = self._generate_visit_id()

        # Message ADT A03 (Sortie)
        message = self._create_adt_message("A03", patient_id, visit_id, specialty)

        if error_injections:
            message = self._apply_error_injections(message, error_injections)

        return TestScenario(
            id=scenario_id,
            name=f"Sortie {specialty} - {patient_id}",
            description=f"Scénario de sortie de patient en {specialty}",
            scenario_type=TestScenarioType.DISCHARGE_PATIENT,
            protocol="HL7",
            messages=[message],
            expected_errors=self._get_expected_errors(error_injections or []),
            success_criteria={
                "message_accepted": True,
                "visit_closed": True,
                "discharge_completed": True,
                "max_response_time": 3000
            },
            metadata={
                "specialty": specialty,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "message_type": "ADT^A03"
            }
        )

    def _generate_bulk_admission_scenario(self, scenario_id: str, specialty: str,
                                        patient_count: int,
                                        error_injections: Optional[List[ErrorInjection]] = None) -> TestScenario:
        """Génère un scénario d'admission en masse."""
        messages = []

        for i in range(patient_count):
            patient_id = f"BULK-{i+1:03d}"
            visit_id = f"VISIT-{i+1:03d}"

            message = self._create_adt_message("A01", patient_id, visit_id, specialty)

            # Varier légèrement les données pour chaque patient
            message["PID"]["5.1"] = f"Patient{i+1}"
            message["PID"]["5.2"] = f"Test{i+1}"
            message["PV1"]["3.1"] = f"CHAMBRE-{i+1:03d}"

            messages.append(message)

        # Appliquer les erreurs seulement sur quelques messages
        if error_injections:
            for i, message in enumerate(messages):
                if random.random() < 0.3:  # 30% des messages ont des erreurs
                    messages[i] = self._apply_error_injections(message, error_injections)

        return TestScenario(
            id=scenario_id,
            name=f"Admission en masse {specialty} - {patient_count} patients",
            description=f"Scénario d'admission simultanée de {patient_count} patients en {specialty}",
            scenario_type=TestScenarioType.BULK_ADMISSION,
            protocol="HL7",
            messages=messages,
            expected_errors=self._get_expected_errors(error_injections or []),
            success_criteria={
                "messages_accepted": patient_count,
                "patients_created": patient_count,
                "visits_created": patient_count,
                "max_response_time": 10000,  # 10 secondes pour le bulk
                "success_rate": 0.95  # 95% de succès minimum
            },
            metadata={
                "specialty": specialty,
                "patient_count": patient_count,
                "message_type": "ADT^A01",
                "bulk_operation": True
            }
        )

    def _generate_error_recovery_scenario(self, scenario_id: str, specialty: str) -> TestScenario:
        """Génère un scénario de récupération d'erreur."""
        patient_id = self._generate_patient_id()
        visit_id = self._generate_visit_id()

        # Message avec erreur (segment MSH manquant)
        message_with_error = self._create_adt_message("A01", patient_id, visit_id, specialty)
        del message_with_error["MSH"]  # Supprimer le segment MSH

        # Message de correction
        correction_message = self._create_adt_message("A01", patient_id, visit_id, specialty)

        return TestScenario(
            id=scenario_id,
            name=f"Récupération d'erreur {specialty} - {patient_id}",
            description=f"Scénario de test de récupération après erreur de message en {specialty}",
            scenario_type=TestScenarioType.ERROR_RECOVERY,
            protocol="HL7",
            messages=[message_with_error, correction_message],
            expected_errors=["Segment MSH manquant"],
            success_criteria={
                "first_message_rejected": True,
                "second_message_accepted": True,
                "patient_created": True,
                "error_handled_gracefully": True
            },
            metadata={
                "specialty": specialty,
                "patient_id": patient_id,
                "visit_id": visit_id,
                "error_recovery_test": True
            }
        )

    def _generate_load_test_scenario(self, scenario_id: str, specialty: str,
                                   request_count: int) -> TestScenario:
        """Génère un scénario de test de charge."""
        messages = []

        for i in range(request_count):
            patient_id = f"LOAD-{i+1:04d}"
            visit_id = f"VISIT-{i+1:04d}"

            message = self._create_adt_message("A01", patient_id, visit_id, specialty)
            message["PID"]["5.1"] = f"LoadPatient{i+1}"
            message["PID"]["5.2"] = f"Test{i+1}"

            messages.append(message)

        return TestScenario(
            id=scenario_id,
            name=f"Test de charge {specialty} - {request_count} requêtes",
            description=f"Scénario de test de charge avec {request_count} requêtes simultanées en {specialty}",
            scenario_type=TestScenarioType.LOAD_TEST,
            protocol="HL7",
            messages=messages,
            expected_errors=[],
            success_criteria={
                "messages_processed": request_count,
                "avg_response_time": 2000,  # 2 secondes max en moyenne
                "success_rate": 0.99,  # 99% de succès
                "no_timeouts": True
            },
            metadata={
                "specialty": specialty,
                "request_count": request_count,
                "load_test": True,
                "concurrent_execution": True
            }
        )

    def _create_adt_message(self, trigger_event: str, patient_id: str,
                           visit_id: str, specialty: str) -> Dict[str, Any]:
        """Crée un message ADT de base."""
        now = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        return {
            "MSH": {
                "1": "|",
                "2": "^~\\&",
                "3": "SIMULATOR",
                "4": "HOSP",
                "5": "TARGET",
                "6": "HOSP",
                "7": now,
                "8": "",
                "9.1": "ADT",
                "9.2": trigger_event,
                "10": str(uuid.uuid4())[:20],
                "11": "P",
                "12": "2.5",
                "15": "",
                "16": "",
                "17": "",
                "18": "",
                "19": "",
                "20": "",
                "21": ""
            },
            "PID": {
                "1": "1",
                "2": "",
                "3.1": patient_id,
                "3.4": "HOSP",
                "3.5": "PI",
                "5.1": "DUPONT",
                "5.2": "JEAN",
                "7": "19800101",
                "8": "M",
                "11.1": "123 RUE DE TEST",
                "11.3": "PARIS",
                "11.5": "75001"
            },
            "PV1": {
                "1": "1",
                "2": random.choice(self.patient_classes),
                "3.1": f"CHAMBRE-{random.randint(100, 999)}",
                "3.4": f"SERVICE-{specialty[:3].upper()}",
                "7.1": "DR SMITH",
                "7.2": "JOHN",
                "19.1": visit_id,
                "44": now
            }
        }

    def _apply_error_injections(self, message: Dict[str, Any],
                               error_injections: List[ErrorInjection]) -> Dict[str, Any]:
        """Applique les injections d'erreurs au message."""
        modified_message = message.copy()

        for injection in error_injections:
            if random.random() < injection.probability:
                if injection.error_type == ErrorType.MISSING_SEGMENT:
                    # Supprimer un segment aléatoire
                    segments = list(modified_message.keys())
                    if segments:
                        segment_to_remove = random.choice(segments)
                        del modified_message[segment_to_remove]

                elif injection.error_type == ErrorType.INVALID_FIELD:
                    # Rendre un champ invalide
                    if "PID" in modified_message:
                        modified_message["PID"]["7"] = "INVALID_DATE"

                elif injection.error_type == ErrorType.MISSING_REQUIRED_FIELD:
                    # Supprimer un champ requis
                    if "MSH" in modified_message:
                        modified_message["MSH"]["7"] = ""

                elif injection.error_type == ErrorType.WRONG_FORMAT:
                    # Changer le format d'un champ
                    if "MSH" in modified_message:
                        modified_message["MSH"]["9.1"] = "INVALID"

        return modified_message

    def _get_expected_errors(self, error_injections: List[ErrorInjection]) -> List[str]:
        """Détermine les erreurs attendues basées sur les injections."""
        expected_errors = []

        for injection in error_injections:
            if injection.error_type == ErrorType.MISSING_SEGMENT:
                expected_errors.append("Segment manquant")
            elif injection.error_type == ErrorType.INVALID_FIELD:
                expected_errors.append("Champ invalide")
            elif injection.error_type == ErrorType.MISSING_REQUIRED_FIELD:
                expected_errors.append("Champ requis manquant")
            elif injection.error_type == ErrorType.WRONG_FORMAT:
                expected_errors.append("Format incorrect")

        return expected_errors

    def _generate_patient_id(self) -> str:
        """Génère un identifiant patient unique."""
        return f"PAT-{uuid.uuid4().hex[:8].upper()}"

    def _generate_visit_id(self) -> str:
        """Génère un identifiant de visite unique."""
        return f"VISIT-{uuid.uuid4().hex[:8].upper()}"


# Fonctions utilitaires pour créer des injections d'erreurs courantes
def create_missing_segment_injection(probability: float = 0.5) -> ErrorInjection:
    """Crée une injection d'erreur pour segment manquant."""
    return ErrorInjection(
        error_type=ErrorType.MISSING_SEGMENT,
        probability=probability
    )

def create_invalid_field_injection(field: str, probability: float = 0.5) -> ErrorInjection:
    """Crée une injection d'erreur pour champ invalide."""
    return ErrorInjection(
        error_type=ErrorType.INVALID_FIELD,
        probability=probability,
        target_field=field
    )

def create_missing_required_field_injection(field: str, probability: float = 0.5) -> ErrorInjection:
    """Crée une injection d'erreur pour champ requis manquant."""
    return ErrorInjection(
        error_type=ErrorType.MISSING_REQUIRED_FIELD,
        probability=probability,
        target_field=field
    )