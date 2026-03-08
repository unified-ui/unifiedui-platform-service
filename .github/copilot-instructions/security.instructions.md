---
applyTo: '**'
---

# Security Guidelines — Platform Service (Python/FastAPI/PostgreSQL)

## CRITICAL: Read This First

These rules are **mandatory** for all code generation. Violations cause SAST/CodeQL failures in CI.

---

## 1. SQL Injection Prevention

**Threat**: User-controlled values concatenated into SQL queries → attacker manipulates database operations.

### Rules

- **NEVER** use f-strings, `.format()`, or `%` string interpolation to build SQL queries.
- **ALWAYS** use SQLAlchemy ORM methods (`.filter()`, `.where()`) with bound parameters.
- **ALWAYS** use `text()` with `:param` bind syntax for raw SQL when ORM is insufficient.
- **NEVER** pass raw user input into `.order_by()` or column references — map to allowed values first.

### Correct Pattern

```python
# ORM filtering — safe by default
stmt = select(ChatAgent).where(
    ChatAgent.tenant_id == tenant_id,
    ChatAgent.name == name
)

# Raw SQL with bound params when unavoidable
stmt = text("SELECT * FROM agents WHERE tenant_id = :tid")
result = session.execute(stmt, {"tid": tenant_id})
```

### Wrong Pattern

```python
# WRONG — SQL injection via f-string
stmt = text(f"SELECT * FROM agents WHERE tenant_id = '{tenant_id}'")

# WRONG — unvalidated column in order_by
stmt = select(Agent).order_by(text(request.sort_field))
```

---

## 2. SSRF Prevention (Server-Side Request Forgery)

**Threat**: User-controlled URLs in outbound HTTP requests → attacker redirects server to internal services or cloud metadata.

### Rules

- **ALWAYS** validate URLs before making HTTP requests:
  - Parse with `urllib.parse.urlparse()`
  - Verify scheme is `http` or `https`
  - Verify host is not empty
  - Reject private/internal IP ranges (`127.0.0.1`, `169.254.169.254`, `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x`, `localhost`)
- **ALWAYS** validate user-controlled path segments against a strict allowlist regex (e.g., `^[A-Za-z0-9_\-.:]{1,512}$`).
- **NEVER** concatenate raw user input into URL strings.
- **ALWAYS** set timeouts on HTTP clients.

### Correct Pattern

```python
from urllib.parse import urlparse

def validate_url(raw_url: str) -> str:
    """Validate and return a safe HTTP(S) URL."""
    parsed = urlparse(raw_url.rstrip("/"))
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("URL missing host")
    return parsed.geturl()
```

---

## 3. Input Validation

### Rules

- **ALWAYS** use Pydantic models for request validation — they enforce types, lengths, and constraints automatically.
- **ALWAYS** add `max_length`, `min_length`, `pattern` constraints on string fields from user input.
- **NEVER** trust client-supplied IDs without validating format (UUID, etc.).
- **ALWAYS** use `constr()`, `conint()`, or `Field()` validators for constrained inputs.

### Correct Pattern

```python
from pydantic import BaseModel, Field, constr

class CreateAgentRequest(BaseModel):
    name: constr(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9 _\-]+$")
    description: str = Field(default="", max_length=2000)
    tenant_id: str = Field(pattern=r"^[a-f0-9\-]{36}$")
```

---

## 4. Authentication & Authorization

### Rules

- **EVERY** endpoint (except health checks) MUST go through auth middleware.
- **ALWAYS** verify tenant membership before accessing tenant resources.
- **ALWAYS** check RBAC permissions via `check_permission()` — never manually compare roles.
- **NEVER** expose internal IDs in error messages to unauthenticated users.
- **NEVER** return different error messages for "not found" vs "not authorized" — always return 404 for both to prevent enumeration.

---

## 5. Secret Management

- **NEVER** hardcode secrets, API keys, or tokens in source code.
- **ALWAYS** use the vault abstraction (`core/vault/`) to retrieve secrets at runtime.
- **NEVER** log secrets — not even at debug level.
- **NEVER** return secrets in API responses — mask or omit sensitive fields.

---

## 6. Data Exposure Prevention

### Rules

- **ALWAYS** use separate response models (Pydantic) — never return ORM models directly.
- **NEVER** include sensitive fields (passwords, tokens, internal IDs) in response models.
- **ALWAYS** filter list queries by tenant membership — users only see resources they have access to.
- **NEVER** expose stack traces or internal error details in production responses.

---

## Quick Checklist Before Committing

- [ ] No raw string interpolation in SQL queries — all use ORM or bound params
- [ ] All outbound URLs validated (scheme, host, no internal IPs)
- [ ] All user input validated via Pydantic with constraints
- [ ] All endpoints have auth middleware
- [ ] All list queries filter by tenant membership
- [ ] No hardcoded secrets
- [ ] No sensitive data in API responses
- [ ] HTTP clients have timeouts
