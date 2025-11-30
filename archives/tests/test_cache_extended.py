"""Tests étendus pour le service cache (amélioration coverage)."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from redis.exceptions import RedisError, ConnectionError, TimeoutError
from app.services.cache_service import (
    CacheService,
    get_cache_service,
    invalidate_cache,
    invalidate_fhir_cache_for_ej,
    invalidate_fhir_venues_cache,
    _cache_instance
)


class TestCacheServiceErrorHandling:
    """Tests pour la gestion d'erreurs du cache."""
    
    def test_get_with_redis_error(self):
        """Test get() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Simuler erreur Redis
        with patch.object(cache.client, 'get', side_effect=RedisError("Connection lost")):
            result = cache.get("test:key")
            assert result is None
    
    def test_get_with_json_decode_error(self):
        """Test get() avec données JSON invalides."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Simuler retour de données non-JSON
        with patch.object(cache.client, 'get', return_value="invalid{json"):
            result = cache.get("test:key")
            assert result is None
    
    def test_set_with_redis_error(self):
        """Test set() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Simuler erreur Redis
        with patch.object(cache.client, 'setex', side_effect=RedisError("Write failed")):
            result = cache.set("test:key", {"value": 123})
            assert result is False
    
    def test_set_with_json_encode_error(self):
        """Test set() avec objet non-sérialisable."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Créer objet non-sérialisable (sans default=str il échouerait)
        # Mais avec default=str, ça passe - testons TypeError directement
        with patch('json.dumps', side_effect=TypeError("Not serializable")):
            result = cache.set("test:key", {"value": 123})
            assert result is False
    
    def test_delete_with_redis_error(self):
        """Test delete() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'delete', side_effect=RedisError("Delete failed")):
            result = cache.delete("test:key")
            assert result is False
    
    def test_delete_pattern_with_redis_error_on_keys(self):
        """Test delete_pattern() avec erreur lors de keys()."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'keys', side_effect=RedisError("Keys failed")):
            result = cache.delete_pattern("test:*")
            assert result == 0
    
    def test_delete_pattern_with_redis_error_on_delete(self):
        """Test delete_pattern() avec erreur lors de delete()."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'keys', return_value=["key1", "key2"]):
            with patch.object(cache.client, 'delete', side_effect=RedisError("Delete failed")):
                result = cache.delete_pattern("test:*")
                assert result == 0
    
    def test_exists_with_redis_error(self):
        """Test exists() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'exists', side_effect=RedisError("Check failed")):
            result = cache.exists("test:key")
            assert result is False
    
    def test_get_stats_with_redis_error(self):
        """Test get_stats() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'info', side_effect=RedisError("Info failed")):
            stats = cache.get_stats()
            assert stats["enabled"] is False
            assert "error" in stats
    
    def test_flush_all_with_redis_error(self):
        """Test flush_all() avec erreur Redis."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'flushdb', side_effect=RedisError("Flush failed")):
            result = cache.flush_all()
            assert result is False


