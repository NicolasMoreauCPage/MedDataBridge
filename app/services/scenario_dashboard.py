"""Service d'agrégation statistiques pour dashboard scénarios."""
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select, func, and_, or_

from app.models_scenario_runs import ScenarioExecutionRun, ScenarioExecutionStepLog
from app.models_scenarios import InteropScenario


def get_scenario_stats(
    session: Session,
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30
) -> dict:
    """Agrège statistiques globales d'exécution de scénarios.
    
    Args:
        session: Session DB
        scenario_id: Filtrer par scénario spécifique (optionnel)
        endpoint_id: Filtrer par endpoint (optionnel)
        days_back: Fenêtre temporelle en jours (défaut 30)
        
    Returns:
        Dict avec clés:
        - total_runs: Nombre total d'exécutions
        - success_rate: Taux de succès (0-100)
        - avg_duration: Durée moyenne en secondes
        - total_steps: Nombre total de steps exécutés
        - error_count: Nombre d'erreurs
        - recent_runs: Liste des 10 derniers runs (id, scenario_name, status, started_at)
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    
    # Base query
    query = select(ScenarioExecutionRun).where(
        ScenarioExecutionRun.started_at >= cutoff
    )
    
    if scenario_id:
        query = query.where(ScenarioExecutionRun.scenario_id == scenario_id)
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    runs = session.exec(query).all()
    
    total_runs = len(runs)
    if total_runs == 0:
        return {
            "total_runs": 0,
            "success_rate": 0.0,
            "avg_duration": 0.0,
            "total_steps": 0,
            "error_count": 0,
            "recent_runs": []
        }
    
    success_count = sum(1 for r in runs if r.status == "completed")
    error_count = sum(1 for r in runs if r.status in ("failed", "error"))
    
    durations = [r.duration_seconds for r in runs if r.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    
    # Compter steps
    step_query = select(func.count(ScenarioExecutionStepLog.id)).where(
        ScenarioExecutionStepLog.run_id.in_([r.id for r in runs])
    )
    total_steps = session.exec(step_query).one()
    
    # Récents (10 derniers)
    recent_query = (
        select(ScenarioExecutionRun, InteropScenario)
        .join(InteropScenario, ScenarioExecutionRun.scenario_id == InteropScenario.id)
        .where(ScenarioExecutionRun.started_at >= cutoff)
    )
    if scenario_id:
        recent_query = recent_query.where(ScenarioExecutionRun.scenario_id == scenario_id)
    if endpoint_id:
        recent_query = recent_query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    recent_query = recent_query.order_by(ScenarioExecutionRun.started_at.desc()).limit(10)
    recent_results = session.exec(recent_query).all()
    
    recent_runs = [
        {
            "id": run.id,
            "scenario_name": scenario.name,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "duration": run.duration_seconds
        }
        for run, scenario in recent_results
    ]
    
    return {
        "total_runs": total_runs,
        "success_rate": round((success_count / total_runs) * 100, 1),
        "avg_duration": round(avg_duration, 2),
        "total_steps": total_steps,
        "error_count": error_count,
        "recent_runs": recent_runs
    }


def get_ack_distribution(
    session: Session,
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30
) -> dict[str, int]:
    """Agrège distribution des codes ACK.
    
    Returns:
        Dict {ack_code: count}, ex: {"AA": 150, "AE": 5, "AR": 2, "null": 10}
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    
    # Récupérer tous les step logs dans fenêtre
    query = (
        select(ScenarioExecutionStepLog)
        .join(ScenarioExecutionRun, ScenarioExecutionStepLog.run_id == ScenarioExecutionRun.id)
        .where(ScenarioExecutionRun.started_at >= cutoff)
    )
    
    if scenario_id:
        query = query.where(ScenarioExecutionRun.scenario_id == scenario_id)
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    steps = session.exec(query).all()
    
    distribution: dict[str, int] = {}
    for step in steps:
        code = step.ack_code if step.ack_code else "null"
        distribution[code] = distribution.get(code, 0) + 1
    
    return distribution


