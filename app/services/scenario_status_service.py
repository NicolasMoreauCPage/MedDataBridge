"""Service pour récupérer le statut des scénarios (dernier run avec ACK).

Permet de déterminer rapidement si un scénario a reçu un ACK positif (AA)
lors de son dernier envoi sur une EJ donnée.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlmodel import Session, select, func, and_

from app.models_scenarios import InteropScenario
from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_endpoints import SystemEndpoint
from app.models_structure import EntiteJuridique


class ScenarioStatus:
    """Représente le statut du dernier exécution d'un scénario."""
    
    def __init__(
        self,
        scenario_id: int,
        scenario_name: str,
        ej_id: Optional[int] = None,
        ej_name: Optional[str] = None,
        last_run_at: Optional[datetime] = None,
        ack_code: Optional[str] = None,
        status: str = "unknown",  # unknown|success|partial|error|all_aa|some_aa|no_aa
        success_steps: int = 0,
        total_steps: int = 0,
        error_message: Optional[str] = None,
    ):
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.ej_id = ej_id
        self.ej_name = ej_name
        self.last_run_at = last_run_at
        self.ack_code = ack_code
        self.status = status
        self.success_steps = success_steps
        self.total_steps = total_steps
        self.error_message = error_message

    @property
    def is_success(self) -> bool:
        """Retourne True si tous les messages ont reçu un ACK AA."""
        return self.status == "all_aa"

    @property
    def is_partial(self) -> bool:
        """Retourne True si certains messages ont reçu un ACK AA."""
        return self.status == "some_aa"

    @property
    def has_errors(self) -> bool:
        """Retourne True si le dernier run a des erreurs."""
        return self.status in ("error", "partial")

    @property
    def visual_indicator(self) -> str:
        """Retourne un indicateur visuel du statut."""
        if self.status == "all_aa":
            return "✅"  # Tous les AA
        elif self.status == "some_aa":
            return "⚠️"   # Partiel
        elif self.status == "error":
            return "❌"  # Erreur
        else:
            return "⏹️"   # Inconnu/Jamais exécuté
    
    @property
    def css_class(self) -> str:
        """Retourne la classe CSS pour le styling."""
        if self.status == "all_aa":
            return "bg-green-50 border-l-4 border-green-500"
        elif self.status == "some_aa":
            return "bg-yellow-50 border-l-4 border-yellow-500"
        elif self.status == "error":
            return "bg-red-50 border-l-4 border-red-500"
        else:
            return "bg-slate-50 border-l-4 border-slate-300"


def get_last_scenario_status(
    session: Session,
    scenario_id: int,
    ej_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
) -> ScenarioStatus:
    """Récupère le statut du dernier run d'un scénario.
    
    Si ej_id est fourni, retourne le statut du dernier run sur cette EJ.
    Si endpoint_id est fourni, retourne le statut du dernier run sur cet endpoint.
    """
    
    # Construire la query
    query = select(ScenarioExecutionRun).where(
        ScenarioExecutionRun.scenario_id == scenario_id
    )
    
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    # Récupérer le dernier run
    last_run = session.exec(
        query.order_by(ScenarioExecutionRun.finished_at.desc()).limit(1)
    ).first()
    
    # Récupérer le nom du scénario
    scenario = session.get(InteropScenario, scenario_id)
    scenario_name = scenario.name if scenario else f"Scenario {scenario_id}"
    
    # Si pas de run trouvé
    if not last_run:
        return ScenarioStatus(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            ej_id=ej_id,
            status="unknown",
        )
    
    # Récupérer les logs des étapes
    step_logs = session.exec(
        select(ScenarioExecutionStepLog).where(
            ScenarioExecutionStepLog.run_id == last_run.id
        )
    ).all()
    
    # Analyser les ACK codes
    ack_codes = [log.ack_code for log in step_logs if log.ack_code]
    aa_count = len([code for code in ack_codes if code == "AA"])
    error_count = len([code for code in ack_codes if code in ("AE", "AR")])
    
    # Déterminer le statut
    if last_run.status in ("error",):
        status = "error"
        ack_code = "ERROR"
    elif last_run.status == "dry_run":
        status = "unknown"
        ack_code = "DRY_RUN"
    elif aa_count == len(ack_codes) and len(ack_codes) > 0:
        status = "all_aa"
        ack_code = "AA"
    elif aa_count > 0:
        status = "some_aa"
        ack_code = f"AA({aa_count}/{len(ack_codes)})"
    elif error_count > 0:
        status = "error"
        ack_code = f"AE/AR({error_count}/{len(ack_codes)})"
    else:
        status = "unknown"
        ack_code = None
    
    # Récupérer l'EJ si c'est pas fourni
    ej_name = None
    if ej_id:
        ej = session.get(EntiteJuridique, ej_id)
        ej_name = ej.name if ej else f"EJ {ej_id}"
    elif endpoint_id:
        endpoint = session.get(SystemEndpoint, endpoint_id)
        if endpoint and endpoint.entite_juridique_id:
            ej = session.get(EntiteJuridique, endpoint.entite_juridique_id)
            ej_name = ej.name if ej else f"EJ {endpoint.entite_juridique_id}"
            ej_id = endpoint.entite_juridique_id
    
    return ScenarioStatus(
        scenario_id=scenario_id,
        scenario_name=scenario_name,
        ej_id=ej_id,
        ej_name=ej_name,
        last_run_at=last_run.finished_at or last_run.started_at,
        ack_code=ack_code,
        status=status,
        success_steps=last_run.success_steps,
        total_steps=last_run.total_steps,
    )


