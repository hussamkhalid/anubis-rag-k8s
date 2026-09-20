"""Two auth paths:

1. Machine-to-machine: header `X-ANUBIS-TOKEN` == ANUBIS_API_TOKEN (unchanged
   from the .17 contract; used by scripts and the ingest worker).
2. Human/UI: POST /auth/login with a username+password -> a short-lived JWT
   carrying a `role` claim ("user" or "admin"). The UI sends it as a Bearer
   token. Admin-only routes require role == "admin".

Either a valid Bearer JWT OR the API token satisfies a normal request; admin
actions additionally require admin role (or the API token, which is trusted).
"""
import time
import hmac

from fastapi import Request, HTTPException
import jwt

import config


def issue_token(role: str) -> tuple[str, int]:
    if not config.JWT_SECRET:
        raise HTTPException(status_code=500, detail="JWT secret not configured")
    ttl = config.JWT_TTL_HOURS * 3600
    now = int(time.time())
    payload = {"role": role, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256"), ttl


def verify_login(username: str, password: str) -> str:
    """Return the granted role, or raise 401. Constant-time comparison."""
    candidates = []
    if config.UI_ADMIN_PASSWORD:
        candidates.append(("admin", config.UI_ADMIN_PASSWORD, "admin"))
    if config.UI_USER_PASSWORD:
        candidates.append(("user", config.UI_USER_PASSWORD, "user"))
    for uname, pw, role in candidates:
        if hmac.compare_digest(username, uname) and hmac.compare_digest(password, pw):
            return role
    raise HTTPException(status_code=401, detail="Invalid credentials")


def _bearer_role(req: Request):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not config.JWT_SECRET:
        return None
    try:
        claims = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return claims.get("role")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _api_token_ok(req: Request) -> bool:
    expected = config.ANUBIS_API_TOKEN
    token = req.headers.get("X-ANUBIS-TOKEN")
    return bool(expected) and bool(token) and hmac.compare_digest(token, expected)


def require_user(req: Request) -> str:
    """Any authenticated caller (JWT user/admin, or the API token)."""
    if _api_token_ok(req):
        return "admin"
    role = _bearer_role(req)
    if role in ("user", "admin"):
        return role
    raise HTTPException(status_code=401, detail="Authentication required")


def require_admin(req: Request) -> str:
    """Admin JWT, or the trusted API token."""
    if _api_token_ok(req):
        return "admin"
    role = _bearer_role(req)
    if role == "admin":
        return role
    raise HTTPException(status_code=403, detail="Admin role required")
