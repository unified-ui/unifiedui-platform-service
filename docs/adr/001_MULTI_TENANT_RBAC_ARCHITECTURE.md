# ADR 001: Multi-Tenant RBAC Architecture

## Status

**Accepted** — 2025-12-07

## Context

unified-ui is a platform that manages AI agents across multiple teams and organizations. We need an access control model that:

- Isolates tenant data completely
- Supports fine-grained permissions per resource
- Scales to organizations with many tenants
- Allows both admin-level and resource-level access control

## Decision

We adopt a **two-layer RBAC model**:

### Layer 1: Tenant-Level Roles

Users are assigned roles at the tenant level that grant broad capabilities:

| Role | Scope |
|------|-------|
| `READER` | Minimal access — can view the tenant |
| `GLOBAL_ADMIN` | Full access to all tenant resources |
| `{RESOURCE}_ADMIN` | Full access to a specific resource type |
| `{RESOURCE}_CREATOR` | Can create new instances of a resource type |

### Layer 2: Resource-Level Permissions

Individual resources (Chat Agents, Credentials, etc.) have a **member table** that maps principals (users/groups) to permissions:

| Permission | Grants |
|------------|--------|
| `READ` | View / use the resource |
| `WRITE` | Modify the resource |
| `ADMIN` | Full control + manage permissions |

**Hierarchy**: `ADMIN` > `WRITE` > `READ` (higher includes lower).

### Permission Resolution

Every list operation joins the resource's member table and filters by the requesting user's principal IDs (user ID + group IDs). This ensures users **only see resources they have access to**.

The `PermissionResolver` centralizes role-to-capability mapping and is the single source of truth for "can this user do X?".

### Organization Layer

Organizations group multiple tenants. Organization-level roles (`ORG_OWNER`, `ORG_ADMIN`) can optionally bypass tenant-level restrictions for administrative purposes.

## Consequences

### Positive

- Complete tenant isolation — no accidental data leakage
- Fine-grained access control per resource
- Consistent pattern across all 16+ resource types
- Permission checks are composable (tenant role + resource permission)
- Scales to any number of tenants and resources

### Negative

- Every list query requires a JOIN with the member table (slight performance cost, mitigated by caching)
- Adding a new resource type requires creating a corresponding member model and migration
- Permission resolution logic is complex but centralized in `PermissionResolver`

## Alternatives Considered

1. **Simple role-based (no resource-level)** — Too coarse for multi-team environments
2. **ACL lists** — Too complex, hard to query efficiently with SQL
3. **Policy-based (OPA/Cedar)** — Overkill for current scale, adds infrastructure dependency
