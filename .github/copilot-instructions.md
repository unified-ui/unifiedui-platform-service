---
applyTo: '**'
---

# unified-ui Platform Service — Copilot Instructions

## Project Overview

**unified-ui** is a multi-tenant integration platform for AI agent systems with role-based access control (RBAC). This platform service is the core backend providing management APIs for organizations, tenants, chat agents, autonomous agents, ReACT agents (a ChatAgent sub-type), conversations, credentials, chat widgets, tools, tags, permissions, tenant AI models, recent visits, dashboard, and global search.

**Tech Stack**: Python 3.13+ · FastAPI · SQLAlchemy · PostgreSQL · Redis · HashiCorp Vault / Azure Key Vault · MSAL · Pydantic v2 · Alembic

---

## Instruction Files Index

Read the relevant instruction file **before** working in that area.

| File | Read when... |
|------|-------------|
| [project-structure.instructions.md](./instructions/project-structure.instructions.md) | Understanding folder layout, adding new modules, modifying structure |
| [api-routes.instructions.md](./instructions/api-routes.instructions.md) | Adding or modifying API routes in `apis/v1/` |
| [handlers.instructions.md](./instructions/handlers.instructions.md) | Implementing business logic in `handlers/` |
| [database.instructions.md](./instructions/database.instructions.md) | Working with models, enums, migrations, or queries |
| [auth-permissions.instructions.md](./instructions/auth-permissions.instructions.md) | Touching auth middleware, RBAC, permission checks, or tenant access |
| [infrastructure.instructions.md](./instructions/infrastructure.instructions.md) | Working with caching, vault, identity providers, or document DB |
| [security.instructions.md](./instructions/security.instructions.md) | **ALWAYS read** — SQL injection, SSRF, input validation, auth, secrets |
| [testing.instructions.md](./instructions/testing.instructions.md) | Writing tests, running tests, or understanding test patterns |
| [github-pipelines.instructions.md](./instructions/github-pipelines.instructions.md) | Working with CI/CD workflows, adding pipelines, coverage thresholds |
| [instruction-management.instructions.md](./instructions/instruction-management.instructions.md) | After completing work — decides if/how to update docs |

---

## Golden Rules

1. **No comments in code** — Comments only for class docstrings and function docstrings (those are **mandatory**). No inline comments, no block comments explaining logic. Code must be self-documenting.
2. **ALL business logic in handlers** — Routes (`apis/v1/`) are thin wrappers. Zero logic, zero data transformation. Only: accept params → call handler → return response.
3. **Factory pattern for infrastructure** — All infrastructure components (database, cache, vault, identity) use factory pattern with interface in `core/` and implementation outside.
4. **Type annotations everywhere** — ALL function signatures must have annotations on every parameter and return type, no exceptions (public, private, nested). No `Any` unless absolutely unavoidable. No `# type: ignore` without a specific error code (e.g. `# type: ignore[override]`). Run `uv run mypy unifiedui/` to verify — **zero errors required**.
5. **Pydantic for all schemas** — Separate request and response models. Never return raw dicts from handlers.
6. **Permission filtering on every list** — List operations MUST join `{resource}_members` and filter by user's principal_id. Users only see what they have access to.
7. **Dependency injection** — Never instantiate DB/cache/vault clients in handlers. Always inject via `Depends()` or constructor.
8. **Keep files under 400 lines** — Split large handlers into helper methods or separate sub-handlers.
9. **Custom exceptions** — Use typed exceptions from `exc/` for every error case. Never raise generic `Exception`.
10. **Run tests and lint after changes** — After significant changes or when asked to test, run: `pytest tests/ -n auto --no-header -q`. Always run tests in parallel (`-n auto`) since there are many tests. Run `ruff check . && ruff format --check .` to verify linting passes.
11. **Run pre-commit after EVERY task** — After completing any task (including intermediate sub-tasks), ALWAYS run `pre-commit run --all-files` and fix any failures before reporting completion. This is mandatory — never skip this step, even for small changes. Pre-commit must pass before any task is considered done.

---

## Naming Conventions

| What | Pattern | Example |
|------|---------|---------|
| Route file | `{resource}.py` in `apis/v1/` | `chat_agents.py` |
| Handler file | `{resource}.py` in `handlers/` | `chat_agents.py` |
| Schema (request) | `{Resource}Request` in `schema/requests/` | `CreateChatAgentRequest` |
| Schema (response) | `{Resource}Response` in `schema/responses/` | `ChatAgentResponse` |
| DB model | `{Resource}` in `core/database/models.py` | `ChatAgent` |
| Member model | `{Resource}Member` | `ChatAgentMember` |
| Exception | `{Resource}{Error}Error` in `exc/` | `ChatAgentNotFoundError` |
| Handler class | `{Resource}Handler` | `ChatAgentHandler` |
| Dependency | `get_{resource}_handler` in `handlers/dependencies/` | `get_chat_agent_handler` |
| Validator | `{Resource}ConfigValidatorFactory` in `handlers/validators/` | `ChatAgentConfigValidatorFactory` |
| Enum | `{Name}Enum` in `core/database/enums.py` | `PermissionActionEnum` |
| Test file (CRUD) | `test_{resource}.py` | `test_chat_agents.py` |
| Test file (RBAC) | `test_{resource}_rbac.py` | `test_chat_agents_rbac.py` |
| Test file (Cache) | `test_{resource}_caching.py` | `test_chat_agents_caching.py` |

---

## Quick Reference

