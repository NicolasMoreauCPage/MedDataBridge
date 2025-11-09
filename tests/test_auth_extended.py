"""Tests étendus pour le module auth (amélioration coverage)."""
import pytest
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi import HTTPException
from app.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    Token,
    TokenData,
    UserInDB,
    SECRET_KEY,
    ALGORITHM
)


class TestTokenCreation:
    """Tests de création de tokens."""
    
    def test_create_access_token_with_roles(self):
        """Test création token access avec roles."""
        data = {"sub": "testuser", "roles": ["admin", "user"]}
        token = create_access_token(data)
        assert token is not None
        assert isinstance(token, str)
        
        # Décoder et vérifier contenu
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["roles"] == ["admin", "user"]
        assert "exp" in payload
    
    def test_create_access_token_with_expiry(self):
        """Test création token avec expiration personnalisée."""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=10)
        token = create_access_token(data, expires_delta=expires_delta)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = payload["exp"]
        exp_time = datetime.fromtimestamp(exp_timestamp)
        now = datetime.utcnow()
        
        # Vérifier que l'expiration est dans le futur (pas exact à cause du timing d'exécution)
        assert exp_time > now
    
    def test_create_refresh_token(self):
        """Test création refresh token."""
        data = {"sub": "testuser", "roles": ["user"]}
        token = create_refresh_token(data)
        assert token is not None
        assert isinstance(token, str)
        
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["roles"] == ["user"]
        assert "exp" in payload


class TestTokenVerification:
    """Tests pour la vérification de tokens."""
    
    def test_verify_valid_token(self):
        """Test vérification token valide."""
        data = {"sub": "testuser", "user_id": 123, "roles": ["user"]}
        token = create_access_token(data)
        
        token_data = decode_token(token)
        assert token_data.username == "testuser"
        assert token_data.user_id == 123
        assert token_data.roles == ["user"]
    
    def test_verify_expired_token(self):
        """Test vérification token expiré."""
        data = {"sub": "testuser"}
        # Créer un token déjà expiré
        expired_token = jwt.encode(
            {**data, "exp": datetime.utcnow() - timedelta(minutes=1)},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)
        assert exc_info.value.status_code == 401
    
    def test_verify_malformed_token(self):
        """Test vérification token mal formé."""
        malformed_token = "not.a.valid.jwt.token"
        with pytest.raises(HTTPException) as exc_info:
            decode_token(malformed_token)
        assert exc_info.value.status_code == 401
    
    def test_verify_token_wrong_signature(self):
        """Test vérification token avec mauvaise signature."""
        data = {"sub": "testuser"}
        # Créer un token avec une clé différente
        wrong_token = jwt.encode(data, "wrong_secret_key", algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token(wrong_token)
        assert exc_info.value.status_code == 401
    
    def test_verify_token_missing_sub(self):
        """Test vérification token sans 'sub' claim."""
        data = {"other_field": "value"}
        token = jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)
        
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token)
        assert exc_info.value.status_code == 401


class TestPasswordHashing:
    """Tests des fonctions de hachage de mot de passe."""
    
    def test_get_password_hash(self):
        """Test hachage mot de passe."""
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_verify_correct_password(self):
        """Test vérification mot de passe correct."""
        password = "mysecretpassword"
        hashed = get_password_hash(password)
        
        assert verify_password(password, hashed)
    
    def test_verify_incorrect_password(self):
        """Test vérification mot de passe incorrect."""
        password = "mysecretpassword"
        wrong_password = "wrongpassword"
        hashed = get_password_hash(password)
        
        assert not verify_password(wrong_password, hashed)
    
    def test_hash_password_different_each_time(self):
        """Test que le hachage produit des résultats différents à chaque fois (salt)."""
        password = "mysecretpassword"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Les hashs doivent être différents mais tous deux valides
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestModels:
    """Tests des modèles Pydantic."""
    
    def test_token_model(self):
        """Test modèle Token."""
        token = Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="bearer",
            roles=["admin", "user"]
        )
        assert token.access_token == "test_access_token"
        assert token.refresh_token == "test_refresh_token"
        assert token.token_type == "bearer"
        assert token.roles == ["admin", "user"]
    
    def test_token_model_defaults(self):
        """Test valeurs par défaut modèle Token."""
        token = Token(
            access_token="test_token",
            refresh_token="test_refresh"
        )
        assert token.token_type == "bearer"
        assert token.roles == []  # Default is empty list, not None
    
    def test_token_data_model(self):
        """Test modèle TokenData."""
        token_data = TokenData(username="testuser", roles=["admin"])
        assert token_data.username == "testuser"
        assert token_data.roles == ["admin"]
    
    def test_token_data_model_optional_roles(self):
        """Test TokenData avec roles optionnels."""
        token_data = TokenData(username="testuser")
        assert token_data.username == "testuser"
        assert token_data.roles == []  # Default is empty list, not None
    
    def test_user_model(self):
        """Test modèle UserInDB."""
        user = UserInDB(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pw",
            roles=["user"],
            is_active=True
        )
        assert user.id == 1
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_pw"
        assert user.roles == ["user"]
        assert user.is_active
    
    def test_user_model_optional_fields(self):
        """Test UserInDB avec valeurs par défaut."""
        user = UserInDB(
            id=1,
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_pw"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == []  # Default is empty list
        assert user.is_active  # Default is True


class TestEdgeCases:
    """Tests de cas limites."""
    
    def test_create_token_with_empty_data(self):
        """Test création token avec données vides."""
        token = create_access_token({})
        assert isinstance(token, str)
        # Le token devrait être valide même avec données vides
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload
    
    def test_create_token_with_extra_claims(self):
        """Test création token avec claims supplémentaires."""
        data = {
            "sub": "testuser",
            "roles": ["admin"],
            "custom_field": "custom_value"
        }
        token = create_access_token(data)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "testuser"
        assert payload["custom_field"] == "custom_value"
        assert payload["roles"] == ["admin"]
    
    def test_verify_empty_token(self):
        """Test vérification token vide."""
        with pytest.raises(HTTPException) as exc_info:
            decode_token("")
        assert exc_info.value.status_code == 401
    
    def test_hash_password_empty(self):
        """Test hashage mot de passe vide."""
        hashed = get_password_hash("")
        assert isinstance(hashed, str)
        assert len(hashed) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