def get_scenario_timeline(
    session: Session,
    scenario_id: Optional[int] = None,
    endpoint_id: Optional[int] = None,
    days_back: int = 30
) -> list[dict]:
    """Agrège timeline d'exécutions par jour.
    
    Returns:
        Liste de dicts [{date: "2025-11-09", success: 10, failed: 2, duration_avg: 45.3}, ...]
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    
    query = select(ScenarioExecutionRun).where(
        ScenarioExecutionRun.started_at >= cutoff
    )
    
    if scenario_id:
        query = query.where(ScenarioExecutionRun.scenario_id == scenario_id)
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    runs = session.exec(query).all()
    
    # Grouper par date
    daily_stats: dict[str, dict] = {}
    for run in runs:
        if not run.started_at:
            continue
        date_key = run.started_at.date().isoformat()
        
        if date_key not in daily_stats:
            daily_stats[date_key] = {"success": 0, "failed": 0, "durations": []}
        
        if run.status == "completed":
            daily_stats[date_key]["success"] += 1
        elif run.status in ("failed", "error"):
            daily_stats[date_key]["failed"] += 1
        
        if run.duration_seconds:
            daily_stats[date_key]["durations"].append(run.duration_seconds)
    
    # Formater résultat
    timeline = []
    for date_str, stats in sorted(daily_stats.items()):
        avg_duration = (
            sum(stats["durations"]) / len(stats["durations"])
            if stats["durations"]
            else 0.0
        )
        timeline.append({
            "date": date_str,
            "success": stats["success"],
            "failed": stats["failed"],
            "duration_avg": round(avg_duration, 2)
        })
    
    return timeline


def get_step_error_summary(
    session: Session,
    run_id: int
) -> list[dict]:
    """Résume les erreurs par step pour un run donné.
    
    Returns:
        Liste [{step_order: 1, status: "error", ack_code: "AE", duration: 1.2}, ...]
    """
    steps = session.exec(
        select(ScenarioExecutionStepLog)
        .where(ScenarioExecutionStepLog.run_id == run_id)
        .order_by(ScenarioExecutionStepLog.step_order)
    ).all()
    
    return [
        {
            "step_order": step.step_order,
            "status": step.status,
            "ack_code": step.ack_code,
            "duration": step.duration_seconds,
            "error_detail": step.error_detail
        }
        for step in steps
        if step.status in ("error", "failed", "skipped")
    ]


def get_scenario_comparison(
    session: Session,
    endpoint_id: Optional[int] = None,
    days_back: int = 30,
    limit: int = 10
) -> list[dict]:
    """Compare performances de plusieurs scénarios.
    
    Returns:
        Liste triée par taux de succès descendant:
        [{scenario_id, scenario_name, runs, success_rate, avg_duration}, ...]
    """
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    
    query = (
        select(ScenarioExecutionRun, InteropScenario)
        .join(InteropScenario, ScenarioExecutionRun.scenario_id == InteropScenario.id)
        .where(ScenarioExecutionRun.started_at >= cutoff)
    )
    
    if endpoint_id:
        query = query.where(ScenarioExecutionRun.endpoint_id == endpoint_id)
    
    results = session.exec(query).all()
    
    # Grouper par scénario
    scenario_stats: dict[int, dict] = {}
    for run, scenario in results:
        sid = scenario.id
        if sid not in scenario_stats:
            scenario_stats[sid] = {
                "scenario_id": sid,
                "scenario_name": scenario.name,
                "runs": 0,
                "success": 0,
                "durations": []
            }
        
        scenario_stats[sid]["runs"] += 1
        if run.status == "completed":
            scenario_stats[sid]["success"] += 1
        if run.duration_seconds:
            scenario_stats[sid]["durations"].append(run.duration_seconds)
    
    # Calculer métriques et trier
    comparison = []
    for stats in scenario_stats.values():
        runs = stats["runs"]
        success_rate = (stats["success"] / runs * 100) if runs > 0 else 0.0
        avg_duration = (
            sum(stats["durations"]) / len(stats["durations"])
            if stats["durations"]
            else 0.0
        )
        comparison.append({
            "scenario_id": stats["scenario_id"],
            "scenario_name": stats["scenario_name"],
            "runs": runs,
            "success_rate": round(success_rate, 1),
            "avg_duration": round(avg_duration, 2)
        })
    
    # Trier par success_rate desc puis avg_duration asc
    comparison.sort(key=lambda x: (-x["success_rate"], x["avg_duration"]))
    
    return comparison[:limit]
