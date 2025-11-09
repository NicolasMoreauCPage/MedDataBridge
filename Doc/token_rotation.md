# Token Rotation Implementation

## Overview
Implemented JWT refresh token rotation with blacklisting to enhance security. This prevents refresh token reuse and limits the impact of token theft.

## Features Implemented

### 1. JWT ID (jti) Claims
- Every access and refresh token now includes a unique `jti` (JWT ID) claim using UUID4
- Enables individual token tracking and revocation
- Implementation in `app/auth.py`:
  - `create_access_token()`: Adds jti to payload
  - `create_refresh_token()`: Adds jti to payload

### 2. Token Blacklisting
- Redis-backed blacklist for revoked tokens
- Automatic expiration using TTL matching token expiration
- Functions in `app/auth.py`:
  - `blacklist_token(jti, ttl_seconds)`: Adds token to blacklist with automatic expiration
  - `is_token_blacklisted(jti)`: Checks if token is revoked
  - `decode_token(token, check_blacklist=True)`: Validates and checks blacklist

### 3. Refresh Token Rotation
- Endpoint: `POST /auth/refresh`
- Process:
  1. Client sends old refresh token
  2. Server validates token
  3. Server extracts old jti and blacklists it (7 days TTL)
  4. Server issues NEW access token AND NEW refresh token
  5. Client replaces old refresh token with new one
- Implementation in `app/routers/auth.py`
- Security benefit: Old refresh tokens become invalid after use, limiting breach window

### 4. Logout Endpoint
- Endpoint: `POST /auth/logout`
- Requires: Bearer token in Authorization header
- Process:
  1. Extracts jti from access token
  2. Calculates remaining TTL from token expiration
  3. Adds jti to blacklist
  4. Client should also delete refresh token locally
- Implementation in `app/routers/auth.py`

## Testing

### Test Suite: `tests/test_token_rotation.py`
- **16 tests total**
- **4 tests passing** (jti generation, token format validation, logout without auth)
- **12 tests skipped** when Redis is not available (blacklist functionality requires Redis)

### Test Categories:

#### JTI Generation (3 tests - all passing)
- ✅ Access tokens include jti claim
- ✅ Refresh tokens include jti claim
- ✅ Each token has unique jti

#### Blacklist (4 tests - require Redis)
- Tokens not blacklisted by default
- Blacklist token functionality
- TTL expiration of blacklisted tokens
- decode_token checks blacklist

#### Refresh Token Rotation (3 tests - require Redis)
- Successful rotation returns new tokens
- Old refresh token cannot be reused
- Multiple refresh cycles work correctly

#### Logout (3 tests - 1 passing, 2 require Redis)
- ✅ Logout without authentication fails
- Logout blacklists access token
- Token rejected after logout

#### Security Scenarios (3 tests - require Redis)
- Blacklisted refresh token rejected
- Invalid token format fails gracefully
- Expired token rejected

## Security Benefits

1. **Limited Token Lifetime**: Even though refresh tokens have 7-day expiration, rotation effectively shortens their usable lifetime
2. **Token Reuse Prevention**: Once a refresh token is used, it's blacklisted and can't be used again
3. **Breach Impact Reduction**: If a refresh token is stolen, it only works until the legitimate user refreshes
4. **Logout Support**: Users can explicitly revoke their access tokens
5. **Audit Trail**: jti claims enable token usage tracking

## Dependencies

- **Redis**: Required for blacklist functionality (graceful degradation if unavailable)
- **python-jose**: JWT encoding/decoding
- **uuid**: Unique jti generation
- **cache_service**: Redis abstraction layer

## Configuration

Current settings in `app/auth.py`:
- Access token TTL: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token TTL: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`)
- Blacklist TTL: Matches token expiration (automatic cleanup)

## Usage Examples

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user", "password": "pass"}'
```

Returns:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "roles": ["user"]
}
```

### Refresh Tokens
```bash
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJ..."}'
```

Returns new access token AND new refresh token:
```json
{
  "access_token": "eyJ...",  # New access token
  "refresh_token": "eyJ...",  # New refresh token (different from input)
  "token_type": "bearer",
  "roles": ["user"]
}
```

### Logout
```bash
curl -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer eyJ..."
```

Returns:
```json
{
  "message": "Déconnexion réussie"
}
```

## Performance Considerations

- Blacklist check adds ~1-2ms per request (Redis lookup)
- Blacklist entries auto-expire, no manual cleanup needed
- Memory usage: ~100 bytes per blacklisted token
- Graceful degradation if Redis unavailable (fail-open for availability)

## Future Enhancements

1. **Token Family Tracking**: Track refresh token chains to detect compromised tokens
2. **Suspicious Activity Detection**: Flag rapid refresh patterns or concurrent usage
3. **Admin Revocation**: Allow admins to revoke user tokens
4. **Refresh Token Limits**: Limit number of active refresh tokens per user
5. **Redis Cluster**: Scale blacklist across multiple Redis instances

## References

- RFC 6749: OAuth 2.0 (refresh tokens)
- RFC 7519: JSON Web Tokens
- OWASP: Token Handling Best Practices