- **Dev server**: `uvicorn unifiedui.app:app --reload`
- **Run tests**: `pytest tests/ -n auto --no-header -q`
- **Run tests with coverage**: `pytest tests/ -n auto --cov=unifiedui --cov-report=html`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Lint + Format check (CI)**: `ruff check . && ruff format --check .`
- **Pre-commit**: `pre-commit run --all-files`
- **Type check**: `mypy unifiedui/`
- **Migrations**: `alembic upgrade head` / `alembic revision --autogenerate -m "description"`
- **Entry point**: `unifiedui/app.py` → `create_app()`
- **Config**: `unifiedui/core/config.py` → `Settings` (Pydantic-Settings, env vars)
- **Models**: `unifiedui/core/database/models.py` (~1009 lines, includes RecentVisit, ReActAgentVersion, UserFavorites for 5 resource types, Organization + OrganizationMember)
- **Enums**: `unifiedui/core/database/enums.py` (includes `TenantRolesEnum`, `OrganizationRoleEnum`, `EnvironmentTypeEnum`, `ChatAgentTypeEnum` with `REACT_AGENT`)
- **Auth middleware**: `unifiedui/core/middleware/apis/v1/auth.py` (4 decorators: `authenticate`, `authenticate_service_key`, `authenticate_autonomous_agent_api_key`, `check_permissions`)
- **Key root files**: `CONTRIBUTING.md`, `SECURITY.md`, `SPONSORS.md`, `CHANGELOG.md`
- **Docs**: `docs/` with ADRs in `docs/adr/`

---

## Debug Backdoor (REQ 007)

This service implements the platform-side debug backdoor used by Copilot for self-testing. See [unifiedui/.github/copilot-instructions.md](https://github.com/unified-ui/unifiedui/blob/main/.github/copilot-instructions.md) for the cross-service contract.

| File | Role |
|------|------|
| `unifiedui/core/middleware/apis/v1/debug_backdoor.py` | Header constants, `build_backdoor_token()` (synthesises `MockIdentityToken`), structured-log helper |
| `unifiedui/core/middleware/apis/v1/auth.py` | `@authenticate()` decorator checks `is_backdoor_enabled() and has_backdoor_headers(request)` BEFORE Bearer extraction |
| `unifiedui/apis/v1/auth.py` | `POST /api/v1/platform-service/auth/debug-backdoor` issues a usable JWT for sessionless tools / the frontend's debug login button |
| `unifiedui/apis/v1/health.py` | `GET /healthcheck` exposes `debug_backdoor_enabled: bool` |
| `unifiedui/app.py` | `_emit_debug_backdoor_banner()` + 30 s reminder ticker on startup |
| `unifiedui/core/config.py` | `enable_debug_back_door`, `debug_back_door_secret`; production validator forbids enabling in `DEPLOYMENT_MODE=production` and requires secret ≥ 32 chars + `allow_mock_identity_provider=True` |

**Tests**: `tests/unit/core/middleware/test_debug_backdoor.py` (14 tests covering settings validation, healthcheck flag, end-to-end protected endpoint, login endpoint).

**Synthetic token** flows through the normal `MockIdentityToken` → `IdentityTokenFactory` → `ContextIdentityUser` pipeline → all RBAC checks fire unchanged.

## Microsoft Foundry — Copilot Reference Project

`.env` carries `FOUNDRY_PROJECT_API_KEY`, `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_PROJECT_OPENAI_ENDPOINT`, `FOUNDRY_DEFAULT_MODEL`. They are NOT consumed by the service. They exist so Copilot can iterate on prompts via `unifiedui/scripts/debug/foundry_smoke.py`.

```bash
set -a && source .env && set +a
cd ../unifiedui/scripts/debug
uv run --with httpx python -i foundry_smoke.py
>>> ping("gpt-4.1")
>>> ask("gpt-4.1", "Refactor this prompt for clarity: ...")
```

API-key path supports prompt iteration only. Foundry agent CRUD requires AAD identity in the Foundry tenant — out of scope for Copilot unless the user grants explicit `az login` access.

**Naming**: any Foundry resource Copilot creates MUST be prefixed `co-debug-`. Never touch resources without that prefix.

---

## Comment Policy (CRITICAL)

### Mandatory docstrings:
```python
class ChatAgentHandler:
    """Handler class for chat agent business logic."""

    def create_chat_agent(
        self,
        tenant_id: str,
        request: CreateChatAgentRequest,
        user_id: str,
        user: ContextIdentityUser
    ) -> ChatAgentResponse:
        """Create a new chat agent with the given configuration.

        Args:
            tenant_id: Tenant ID for scoping
            request: Chat agent creation request data
            user_id: ID of the creating user
            user: Authenticated user context

        Returns:
            Created chat agent response
        """
```

### Forbidden:
```python
# Don't do this
result = handler.create(data)  # Create the thing
# Also don't do this
# Check if the user has permissions before proceeding
if user.has_permission(...):
```

---

## Instruction Management (Summary)

After completing work, evaluate whether documentation needs updating. Full rules in [instruction-management.instructions.md](./instructions/instruction-management.instructions.md).

**Update docs when:**
- New resource entity added → update `project-structure`, `api-routes`, `handlers`, `database`, `testing`
- New auth pattern → update `auth-permissions.instructions.md`
- New infrastructure component → update `infrastructure.instructions.md`
- New test pattern → update `testing.instructions.md`
- **New tenant role added** → update `core/database/enums.py`, create Alembic migration, update `permission_resolver.py` if needed, update `auth-permissions.instructions.md`, and notify frontend-service to update `usePermissions.ts`, `api/types.ts`, and `ui-patterns.instructions.md`

**Never update docs for:** bug fixes, simple field changes, one-off endpoint tweaks.
