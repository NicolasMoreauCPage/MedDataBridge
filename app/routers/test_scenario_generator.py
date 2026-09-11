"""API de génération de scénarios HL7 de qualification."""
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from app.services.test_scenario_generator import (
    ErrorInjection,
    ErrorType,
    TestScenarioGenerator,
    TestScenarioType,
    message_to_hl7,
)

router = APIRouter(prefix="/test-scenario-generator", tags=["Test Scenario Generator"])


class ErrorInjectionPayload(BaseModel):
    error_type: ErrorType
    probability: float = Field(default=1.0, ge=0.0, le=1.0)
    target_field: Optional[str] = None
    custom_value: Optional[str] = None


class ScenarioGenerationRequest(BaseModel):
    scenario_type: TestScenarioType = TestScenarioType.ADMISSION_COMPLETE
    specialty: Optional[str] = None
    patient_count: int = Field(default=1, ge=1, le=500)
    error_injections: list[ErrorInjectionPayload] = Field(default_factory=list)


@router.get("/catalog")
async def scenario_catalog() -> dict:
    """Expose les options valides afin qu'un outil de qualification les découvre."""
    return {
        "scenario_types": [item.value for item in TestScenarioType],
        "error_types": [item.value for item in ErrorType],
        "max_patient_count": 500,
    }


@router.post("/generate")
async def generate_scenario(payload: ScenarioGenerationRequest) -> dict:
    """Génère un scénario HL7 en mémoire, sans l'envoyer à une interface."""
    try:
        injections = [
            ErrorInjection(
                error_type=item.error_type,
                probability=item.probability,
                target_field=item.target_field,
                custom_value=item.custom_value,
            )
            for item in payload.error_injections
        ]
        scenario = TestScenarioGenerator().generate_scenario(
            scenario_type=payload.scenario_type,
            specialty=payload.specialty,
            patient_count=payload.patient_count,
            error_injections=injections or None,
        )
        response = asdict(scenario)
        response["messages_hl7"] = [message_to_hl7(message) for message in scenario.messages]
        return jsonable_encoder(response)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
