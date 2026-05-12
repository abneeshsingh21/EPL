# epl-auth

Authentication & security for EPL — JWT tokens, password hashing, sessions, API keys.

## Installation

```
epl install epl-auth
```

## Quick Start

```epl
Import "epl-auth"

Note: Hash a password
Set hashed to hash_password("my_secret")
Set valid to verify_password("my_secret", hashed)

Note: Create a JWT token
Set token to create_token({"user_id": 1, "role": "admin"}, "secret", 24)
Set payload to verify_token(token, "secret")
Say "User: " + payload["user_id"]
```

## Features

- **Password Hashing** — bcrypt with configurable rounds
- **JWT Tokens** — Create, verify, refresh, expiration check
- **API Keys** — Generate prefixed secure keys
- **Sessions** — Create, validate, invalidate
- **OAuth2** — Build auth URLs, exchange codes (GitHub, Google, etc.)
- **Hashing** — SHA-256, SHA-512, MD5, HMAC signing
- **Rate Limiting** — Per-identifier request throttling
- **Input Validation** — Email, password strength, sanitization

## API Reference

| Function | Description |
|----------|-------------|
| `hash_password(pw)` | Bcrypt hash |
| `verify_password(pw, hash)` | Verify against hash |
| `create_token(payload, secret, hours)` | Create JWT |
| `verify_token(token, secret)` | Verify & decode JWT |
| `is_token_expired(token, secret)` | Check expiration |
| `refresh_token(token, secret, hours)` | Refresh JWT |
| `generate_api_key(prefix)` | Random API key |
| `generate_secret(length)` | Crypto-random string |
| `generate_uuid()` | UUID v4 |
| `hash_sha256(data)` | SHA-256 digest |
| `hmac_sign(msg, key)` | HMAC-SHA256 signature |
| `hmac_verify(msg, sig, key)` | Verify HMAC |
| `is_valid_email(email)` | Email validation |
| `is_strong_password(pw)` | Strength check |
| `sanitize_input(text)` | Strip dangerous chars |
| `check_rate_limit(id, max, window)` | Rate limit check |