class TestCachePatternMatching:
    """Tests pour le matching de patterns."""
    
    def test_delete_pattern_with_empty_keys(self):
        """Test delete_pattern() quand aucune clé ne correspond."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Pattern qui ne match rien
        deleted = cache.delete_pattern("nonexistent:pattern:*")
        assert deleted == 0
    
    def test_delete_pattern_with_multiple_keys(self):
        """Test delete_pattern() avec plusieurs clés."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Créer plusieurs clés
        cache.set("pattern:test:1", "val1", ttl=60)
        cache.set("pattern:test:2", "val2", ttl=60)
        cache.set("pattern:test:3", "val3", ttl=60)
        
        # Supprimer par pattern
        deleted = cache.delete_pattern("pattern:test:*")
        assert deleted >= 3
        
        # Vérifier suppression
        assert not cache.exists("pattern:test:1")
        assert not cache.exists("pattern:test:2")
        assert not cache.exists("pattern:test:3")
    
    def test_delete_pattern_wildcard_variations(self):
        """Test delete_pattern() avec différents wildcards."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Créer clés
        cache.set("prefix:a:suffix", "val", ttl=60)
        cache.set("prefix:b:suffix", "val", ttl=60)
        
        # Pattern avec wildcard au milieu
        deleted = cache.delete_pattern("prefix:*:suffix")
        assert deleted >= 2


class TestCacheMetrics:
    """Tests pour les métriques du cache."""
    
    def test_get_records_miss_metric(self):
        """Test que get() enregistre une métrique de miss."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Récupérer clé inexistante
        with patch('app.services.cache_service.metrics.record_operation') as mock_metrics:
            cache.get("nonexistent:key")
            mock_metrics.assert_called()
            # Vérifier qu'un appel contient status="miss"
            calls = [str(call) for call in mock_metrics.call_args_list]
            assert any('miss' in call for call in calls)
    
    def test_get_records_success_metric(self):
        """Test que get() enregistre une métrique de succès."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Stocker puis récupérer
        cache.set("metric:test", {"value": 123}, ttl=60)
        
        with patch('app.services.cache_service.metrics.record_operation') as mock_metrics:
            cache.get("metric:test")
            mock_metrics.assert_called()
            # Vérifier qu'un appel contient status="success"
            calls = [str(call) for call in mock_metrics.call_args_list]
            assert any('success' in call for call in calls)
        
        cache.delete("metric:test")
    
    def test_set_records_metric(self):
        """Test que set() enregistre une métrique."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch('app.services.cache_service.metrics.record_operation') as mock_metrics:
            cache.set("metric:set", {"val": 1}, ttl=60)
            mock_metrics.assert_called()
        
        cache.delete("metric:set")
    
    def test_delete_records_metric(self):
        """Test que delete() enregistre une métrique."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        cache.set("metric:delete", "val", ttl=60)
        
        with patch('app.services.cache_service.metrics.record_operation') as mock_metrics:
            cache.delete("metric:delete")
            mock_metrics.assert_called()


class TestCacheHelperFunctions:
    """Tests pour les fonctions helper."""
    
    def test_invalidate_cache_default_pattern(self):
        """Test invalidate_cache() avec pattern par défaut."""
        # Ne pas vraiment invalider tout - mocker
        with patch('app.services.cache_service.get_cache_service') as mock_get:
            mock_cache = Mock()
            mock_cache.delete_pattern.return_value = 5
            mock_get.return_value = mock_cache
            
            invalidate_cache()
            mock_cache.delete_pattern.assert_called_once_with("*")
    
    def test_invalidate_cache_custom_pattern(self):
        """Test invalidate_cache() avec pattern personnalisé."""
        with patch('app.services.cache_service.get_cache_service') as mock_get:
            mock_cache = Mock()
            mock_cache.delete_pattern.return_value = 3
            mock_get.return_value = mock_cache
            
            invalidate_cache("fhir:*")
            mock_cache.delete_pattern.assert_called_once_with("fhir:*")
    
    def test_invalidate_fhir_cache_for_ej_default_types(self):
        """Test invalidate_fhir_cache_for_ej() avec types par défaut."""
        with patch('app.services.cache_service.get_cache_service') as mock_get:
            mock_cache = Mock()
            mock_cache.delete_pattern.return_value = 1
            mock_get.return_value = mock_cache
            
            invalidate_fhir_cache_for_ej(123)
            
            # Devrait appeler pour structure, patients, venues
            assert mock_cache.delete_pattern.call_count == 3
            calls = [call[0][0] for call in mock_cache.delete_pattern.call_args_list]
            assert "fhir:export:structure:ej:123" in calls
            assert "fhir:export:patients:ej:123" in calls
            assert "fhir:export:venues:ej:123" in calls
    
    def test_invalidate_fhir_cache_for_ej_specific_types(self):
        """Test invalidate_fhir_cache_for_ej() avec types spécifiques."""
        with patch('app.services.cache_service.get_cache_service') as mock_get:
            mock_cache = Mock()
            mock_cache.delete_pattern.return_value = 1
            mock_get.return_value = mock_cache
            
            invalidate_fhir_cache_for_ej(456, export_types=["structure"])
            
            # Devrait appeler seulement pour structure
            mock_cache.delete_pattern.assert_called_once()
            assert "structure" in mock_cache.delete_pattern.call_args[0][0]
    
    def test_invalidate_fhir_venues_cache(self):
        """Test invalidate_fhir_venues_cache()."""
        with patch('app.services.cache_service.get_cache_service') as mock_get:
            mock_cache = Mock()
            mock_cache.delete_pattern.return_value = 10
            mock_get.return_value = mock_cache
            
            invalidate_fhir_venues_cache()
            mock_cache.delete_pattern.assert_called_once_with("fhir:export:venues:*")


class TestCacheStats:
    """Tests pour les statistiques du cache."""
    
    def test_calculate_hit_rate_zero_total(self):
        """Test _calculate_hit_rate() avec total zéro."""
        cache = CacheService()
        
        info = {"keyspace_hits": 0, "keyspace_misses": 0}
        rate = cache._calculate_hit_rate(info)
        assert rate == 0.0
    
    def test_calculate_hit_rate_normal(self):
        """Test _calculate_hit_rate() avec valeurs normales."""
        cache = CacheService()
        
        info = {"keyspace_hits": 75, "keyspace_misses": 25}
        rate = cache._calculate_hit_rate(info)
        assert rate == 75.0
    
    def test_calculate_hit_rate_partial(self):
        """Test _calculate_hit_rate() avec valeur partielle."""
        cache = CacheService()
        
        info = {"keyspace_hits": 33, "keyspace_misses": 67}
        rate = cache._calculate_hit_rate(info)
        assert 32.0 <= rate <= 34.0  # ~33%
    
    def test_get_stats_when_enabled(self):
        """Test get_stats() quand cache activé."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        stats = cache.get_stats()
        assert stats["enabled"] is True
        assert "used_memory" in stats
        assert "total_connections" in stats
        assert "keyspace_hits" in stats
        assert "hit_rate" in stats
    
    def test_get_stats_when_disabled(self):
        """Test get_stats() quand cache désactivé."""
        cache = CacheService(host="invalid", port=9999)
        
        stats = cache.get_stats()
        assert stats["enabled"] is False


