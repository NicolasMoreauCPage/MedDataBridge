"""Tests pour les endpoints protégés par rôles."""
import pytest
from fastapi.testclient import TestClient
from app.app import app
from app.auth import create_access_token


client = TestClient(app)


class TestRoleBasedAccess:
    """Tests pour l'accès basé sur les rôles."""
    
    def test_admin_endpoint_with_admin_token(self):
        """Test accès endpoint admin avec token admin."""
        # Créer token admin
        token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin", "user"]})
        
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert len(data["users"]) >= 2  # admin et user
    
    def test_admin_endpoint_with_user_token(self):
        """Test accès endpoint admin avec token user (devrait échouer)."""
        # Créer token user sans rôle admin
        token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "Rôle 'admin' requis" in response.json()["detail"]
    
    def test_admin_endpoint_without_token(self):
        """Test accès endpoint admin sans token."""
        response = client.get("/api/admin/users")
        
        assert response.status_code == 403
    
    def test_multi_role_endpoint_with_admin(self):
        """Test endpoint multi-rôles avec admin."""
        token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin"]})
        
        response = client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "admin" in data["roles"]
    
    def test_multi_role_endpoint_with_moderator(self):
        """Test endpoint multi-rôles avec moderator."""
        token = create_access_token({"sub": "moderator", "user_id": 3, "roles": ["moderator"]})
        
        # Note: moderator n'existe pas dans fake_users_db, donc devrait échouer à get_current_user
        response = client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Le token est valide mais l'utilisateur n'existe pas en DB
        assert response.status_code == 401
    
    def test_multi_role_endpoint_with_user(self):
        """Test endpoint multi-rôles avec user simple (devrait échouer)."""
        token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        
        response = client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower() or "moderator" in response.json()["detail"].lower()
    
    def test_authenticated_endpoint_with_any_user(self):
        """Test endpoint authentifié accessible à tout utilisateur."""
        token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        
        response = client.get(
            "/api/admin/profile",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "user"
        assert "user" in data["roles"]
    
    def test_maintenance_endpoint_requires_admin(self):
        """Test endpoint de maintenance nécessite admin."""
        # Avec user
        user_token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        response = client.post(
            "/api/admin/maintenance",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403
        
        # Avec admin
        admin_token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin"]})
        response = client.post(
            "/api/admin/maintenance",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "Maintenance déclenchée" in data["message"]
    
    def test_config_endpoint_requires_admin_via_rolechecker(self):
        """Test endpoint config utilisant RoleChecker."""
        # Avec user
        user_token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        response = client.get(
            "/api/admin/config",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403
        
        # Avec admin
        admin_token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin"]})
        response = client.get(
            "/api/admin/config",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "config" in data
        assert "environment" in data["config"]


class TestTokenValidation:
    """Tests pour la validation des tokens."""
    
    def test_invalid_token_format(self):
        """Test avec token mal formé."""
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401
    
    def test_missing_authorization_header(self):
        """Test sans header Authorization."""
        response = client.get("/api/admin/users")
        
        assert response.status_code == 403
    
    def test_token_with_missing_roles(self):
        """Test token sans champ roles."""
        # Token sans roles (devrait avoir liste vide par défaut)
        token = create_access_token({"sub": "user", "user_id": 2})
        
        response = client.get(
            "/api/admin/users",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        # Devrait échouer car pas de rôle admin
        assert response.status_code == 403


class TestRoleCheckerClass:
    """Tests pour la classe RoleChecker."""
    
    def test_rolechecker_with_multiple_allowed_roles(self):
        """Test RoleChecker avec plusieurs rôles autorisés."""
        # User avec un des rôles autorisés
        token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin", "user"]})
        
        response = client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 200
    
    def test_rolechecker_rejects_unauthorized_roles(self):
        """Test RoleChecker rejette les rôles non autorisés."""
        token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user", "guest"]})
        
        response = client.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 403


class TestInactiveUser:
    """Tests pour les utilisateurs inactifs."""
    
    def test_inactive_user_cannot_access_protected_endpoint(self):
        """Test qu'un utilisateur inactif ne peut pas accéder aux endpoints."""
        # Modifier temporairement fake_users_db pour marquer user comme inactif
        from app.auth import fake_users_db
        
        original_active = fake_users_db["user"].is_active
        fake_users_db["user"].is_active = False
        
        try:
            token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
            
            response = client.get(
                "/api/admin/profile",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == 403
            assert "inactif" in response.json()["detail"].lower()
        finally:
            # Restaurer
            fake_users_db["user"].is_active = original_active


class TestRoleInheritance:
    """Tests pour la hiérarchie des rôles."""
    
    def test_admin_has_all_permissions(self):
        """Test que admin peut accéder à tous les endpoints."""
        admin_token = create_access_token({"sub": "admin", "user_id": 1, "roles": ["admin", "user"]})
        
        # Admin endpoints
        response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        
        response = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        
        response = client.get("/api/admin/config", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        
        # Authenticated endpoint
        response = client.get("/api/admin/profile", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
    
    def test_user_has_limited_permissions(self):
        """Test que user simple a des permissions limitées."""
        user_token = create_access_token({"sub": "user", "user_id": 2, "roles": ["user"]})
        
        # Devrait échouer sur admin endpoints
        response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {user_token}"})
        assert response.status_code == 403
        
        response = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {user_token}"})
        assert response.status_code == 403
        
        # Devrait réussir sur authenticated endpoint
        response = client.get("/api/admin/profile", headers={"Authorization": f"Bearer {user_token}"})
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
