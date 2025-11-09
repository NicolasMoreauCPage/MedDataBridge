"""Système de logging structuré pour MedDataBridge."""
import logging
import json
import time
from datetime import datetime
from typing import Any, Dict, Optional
from functools import wraps
from contextlib import contextmanager


class StructuredLogger:
    """Logger qui produit des logs au format JSON structuré."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def _log(self, level: int, message: str, **kwargs):
        """Log un message avec des données structurées."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "logger": self.name,
            "message": message,
            **kwargs
        }
        
        # Si on a un handler JSON, on log en JSON
        # Sinon on log en texte simple
        if any(isinstance(h, JsonFormatter) for h in self.logger.handlers):
            self.logger.log(level, json.dumps(log_data))
        else:
            # Format lisible pour le développement
            extras = " ".join(f"{k}={v}" for k, v in kwargs.items())
            self.logger.log(level, f"{message} {extras}".strip())
    
    def info(self, message: str, **kwargs):
        """Log un message d'information."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log un avertissement."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log une erreur."""
        self._log(logging.ERROR, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log un message de debug."""
        self._log(logging.DEBUG, message, **kwargs)
    
    @contextmanager
    def operation(self, operation_name: str, **kwargs):
        """
        Context manager pour logger une opération avec durée.
        
        Usage:
            with logger.operation("export_structure", ej_id=1):
                # ... code ...
        """
        start_time = time.time()
        operation_id = f"{operation_name}_{int(start_time * 1000)}"
        
        self.info(
            f"Starting {operation_name}",
            operation=operation_name,
            operation_id=operation_id,
            **kwargs
        )
        
        try:
            yield
            duration = time.time() - start_time
            self.info(
                f"Completed {operation_name}",
                operation=operation_name,
                operation_id=operation_id,
                duration_seconds=duration,
                status="success",
                **kwargs
            )
        except Exception as e:
            duration = time.time() - start_time
            self.error(
                f"Failed {operation_name}",
                operation=operation_name,
                operation_id=operation_id,
                duration_seconds=duration,
                status="error",
                error=str(e),
                error_type=type(e).__name__,
                **kwargs
            )
            raise


class JsonFormatter(logging.Formatter):
    """Formatter qui produit des logs JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Formate un log record en JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Ajouter les attributs extra si présents
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "operation_id"):
            log_data["operation_id"] = record.operation_id
        if hasattr(record, "duration_seconds"):
            log_data["duration_seconds"] = record.duration_seconds
        if hasattr(record, "status"):
            log_data["status"] = record.status
        
        # Ajouter l'exception si présente
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def log_operation(operation_name: str):
    """
    Décorateur pour logger automatiquement une fonction/méthode.
    
    Usage:
        @log_operation("export_structure")
        def export_structure(ej_id: int):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            
            # Essayer d'extraire des infos des arguments
            func_args = {}
            if args:
                func_args["args_count"] = len(args)
            if kwargs:
                func_args.update({k: v for k, v in kwargs.items() if not k.startswith("_")})
            
            with logger.operation(operation_name, function=func.__name__, **func_args):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


class MetricsCollector:
    """Collecteur de métriques pour les opérations."""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
        self.logger = StructuredLogger("metrics")
    
    def record_operation(
        self,
        operation: str,
        duration: float,
        status: str = "success",
        **kwargs
    ):
        """Enregistre une métrique d'opération."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                "count": 0,
                "success_count": 0,
                "error_count": 0,
                "total_duration": 0.0,
                "min_duration": float('inf'),
                "max_duration": 0.0,
            }
        
        metrics = self.metrics[operation]
        metrics["count"] += 1
        
        if status == "success":
            metrics["success_count"] += 1
        else:
            metrics["error_count"] += 1
        
        metrics["total_duration"] += duration
        metrics["min_duration"] = min(metrics["min_duration"], duration)
        metrics["max_duration"] = max(metrics["max_duration"], duration)
        
        # Logger la métrique
        self.logger.info(
            f"Operation metric: {operation}",
            operation=operation,
            duration=duration,
            status=status,
            **kwargs
        )
    
    def get_metrics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Récupère les métriques."""
        if operation:
            metrics = self.metrics.get(operation, {})
            if metrics and metrics["count"] > 0:
                metrics["avg_duration"] = metrics["total_duration"] / metrics["count"]
                metrics["success_rate"] = metrics["success_count"] / metrics["count"]
            return metrics
        
        # Retourner toutes les métriques
        result = {}
        for op, metrics in self.metrics.items():
            result[op] = dict(metrics)
            if metrics["count"] > 0:
                result[op]["avg_duration"] = metrics["total_duration"] / metrics["count"]
                result[op]["success_rate"] = metrics["success_count"] / metrics["count"]
        
        return result
    
    def reset(self):
        """Réinitialise les métriques."""
        self.metrics.clear()

    # --- Extension légère pour compatibilité avec code utilisant metrics.observe() ---
    def observe(self, metric: str, value: float, tags: Optional[Dict[str, Any]] = None):
        """Observe une valeur (style gauge/histogram simplifié).

        Conserve agrégats min/max/sum/count et la dernière valeur. Tags sont fusionnés.
        """
        if metric not in self.metrics:
            self.metrics[metric] = {
                "count": 0,
                "total": 0.0,
                "min": float('inf'),
                "max": 0.0,
                "last": None,
                "tags": tags or {},
            }
        m = self.metrics[metric]
        m["count"] += 1
        m["total"] += value
        m["min"] = min(m["min"], value)
        m["max"] = max(m["max"], value)
        m["last"] = value
        if tags:
            # Met à jour les tags (sans pertes)
            m["tags"].update(tags)
        # Log basique
        self.logger.info(
            f"Metric observed: {metric}", metric=metric, value=value, tags=m.get("tags")
        )


# Instance globale du collecteur de métriques
metrics = MetricsCollector()


def configure_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None
):
    """
    Configure le système de logging.
    
    Args:
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
        json_format: Si True, utilise le format JSON
        log_file: Chemin du fichier de log (optionnel)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configuration du root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Supprimer les handlers existants
    root_logger.handlers.clear()
    
    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    if json_format:
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"
            )
        )
    
    root_logger.addHandler(console_handler)
    
    # Handler fichier si demandé
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        
        if json_format:
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s: %(message)s"
                )
            )
        
        root_logger.addHandler(file_handler)


# Logger par défaut pour le module
logger = StructuredLogger(__name__)