def get_scenarios_status_for_ej(
    session: Session,
    ej_id: int,
    only_failed: bool = False,
) -> List[ScenarioStatus]:
    """Récupère le statut de tous les scénarios pour une EJ donnée.
    
    Si only_failed=True, retourne seulement les scénarios en erreur/sans ACK AA.
    """
    
    # Récupérer tous les endpoints de cette EJ
    endpoints = session.exec(
        select(SystemEndpoint).where(SystemEndpoint.entite_juridique_id == ej_id)
    ).all()
    
    if not endpoints:
        return []
    
    endpoint_ids = [ep.id for ep in endpoints]
    
    # Récupérer les derniers runs par scénario/endpoint
    subquery = (
        select(
            ScenarioExecutionRun.scenario_id,
            ScenarioExecutionRun.endpoint_id,
            func.max(ScenarioExecutionRun.finished_at).label("max_finished_at")
        )
        .where(ScenarioExecutionRun.endpoint_id.in_(endpoint_ids))
        .group_by(ScenarioExecutionRun.scenario_id, ScenarioExecutionRun.endpoint_id)
    ).subquery()
    
    last_runs = session.exec(
        select(ScenarioExecutionRun).join(
            subquery,
            and_(
                ScenarioExecutionRun.scenario_id == subquery.c.scenario_id,
                ScenarioExecutionRun.endpoint_id == subquery.c.endpoint_id,
                ScenarioExecutionRun.finished_at == subquery.c.max_finished_at,
            )
        )
    ).all()
    
    statuses = []
    for run in last_runs:
        status = get_last_scenario_status(
            session,
            run.scenario_id,
            ej_id=ej_id,
            endpoint_id=run.endpoint_id,
        )
        
        if only_failed and status.is_success:
            continue  # Passer les succès
        
        statuses.append(status)
    
    return sorted(statuses, key=lambda s: (not s.is_success, s.scenario_name))


def get_scenarios_with_status(
    session: Session,
    filter_by_status: Optional[str] = None,  # None|all_aa|some_aa|error|no_run
) -> List[tuple[InteropScenario, Optional[ScenarioStatus]]]:
    """Récupère tous les scénarios avec leur statut de dernier run."""
    
    scenarios = session.exec(
        select(InteropScenario).order_by(InteropScenario.name)
    ).all()
    
    results = []
    for scenario in scenarios:
        # Récupérer le dernier run global
        last_run = session.exec(
            select(ScenarioExecutionRun)
            .where(ScenarioExecutionRun.scenario_id == scenario.id)
            .order_by(ScenarioExecutionRun.finished_at.desc())
            .limit(1)
        ).first()
        
        if not last_run:
            status = ScenarioStatus(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                status="no_run",
            )
        else:
            status = get_last_scenario_status(session, scenario.id)
        
        # Appliquer le filtre
        if filter_by_status:
            if filter_by_status == "no_run" and status.status != "no_run":
                continue
            elif filter_by_status != "no_run" and status.status != filter_by_status:
                continue
        
        results.append((scenario, status))
    
    return results
