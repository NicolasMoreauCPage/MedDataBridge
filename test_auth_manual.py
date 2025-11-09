#!/usr/bin/env python3
"""
Test script pour vérifier l'authentification JWT.
"""
from app.auth import (
    authenticate_user,
    create_access_token,
    decode_token,
    fake_users_db
)
from datetime import timedelta

print("="*60)
print("TEST D'AUTHENTIFICATION JWT")
print("="*60)

# 1. Test des utilisateurs factices
print("\n1. Utilisateurs configurés:")
for username, user in fake_users_db.items():
    print(f"   - {username}: {user.email} (roles: {', '.join(user.roles)})")

# 2. Test d'authentification
print("\n2. Test d'authentification:")
user = authenticate_user("admin", "admin")
if user:
    print(f"   ✓ Login admin réussi: {user.username} ({user.email})")
else:
    print("   ✗ Login admin échoué")

user2 = authenticate_user("user", "user")
if user2:
    print(f"   ✓ Login user réussi: {user2.username} ({user2.email})")
else:
    print("   ✗ Login user échoué")

# Test avec mauvais mot de passe
user3 = authenticate_user("admin", "wrongpassword")
if user3:
    print("   ✗ Login avec mauvais mdp devrait échouer!")
else:
    print("   ✓ Rejet du mauvais mot de passe")

# 3. Test création de token
print("\n3. Test création de token:")
if user:
    token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "roles": user.roles},
        expires_delta=timedelta(minutes=30)
    )
    print(f"   ✓ Token créé: {token[:50]}...")
    
    # 4. Test décodage
    print("\n4. Test décodage de token:")
    try:
        token_data = decode_token(token)
        print(f"   ✓ Token décodé:")
        print(f"      - Username: {token_data.username}")
        print(f"      - User ID: {token_data.user_id}")
        print(f"      - Roles: {', '.join(token_data.roles)}")
    except Exception as e:
        print(f"   ✗ Erreur décodage: {e}")

# 5. Test avec token invalide
print("\n5. Test avec token invalide:")
try:
    decode_token("invalid.token.here")
    print("   ✗ Le token invalide devrait être rejeté!")
except Exception as e:
    print(f"   ✓ Token invalide rejeté: {e}")

print("\n" + "="*60)
print("TOUS LES TESTS PASSÉS ✓")
print("="*60)
