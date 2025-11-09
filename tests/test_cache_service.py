"""
Tests pour le service de cache Redis.
"""
import pytest
from app.services.cache_service import CacheService, get_cache_service


def test_cache_init():
    """Test de l'initialisation du cache."""
    cache = CacheService(host="localhost", port=6379)
    
    # Devrait être soit enabled (si Redis dispo), soit disabled
    assert isinstance(cache.enabled, bool)
    
    if cache.enabled:
        assert cache.client is not None
        stats = cache.get_stats()
        assert stats["enabled"] is True
    else:
        # Si Redis n'est pas disponible, le service doit gracefully fallback
        assert cache.client is None


def test_cache_set_get():
    """Test de stockage et récupération."""
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    # Stocker une valeur
    key = "test:key:1"
    value = {"name": "Test", "count": 42}
    
    assert cache.set(key, value, ttl=60)
    
    # Récupérer la valeur
    retrieved = cache.get(key)
    assert retrieved == value
    
    # Nettoyer
    cache.delete(key)


def test_cache_exists():
    """Test de vérification d'existence."""
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    key = "test:exists:1"
    
    # Avant stockage
    assert not cache.exists(key)
    
    # Après stockage
    cache.set(key, "test", ttl=60)
    assert cache.exists(key)
    
    # Nettoyer
    cache.delete(key)


def test_cache_delete_pattern():
    """Test de suppression par motif."""
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    # Créer plusieurs clés
    cache.set("test:pattern:1", "value1", ttl=60)
    cache.set("test:pattern:2", "value2", ttl=60)
    cache.set("test:other:1", "value3", ttl=60)
    
    # Supprimer par motif
    deleted = cache.delete_pattern("test:pattern:*")
    assert deleted >= 2
    
    # Vérifier
    assert not cache.exists("test:pattern:1")
    assert not cache.exists("test:pattern:2")
    assert cache.exists("test:other:1")  # Doit rester
    
    # Nettoyer
    cache.delete("test:other:1")


def test_cache_stats():
    """Test de récupération des stats."""
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    stats = cache.get_stats()
    
    assert "enabled" in stats
    assert stats["enabled"] is True
    assert "used_memory" in stats
    assert "hit_rate" in stats


def test_cache_disabled_fallback():
    """Test du fallback quand cache désactivé."""
    # Simuler un cache avec Redis indisponible
    cache = CacheService(host="invalid_host", port=9999)
    
    # Doit être désactivé
    assert not cache.enabled
    
    # Toutes les opérations doivent échouer gracefully
    assert cache.get("any_key") is None
    assert cache.set("any_key", "value") is False
    assert cache.exists("any_key") is False
    assert cache.delete("any_key") is False
    assert cache.delete_pattern("*") == 0


def test_cache_ttl():
    """Test de l'expiration TTL."""
    import time
    
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    key = "test:ttl:1"
    
    # Stocker avec TTL de 2 secondes
    cache.set(key, "value", ttl=2)
    assert cache.exists(key)
    
    # Attendre expiration
    time.sleep(3)
    assert not cache.exists(key)


def test_cache_json_serialization():
    """Test de sérialisation de types complexes."""
    from datetime import datetime
    
    cache = get_cache_service()
    
    if not cache.enabled:
        pytest.skip("Redis non disponible")
    
    key = "test:json:1"
    value = {
        "string": "test",
        "int": 42,
        "float": 3.14,
        "bool": True,
        "null": None,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
        "datetime": datetime.now().isoformat()
    }
    
    cache.set(key, value, ttl=60)
    retrieved = cache.get(key)
    
    # Doit être identique (datetime converti en string)
    assert retrieved["string"] == value["string"]
    assert retrieved["int"] == value["int"]
    assert retrieved["float"] == value["float"]
    assert retrieved["bool"] == value["bool"]
    assert retrieved["null"] == value["null"]
    assert retrieved["list"] == value["list"]
    assert retrieved["dict"] == value["dict"]
    
    # Nettoyer
    cache.delete(key)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
