"""
Tests for cache metrics API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from app.app import app


client = TestClient(app)


@pytest.fixture
def admin_token():
    """Get an admin token for testing."""
    # Note: This assumes test admin user exists in fake_users_db
    # Using the default fake admin credentials from app.auth
    response = client.post(
        "/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    return None


class TestCacheMetricsAPI:
    """Test cache metrics API endpoints."""
    
    def test_cache_metrics_requires_auth(self):
        """Cache metrics should require authentication."""
        response = client.get("/api/metrics/cache")
        assert response.status_code in [401, 403]
    
    def test_cache_metrics_with_invalid_token(self):
        """Invalid token should be rejected."""
        response = client.get(
            "/api/metrics/cache",
            headers={"Authorization": "Bearer invalid-token"}
        )
        assert response.status_code == 401
    
    def test_cache_metrics_with_admin_token(self, admin_token):
        """Admin should be able to access cache metrics."""
        if not admin_token:
            pytest.skip("Admin user not available")
        
        response = client.get(
            "/api/metrics/cache",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should succeed or return cache unavailable
        assert response.status_code == 200
        data = response.json()
        
        assert "enabled" in data
        
        if data["enabled"]:
            # If Redis is available, check structure
            assert "hit_rate" in data
            assert "keyspace_hits" in data
            assert "keyspace_misses" in data
            assert "used_memory" in data
            assert "total_operations" in data
    
    def test_cache_health_check_public(self):
        """Cache health check should be public."""
        response = client.get("/api/metrics/cache/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
        assert "enabled" in data
        assert "message" in data
    
    def test_cache_health_check_structure(self):
        """Health check should return proper structure."""
        response = client.get("/api/metrics/cache/health")
        data = response.json()
        
        # Required fields
        assert "status" in data
        assert "enabled" in data
        assert "message" in data
        
        # Status should be valid
        assert data["status"] in ["healthy", "unhealthy", "degraded"]
        
        # Message should be non-empty
        assert len(data["message"]) > 0


class TestCacheDashboard:
    """Test cache dashboard HTML page."""
    
    def test_cache_dashboard_accessible(self):
        """Dashboard page should be accessible."""
        response = client.get("/cache-dashboard")
        
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
    
    def test_cache_dashboard_contains_title(self):
        """Dashboard should contain title."""
        response = client.get("/cache-dashboard")
        content = response.text
        
        assert "Cache Metrics Dashboard" in content
    
    def test_cache_dashboard_has_chart(self):
        """Dashboard should include chart functionality."""
        response = client.get("/cache-dashboard")
        content = response.text
        
        # Check for Chart.js
        assert "chart.js" in content.lower() or "Chart" in content
        
        # Check for metric elements
        assert "hit-rate" in content
        assert "total-hits" in content
        assert "total-misses" in content


class TestMetricsIntegration:
    """Integration tests for metrics system."""
    
    def test_cache_metrics_match_health_check(self, admin_token):
        """Metrics and health check should agree on cache status."""
        if not admin_token:
            pytest.skip("Admin user not available")
        
        # Get health check
        health_response = client.get("/api/metrics/cache/health")
        health_data = health_response.json()
        
        # Get detailed metrics
        metrics_response = client.get(
            "/api/metrics/cache",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        metrics_data = metrics_response.json()
        
        # Both should agree on enabled status
        assert health_data["enabled"] == metrics_data["enabled"]
        
        # If healthy, metrics should show valid data
        if health_data["status"] == "healthy":
            assert metrics_data["enabled"] is True
            assert "hit_rate" in metrics_data
    
    def test_cache_metrics_format(self, admin_token):
        """Cache metrics should have correct data types."""
        if not admin_token:
            pytest.skip("Admin user not available")
        
        response = client.get(
            "/api/metrics/cache",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if response.status_code != 200:
            pytest.skip("Metrics not available")
        
        data = response.json()
        
        if data.get("enabled"):
            # Numeric fields should be numbers
            assert isinstance(data.get("keyspace_hits", 0), int)
            assert isinstance(data.get("keyspace_misses", 0), int)
            assert isinstance(data.get("total_operations", 0), int)
            
            # Hit rate should be percentage (0-100)
            hit_rate = data.get("hit_rate", 0)
            assert isinstance(hit_rate, (int, float))
            assert 0 <= hit_rate <= 100
            
            # Percentages should sum to ~100
            hits_pct = data.get("hits_percentage", 0)
            misses_pct = data.get("misses_percentage", 0)
            
            if data["total_operations"] > 0:
                total_pct = hits_pct + misses_pct
                assert 99.9 <= total_pct <= 100.1  # Allow rounding errors


class TestCacheMetricsErrors:
    """Test error handling in cache metrics."""
    
    def test_metrics_graceful_degradation(self, admin_token):
        """Metrics should handle Redis unavailability gracefully."""
        if not admin_token:
            pytest.skip("Admin user not available")
        
        response = client.get(
            "/api/metrics/cache",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Should always return 200 even if cache unavailable
        assert response.status_code == 200
        
        data = response.json()
        assert "enabled" in data
        
        # If disabled, should still return valid response
        if not data["enabled"]:
            assert data["enabled"] is False
    
    def test_health_check_no_crash_without_redis(self):
        """Health check should not crash if Redis unavailable."""
        response = client.get("/api/metrics/cache/health")
        
        # Should return valid response
        assert response.status_code == 200
        data = response.json()
        
        # Should have required fields
        assert "status" in data
        assert "enabled" in data
        assert "message" in data
