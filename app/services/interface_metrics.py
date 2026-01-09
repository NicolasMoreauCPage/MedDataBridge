"""Service de métriques de performance pour les interfaces.

Ce service collecte et analyse les métriques de performance
des interfaces d'interopérabilité (latence, taux de succès, etc.).
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time
import statistics
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum


class MetricType(Enum):
    """Types de métriques."""
    LATENCY = "latency"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"


@dataclass
class PerformanceMetric:
    """Métrique de performance."""
    timestamp: datetime
    metric_type: MetricType
    value: float
    labels: Dict[str, str]
    message_type: Optional[str] = None
    endpoint: Optional[str] = None


@dataclass
class InterfaceMetrics:
    """Métriques consolidées d'une interface."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p95_response_time: float
    success_rate: float
    requests_per_minute: float
    error_rate: float
    last_updated: datetime


class InterfaceMetricsService:
    """Service de collecte et analyse des métriques d'interfaces."""

    def __init__(self):
        self.metrics: List[PerformanceMetric] = []
        self.max_metrics = 10000  # Limite pour éviter la surcharge mémoire

    def record_request(self, response_time: float, success: bool,
                      message_type: Optional[str] = None,
                      endpoint: Optional[str] = None,
                      protocol: str = "unknown"):
        """
        Enregistre une métrique de requête.

        Args:
            response_time: Temps de réponse en millisecondes
            success: True si la requête a réussi
            message_type: Type de message (HL7, FHIR, etc.)
            endpoint: Endpoint utilisé
            protocol: Protocole (HL7, FHIR, HTTP, etc.)
        """
        metric = PerformanceMetric(
            timestamp=datetime.utcnow(),
            metric_type=MetricType.LATENCY,
            value=response_time,
            labels={
                "protocol": protocol,
                "success": str(success),
                "endpoint": endpoint or "unknown"
            },
            message_type=message_type,
            endpoint=endpoint
        )

        self.metrics.append(metric)

        # Limiter la taille pour éviter la surcharge mémoire
        if len(self.metrics) > self.max_metrics:
            # Garder seulement les métriques récentes
            self.metrics = self.metrics[-self.max_metrics:]

    def get_interface_metrics(self, protocol: Optional[str] = None,
                            message_type: Optional[str] = None,
                            time_window_minutes: int = 60) -> InterfaceMetrics:
        """
        Calcule les métriques consolidées pour une interface.

        Args:
            protocol: Filtrer par protocole (optionnel)
            message_type: Filtrer par type de message (optionnel)
            time_window_minutes: Fenêtre temporelle en minutes

        Returns:
            Métriques consolidées
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        # Filtrer les métriques pertinentes
        relevant_metrics = [
            m for m in self.metrics
            if m.timestamp >= cutoff_time
            and (protocol is None or m.labels.get("protocol") == protocol)
            and (message_type is None or m.message_type == message_type)
        ]

        if not relevant_metrics:
            return InterfaceMetrics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time=0.0,
                min_response_time=0.0,
                max_response_time=0.0,
                p95_response_time=0.0,
                success_rate=0.0,
                requests_per_minute=0.0,
                error_rate=0.0,
                last_updated=datetime.utcnow()
            )

        # Calculer les métriques
        response_times = [m.value for m in relevant_metrics]
        successful_requests = sum(1 for m in relevant_metrics
                                if m.labels.get("success") == "True")
        total_requests = len(relevant_metrics)

        # Calculer le taux de succès
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0

        # Statistiques de temps de réponse
        avg_response_time = statistics.mean(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)

        # Percentile 95
        sorted_times = sorted(response_times)
        p95_index = int(len(sorted_times) * 0.95)
        p95_response_time = sorted_times[min(p95_index, len(sorted_times) - 1)]

        # Taux de requêtes par minute
        time_span_minutes = time_window_minutes
        requests_per_minute = total_requests / time_span_minutes if time_span_minutes > 0 else 0

        # Taux d'erreur
        error_rate = ((total_requests - successful_requests) / total_requests) * 100 if total_requests > 0 else 0

        return InterfaceMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=total_requests - successful_requests,
            avg_response_time=round(avg_response_time, 2),
            min_response_time=round(min_response_time, 2),
            max_response_time=round(max_response_time, 2),
            p95_response_time=round(p95_response_time, 2),
            success_rate=round(success_rate, 2),
            requests_per_minute=round(requests_per_minute, 2),
            error_rate=round(error_rate, 2),
            last_updated=datetime.utcnow()
        )

    def get_metrics_by_message_type(self, time_window_minutes: int = 60) -> Dict[str, InterfaceMetrics]:
        """
        Retourne les métriques groupées par type de message.

        Args:
            time_window_minutes: Fenêtre temporelle en minutes

        Returns:
            Dictionnaire type_message -> métriques
        """
        message_types = set(m.message_type for m in self.metrics if m.message_type)

        result = {}
        for msg_type in message_types:
            result[msg_type] = self.get_interface_metrics(
                message_type=msg_type,
                time_window_minutes=time_window_minutes
            )

        return result

    def get_protocol_distribution(self, time_window_minutes: int = 60) -> Dict[str, int]:
        """
        Retourne la distribution des requêtes par protocole.

        Args:
            time_window_minutes: Fenêtre temporelle en minutes

        Returns:
            Dictionnaire protocole -> nombre de requêtes
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        distribution = defaultdict(int)
        for metric in self.metrics:
            if metric.timestamp >= cutoff_time:
                protocol = metric.labels.get("protocol", "unknown")
                distribution[protocol] += 1

        return dict(distribution)

    def get_recent_errors(self, limit: int = 10) -> List[PerformanceMetric]:
        """
        Retourne les erreurs récentes.

        Args:
            limit: Nombre maximum d'erreurs à retourner

        Returns:
            Liste des métriques d'erreur récentes
        """
        errors = [
            m for m in self.metrics
            if m.labels.get("success") == "False"
        ]

        # Trier par timestamp décroissant
        errors.sort(key=lambda x: x.timestamp, reverse=True)

        return errors[:limit]

    def clear_old_metrics(self, max_age_hours: int = 24):
        """
        Supprime les métriques anciennes.

        Args:
            max_age_hours: Âge maximum des métriques à conserver
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        self.metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]

    def get_health_status(self) -> Dict[str, Any]:
        """
        Évalue l'état de santé des interfaces basé sur les métriques.

        Returns:
            Statut de santé avec indicateurs
        """
        recent_metrics = self.get_interface_metrics(time_window_minutes=5)

        # Critères de santé
        health_status = "healthy"
        issues = []

        if recent_metrics.success_rate < 95:
            health_status = "degraded"
            issues.append(f"Taux de succès faible: {recent_metrics.success_rate}%")

        if recent_metrics.avg_response_time > 5000:  # 5 secondes
            health_status = "degraded"
            issues.append(f"Latence élevée: {recent_metrics.avg_response_time}ms")

        if recent_metrics.error_rate > 5:
            health_status = "unhealthy"
            issues.append(f"Taux d'erreur élevé: {recent_metrics.error_rate}%")

        return {
            "status": health_status,
            "issues": issues,
            "metrics": {
                "success_rate": recent_metrics.success_rate,
                "avg_response_time": recent_metrics.avg_response_time,
                "error_rate": recent_metrics.error_rate,
                "total_requests": recent_metrics.total_requests
            },
            "timestamp": datetime.utcnow().isoformat()
        }


# Instance globale du service
interface_metrics_service = InterfaceMetricsService()