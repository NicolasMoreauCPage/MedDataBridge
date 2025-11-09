"""
Système d'authentification JWT pour les API.

Fournit:
- Génération et validation de tokens JWT
- Dépendances FastAPI pour protéger les endpoints
- Gestion des utilisateurs basique
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os


# Configuration JWT
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Configuration password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """Données contenues dans le token."""
    username: Optional[str] = None
    user_id: Optional[int] = None
    roles: list[str] = []


class Token(BaseModel):
    """Token de réponse."""
    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None


class UserInDB(BaseModel):
    """Utilisateur en base (simulé)."""
    id: int
    username: str
    email: str
    hashed_password: str
    roles: list[str] = []
    is_active: bool = True


# Base de données utilisateurs simulée (à remplacer par vraie DB)
# Hashes pré-calculés pour éviter les problèmes bcrypt à l'import
# admin:admin = $2b$12$... (bcrypt)
# user:user = $2b$12$... (bcrypt)
fake_users_db: Dict[str, UserInDB] = {
    "admin": UserInDB(
        id=1,
        username="admin",
        email="admin@example.com",
        # Password: "admin" (bcrypt hashed)
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5yx3zf8xKqw0.",
        roles=["admin", "user"],
        is_active=True
    ),
    "user": UserInDB(
        id=2,
        username="user",
        email="user@example.com",
        # Password: "user" (bcrypt hashed)
        hashed_password="$2b$12$7qlKjQeOG3ZWHbrXdD1pGuLX9dwxZxOv3D7K7XOC.qXpTfZ7r3rRC",
        roles=["user"],
        is_active=True
    )
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash un mot de passe."""
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Authentifie un utilisateur."""
    user = fake_users_db.get(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crée un token JWT."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Crée un refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> TokenData:
    """Décode et valide un token JWT."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        roles: list = payload.get("roles", [])
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return TokenData(username=username, user_id=user_id, roles=roles)
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserInDB:
    """
    Dépendance FastAPI pour obtenir l'utilisateur courant.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: UserInDB = Depends(get_current_user)):
            return {"message": f"Hello {user.username}"}
    """
    token = credentials.credentials
    token_data = decode_token(token)
    
    user = fake_users_db.get(token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur non trouvé",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Utilisateur inactif"
        )
    
    return user


async def get_current_active_user(
    current_user: UserInDB = Depends(get_current_user)
) -> UserInDB:
    """Dépendance pour utilisateur actif uniquement."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Utilisateur inactif")
    return current_user


def require_role(required_role: str):
    """
    Créé une dépendance qui vérifie qu'un utilisateur a un rôle spécifique.
    
    Usage:
        @router.get("/admin-only")
        async def admin_route(user: UserInDB = Depends(require_role("admin"))):
            return {"message": "Admin access"}
    """
    async def role_checker(user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle '{required_role}' requis"
            )
        return user
    
    return role_checker


class RoleChecker:
    """
    Vérifie que l'utilisateur a au moins un des rôles requis.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(user: UserInDB = Depends(RoleChecker(["admin", "moderator"]))):
            return {"message": "Access granted"}
    """
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, user: UserInDB = Depends(get_current_user)) -> UserInDB:
        if not any(role in user.roles for role in self.allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Un des rôles suivants est requis: {', '.join(self.allowed_roles)}"
            )
        return user
