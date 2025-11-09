"""
Service de cache Redis pour optimiser les performances.

Utilisé pour mettre en cache :
- Exports FHIR fréquents
- Résultats de recherche
- Données de référence (vocabulaires, structures)
"""
import json
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta
try:
    import redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # Redis library not installed; degrade gracefully
    redis = None
    class RedisError(Exception):
        pass
from app.utils.structured_logging import metrics

logger = logging.getLogger(__name__)


class CacheService:
    """Service de gestion du cache Redis."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600  # 1 heure par défaut
    ):
        """
        Initialise la connexion Redis.
        
        Args:
            host: Hôte Redis
            port: Port Redis
            db: Numéro de base Redis
            password: Mot de passe Redis (optionnel)
            default_ttl: TTL par défaut en secondes
        """
        self.default_ttl = default_ttl
        self.enabled = True
        
        if redis is None:
            logger.warning("Redis library not installed; cache disabled (install 'redis' package to enable).")
            self.enabled = False
            self.client = None
        else:
            try:
                self.client = redis.Redis(
                    host=host,
                    port=port,
                    db=db,
                    password=password,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # Test de connexion
                self.client.ping()
                logger.info(f"✅ Cache Redis connecté sur {host}:{port}")
            except RedisError as e:
                logger.warning(f"⚠️  Cache Redis indisponible: {e}. Désactivation du cache.")
                self.enabled = False
                self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """
        Récupère une valeur depuis le cache.
        
        Args:
            key: Clé de cache
            
        Returns:
            Valeur désérialisée ou None si absente/erreur
        """
        if not self.enabled:
            return None
        
        try:
            value = self.client.get(key)
            if value is None:
                metrics.record_operation("cache_get", 0.0, status="miss", key=key)
                return None
            # Désérialiser JSON
            try:
                deserialized = json.loads(value)
                metrics.record_operation("cache_get", 0.0, status="success", key=key)
                return deserialized
            except json.JSONDecodeError as je:
                metrics.record_operation("cache_get", 0.0, status="error", key=key, error="json_decode")
                logger.error(f"Erreur décodage JSON cache '{key}': {je}")
                return None
        except RedisError as e:
            logger.error(f"Erreur lecture cache '{key}': {e}")
            metrics.record_operation("cache_get", 0.0, status="error", key=key, error=str(e))
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Stocke une valeur dans le cache.
        
        Args:
            key: Clé de cache
            value: Valeur à stocker (sera sérialisée en JSON)
            ttl: TTL en secondes (utilise default_ttl si None)
            
        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            self.client.setex(key, ttl, serialized)
            metrics.record_operation("cache_set", 0.0, status="success", key=key, ttl=ttl)
            return True
        except (RedisError, TypeError, json.JSONEncodeError) as e:
            logger.error(f"Erreur écriture cache '{key}': {e}")
            metrics.record_operation("cache_set", 0.0, status="error", key=key, ttl=ttl, error=str(e))
            return False
    
    def delete(self, key: str) -> bool:
        """
        Supprime une clé du cache.
        
        Args:
            key: Clé à supprimer
            
        Returns:
            True si supprimée, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            self.client.delete(key)
            metrics.record_operation("cache_delete", 0.0, status="success", key=key)
            return True
        except RedisError as e:
            logger.error(f"Erreur suppression cache '{key}': {e}")
            metrics.record_operation("cache_delete", 0.0, status="error", key=key, error=str(e))
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Supprime toutes les clés correspondant à un motif.
        
        Args:
            pattern: Motif Redis (ex: "fhir:export:*")
            
        Returns:
            Nombre de clés supprimées
        """
        if not self.enabled:
            return 0
        
        try:
            keys = self.client.keys(pattern)
            deleted = 0
            if keys:
                deleted = self.client.delete(*keys)
            metrics.record_operation("cache_delete_pattern", 0.0, status="success", pattern=pattern, deleted=deleted)
            return deleted
        except RedisError as e:
            logger.error(f"Erreur suppression pattern '{pattern}': {e}")
            metrics.record_operation("cache_delete_pattern", 0.0, status="error", pattern=pattern, error=str(e))
            return 0
    
    def exists(self, key: str) -> bool:
        """
        Vérifie si une clé existe dans le cache.
        
        Args:
            key: Clé à vérifier
            
        Returns:
            True si existe, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            exists = bool(self.client.exists(key))
            metrics.record_operation("cache_exists", 0.0, status="success", key=key, exists=exists)
            return exists
        except RedisError as e:
            logger.error(f"Erreur vérification existence '{key}': {e}")
            metrics.record_operation("cache_exists", 0.0, status="error", key=key, error=str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques Redis.
        
        Returns:
            Dictionnaire avec les stats (ou dict vide si erreur)
        """
        if not self.enabled:
            return {"enabled": False}
        
        try:
            info = self.client.info()
            return {
                "enabled": True,
                "used_memory": info.get("used_memory_human"),
                "total_connections": info.get("total_connections_received"),
                "total_commands": info.get("total_commands_processed"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(info)
            }
        except RedisError as e:
            logger.error(f"Erreur récupération stats: {e}")
            return {"enabled": False, "error": str(e)}
    
    def _calculate_hit_rate(self, info: Dict) -> float:
        """Calcule le taux de succès du cache."""
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    def flush_all(self) -> bool:
        """
        Vide complètement le cache (ATTENTION: opération destructive).
        
        Returns:
            True si succès, False sinon
        """
        if not self.enabled:
            return False
        
        try:
            self.client.flushdb()
            logger.warning("⚠️  Cache Redis vidé complètement")
            metrics.record_operation("cache_flush_all", 0.0, status="success")
            return True
        except RedisError as e:
            logger.error(f"Erreur vidage cache: {e}")
            metrics.record_operation("cache_flush_all", 0.0, status="error", error=str(e))
            return False


# Instance globale du service de cache
_cache_instance: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """
    Récupère l'instance singleton du service de cache.
    
    Returns:
        Instance CacheService (crée une nouvelle si n'existe pas)
    """
    global _cache_instance
    
    if _cache_instance is None:
        # Configuration depuis variables d'environnement
        import os
        
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDIS_PASSWORD")
        cache_ttl = int(os.getenv("CACHE_TTL", "3600"))
        
        _cache_instance = CacheService(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            default_ttl=cache_ttl
        )
    
    return _cache_instance


def invalidate_cache(pattern: str = "*"):
    """
    Invalide le cache selon un motif.
    
    Args:
        pattern: Motif de clés à invalider (défaut: toutes)
    """
    cache = get_cache_service()
    deleted = cache.delete_pattern(pattern)
    logger.info(f"🗑️  {deleted} clé(s) de cache invalidée(s) (pattern: {pattern})")


def invalidate_fhir_cache_for_ej(ej_id: int, export_types: Optional[List[str]] = None):
    """
    Invalide le cache FHIR pour un établissement.
    
    Args:
        ej_id: ID de l'entité juridique
        export_types: Types d'exports à invalider (défaut: tous)
                     Options: "structure", "patients", "venues"
    """
    if export_types is None:
        export_types = ["structure", "patients", "venues"]
    
    cache = get_cache_service()
    total_deleted = 0
    
    for export_type in export_types:
        pattern = f"fhir:export:{export_type}:ej:{ej_id}"
        deleted = cache.delete_pattern(pattern)
        total_deleted += deleted
        logger.debug(f"Cache invalidé pour {export_type} (EJ {ej_id}): {deleted} clés")
    
    if total_deleted > 0:
        logger.info(f"🗑️  Cache FHIR invalidé pour EJ {ej_id}: {total_deleted} clé(s)")


def invalidate_fhir_venues_cache():
    """Invalide tous les caches de venues (appelé après modification de mouvement)."""
    cache = get_cache_service()
    deleted = cache.delete_pattern("fhir:export:venues:*")
    if deleted > 0:
        logger.info(f"🗑️  Cache venues invalidé: {deleted} clé(s)")
