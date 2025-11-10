#!/usr/bin/env python3
"""Script pour générer un token JWT pour accéder aux dashboards."""

from datetime import datetime, timedelta
from jose import jwt

# Configuration (doit correspondre à app/auth.py)
SECRET_KEY = "your-secret-key-here-change-in-production"  # À ajuster si différent
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict):
    """Crée un token JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    # Créer un token pour un utilisateur admin
    token_data = {
        "sub": "admin",  # username
        "role": "admin",
        "scopes": ["read", "write", "admin"]
    }
    
    token = create_access_token(token_data)
    
    print("=" * 60)
    print("TOKEN JWT GÉNÉRÉ")
    print("=" * 60)
    print(f"\nToken: {token}\n")
    print(f"Expire dans: {ACCESS_TOKEN_EXPIRE_MINUTES} minutes")
    print("\nUtilisation:")
    print("1. Copiez le token ci-dessus")
    print("2. Collez-le dans le champ 'JWT access token' du navigateur")
    print("=" * 60)
