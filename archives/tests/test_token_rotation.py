"""
Tests for refresh token rotation and blacklisting functionality.
"""
import pytest
import time
from datetime import timedelta
from fastapi.testclient import TestClient
from jose import jwt

from app.app import app
from app.auth import (
    create_access_token,
    create_refresh_token,
    blacklist_token,
    is_token_blacklisted,
    decode_token,
    SECRET_KEY,
    ALGORITHM
)


client = TestClient(app)


@pytest.fixture
def test_user_credentials():
    """Credentials for a test user."""
    return {
        "username": "testuser",
        "password": "testpass123"
    }


@pytest.fixture
def test_tokens(test_user_credentials):
    """Generate test tokens with jti."""
    user_data = {
        "sub": test_user_credentials["username"],
        "user_id": 1,
        "roles": ["user"]
    }
    access_token = create_access_token(data=user_data)
    refresh_token = create_refresh_token(data=user_data)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token
    }


class TestJTIGeneration:
    """Test that tokens include jti claims."""
    
    def test_access_token_has_jti(self, test_tokens):
        """Access tokens should include a jti claim."""
        payload = jwt.decode(
            test_tokens["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0
    
    def test_refresh_token_has_jti(self, test_tokens):
        """Refresh tokens should include a jti claim."""
        payload = jwt.decode(
            test_tokens["refresh_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0
    
    def test_jti_is_unique(self):
        """Each token should have a unique jti."""
        user_data = {"sub": "test", "user_id": 1, "roles": ["user"]}
        
        token1 = create_access_token(data=user_data)
        token2 = create_access_token(data=user_data)
        
        payload1 = jwt.decode(token1, SECRET_KEY, algorithms=[ALGORITHM])
        payload2 = jwt.decode(token2, SECRET_KEY, algorithms=[ALGORITHM])
        
        assert payload1["jti"] != payload2["jti"]


class TestBlacklist:
    """Test token blacklisting functionality."""
    
    @pytest.fixture(autouse=True)
    def check_redis(self):
        """Skip tests if Redis is not available."""
        from app.services.cache_service import get_cache_service
        cache = get_cache_service()
        if not cache.enabled:
            pytest.skip("Redis not available - blacklist tests require Redis")
    
    def test_token_not_blacklisted_by_default(self, test_tokens):
        """Newly created tokens should not be blacklisted."""
        payload = jwt.decode(
            test_tokens["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        jti = payload["jti"]
        
        assert not is_token_blacklisted(jti)
    
    def test_blacklist_token(self, test_tokens):
        """Should be able to blacklist a token by jti."""
        payload = jwt.decode(
            test_tokens["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        jti = payload["jti"]
        
        # Blacklist the token
        result = blacklist_token(jti, ttl_seconds=3600)
        assert result is True
        
        # Verify it's blacklisted
        assert is_token_blacklisted(jti)
    
    def test_blacklist_ttl_expiry(self, test_tokens):
        """Blacklisted tokens should expire after TTL."""
        payload = jwt.decode(
            test_tokens["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        jti = payload["jti"]
        
        # Blacklist with very short TTL
        blacklist_token(jti, ttl_seconds=1)
        assert is_token_blacklisted(jti)
        
        # Wait for expiry
        time.sleep(2)
        
        # Should no longer be blacklisted
        assert not is_token_blacklisted(jti)
    
    def test_decode_token_checks_blacklist(self, test_tokens):
        """decode_token should reject blacklisted tokens."""
        payload = jwt.decode(
            test_tokens["access_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        jti = payload["jti"]
        
        # Token should decode successfully initially
        decoded = decode_token(test_tokens["access_token"], check_blacklist=True)
        assert decoded.username == "testuser"
        
        # Blacklist the token
        blacklist_token(jti, ttl_seconds=3600)
        
        # Should now raise exception
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token(test_tokens["access_token"], check_blacklist=True)
        
        assert exc_info.value.status_code == 401
        assert "révoqué" in exc_info.value.detail.lower()


class TestRefreshTokenRotation:
    """Test refresh token rotation endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, test_user_credentials):
        """Create and authenticate a test user."""
        # Note: This assumes user exists in test DB
        # You may need to create the user first or mock the DB
        response = client.post(
            "/auth/login",
            json=test_user_credentials
        )
        if response.status_code == 200:
            return response.json()
        return None
    
    def test_refresh_token_rotation_success(self, authenticated_user):
        """Successful refresh should return new tokens and blacklist old refresh token."""
        if not authenticated_user:
            pytest.skip("Test user authentication failed")
        
        old_refresh_token = authenticated_user["refresh_token"]
        old_payload = jwt.decode(
            old_refresh_token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        old_jti = old_payload["jti"]
        
        # Use refresh token to get new tokens
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh_token}
        )
        
        assert response.status_code == 200
        new_tokens = response.json()
        
        # Should receive new access and refresh tokens
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        
        # New tokens should be different
        assert new_tokens["access_token"] != authenticated_user["access_token"]
        assert new_tokens["refresh_token"] != old_refresh_token
        
        # New refresh token should have different jti
        new_payload = jwt.decode(
            new_tokens["refresh_token"],
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        assert new_payload["jti"] != old_jti
        
        # Old refresh token should be blacklisted
        assert is_token_blacklisted(old_jti)
    
    def test_old_refresh_token_cannot_be_reused(self, authenticated_user):
        """After rotation, old refresh token should be invalid."""
        if not authenticated_user:
            pytest.skip("Test user authentication failed")
        
        old_refresh_token = authenticated_user["refresh_token"]
        
        # First refresh - should succeed
        response1 = client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh_token}
        )
        assert response1.status_code == 200
        
        # Try to use old token again - should fail
        response2 = client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh_token}
        )
        assert response2.status_code == 401
    
    def test_multiple_refresh_cycles(self, authenticated_user):
        """Should be able to refresh multiple times in succession."""
        if not authenticated_user:
            pytest.skip("Test user authentication failed")
        
        current_refresh = authenticated_user["refresh_token"]
        
        # Perform multiple refresh operations
        for i in range(3):
            response = client.post(
                "/auth/refresh",
                json={"refresh_token": current_refresh}
            )
            assert response.status_code == 200
            
            tokens = response.json()
            assert "refresh_token" in tokens
            
            # Update for next iteration
            new_refresh = tokens["refresh_token"]
            assert new_refresh != current_refresh  # Should be different
            current_refresh = new_refresh


class TestLogout:
    """Test logout endpoint."""
    
    @pytest.fixture
    def authenticated_user(self, test_user_credentials):
        """Create and authenticate a test user."""
        response = client.post(
            "/auth/login",
            json=test_user_credentials
        )
        if response.status_code == 200:
            return response.json()
        return None
    
    def test_logout_blacklists_access_token(self, authenticated_user):
        """Logout should blacklist the access token."""
        if not authenticated_user:
            pytest.skip("Test user authentication failed")
        
        access_token = authenticated_user["access_token"]
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload["jti"]
        
        # Token should not be blacklisted initially
        assert not is_token_blacklisted(jti)
        
        # Logout
        response = client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        
        # Token should now be blacklisted
        assert is_token_blacklisted(jti)
    
    def test_cannot_use_token_after_logout(self, authenticated_user):
        """After logout, token should be rejected."""
        if not authenticated_user:
            pytest.skip("Test user authentication failed")
        
        access_token = authenticated_user["access_token"]
        
        # Should be able to access protected endpoint initially
        response1 = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response1.status_code == 200
        
        # Logout
        client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # Should now be rejected
        response2 = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response2.status_code == 401
    
    def test_logout_without_token_fails(self):
        """Logout without authentication should fail."""
        response = client.post("/auth/logout")
        assert response.status_code in [401, 403]


class TestSecurityScenarios:
    """Test security scenarios and edge cases."""
    
    @pytest.fixture(autouse=True)
    def check_redis(self):
        """Skip blacklist tests if Redis is not available."""
        from app.services.cache_service import get_cache_service
        cache = get_cache_service()
        if not cache.enabled:
            pytest.skip("Redis not available - blacklist tests require Redis")
    
    def test_cannot_decode_blacklisted_refresh_token(self, test_tokens):
        """Blacklisted refresh tokens should be rejected by decode_token."""
        refresh_token = test_tokens["refresh_token"]
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload["jti"]
        
        # Blacklist the refresh token
        result = blacklist_token(jti, ttl_seconds=3600)
        assert result is True
        
        # Attempt to decode should fail
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token(refresh_token, check_blacklist=True)
        
        assert exc_info.value.status_code == 401
    
    def test_refresh_with_invalid_token_format(self):
        """Refresh with malformed token should fail gracefully."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": "not.a.valid.jwt"}
        )
        assert response.status_code == 401
    
    def test_refresh_with_expired_token(self):
        """Refresh with expired token should fail."""
        # Create a token with past expiration using jose directly
        from jose import jwt as jose_jwt
        from datetime import datetime
        
        user_data = {
            "sub": "test",
            "user_id": 1,
            "roles": ["user"],
            "type": "refresh",
            "jti": "expired-token-id",
            "exp": datetime.utcnow() - timedelta(seconds=60)  # Expired 1 minute ago
        }
        
        expired_token = jose_jwt.encode(user_data, SECRET_KEY, algorithm=ALGORITHM)
        
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": expired_token}
        )
        assert response.status_code == 401