class TestCacheFlush:
    """Tests pour le vidage du cache."""
    
    def test_flush_all_when_enabled(self):
        """Test flush_all() quand cache activé."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        # Ajouter une clé
        cache.set("test:flush:key", "value", ttl=60)
        
        # Vider
        result = cache.flush_all()
        assert result is True
        
        # Vérifier suppression
        assert not cache.exists("test:flush:key")
    
    def test_flush_all_when_disabled(self):
        """Test flush_all() quand cache désactivé."""
        cache = CacheService(host="invalid", port=9999)
        
        result = cache.flush_all()
        assert result is False


class TestCacheSingleton:
    """Tests pour le pattern singleton."""
    
    def test_get_cache_service_returns_singleton(self):
        """Test que get_cache_service() retourne toujours la même instance."""
        cache1 = get_cache_service()
        cache2 = get_cache_service()
        
        assert cache1 is cache2
    
    def test_get_cache_service_creates_instance_on_first_call(self):
        """Test que get_cache_service() crée l'instance au premier appel."""
        # Reset l'instance globale
        import app.services.cache_service as cache_module
        original_instance = cache_module._cache_instance
        cache_module._cache_instance = None
        
        try:
            cache = get_cache_service()
            assert cache is not None
            assert isinstance(cache, CacheService)
        finally:
            # Restaurer
            cache_module._cache_instance = original_instance


class TestCacheEdgeCases:
    """Tests pour les cas limites."""
    
    def test_set_with_none_ttl_uses_default(self):
        """Test que set() avec ttl=None utilise default_ttl."""
        cache = CacheService(default_ttl=7200)
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        with patch.object(cache.client, 'setex') as mock_setex:
            cache.set("test:key", "value", ttl=None)
            # Vérifier que setex a été appelé avec default_ttl
            assert mock_setex.call_args[0][1] == 7200
    
    def test_get_with_none_value_returns_none(self):
        """Test que get() retourne None pour clé inexistante."""
        cache = CacheService()
        if not cache.enabled:
            pytest.skip("Redis non disponible")
        
        result = cache.get("definitely:does:not:exist:" + str(id(cache)))
        assert result is None
    
    def test_operations_when_disabled_return_safely(self):
        """Test que toutes les opérations retournent des valeurs safe quand désactivé."""
        cache = CacheService(host="invalid", port=9999)
        
        assert cache.get("key") is None
        assert cache.set("key", "val") is False
        assert cache.delete("key") is False
        assert cache.delete_pattern("*") == 0
        assert cache.exists("key") is False
        assert cache.flush_all() is False
        assert cache.get_stats() == {"enabled": False}
