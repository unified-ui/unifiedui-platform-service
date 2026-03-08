# ADR 005: Caching Strategy

## Status

**Accepted** — 2025-12-07

## Context

The platform service handles frequent read operations for agent configurations, permissions, and tenant data. Performance is critical because:

- The Agent Service (Go) calls the Platform Service on every chat message for config & credential retrieval
- Permission resolution requires multiple DB queries (tenant roles + resource permissions + group memberships)
- Dashboard and search endpoints aggregate data across many tables

We need a caching strategy that:

- Reduces database load for hot paths
- Maintains data consistency after writes
- Is transparent to handler code
- Supports cache invalidation per resource

## Decision

We use **Redis** as the caching layer with a **cache-aside pattern** and **per-resource invalidation**.

### Architecture

```
core/caching/
├── cache.py       # ABC: BaseCache interface
├── client.py      # ABC: BaseCacheClient interface
└── collections/
    └── tenants.py # Tenant-scoped cache key builder

caching/
├── client.py      # CacheClient implementation
├── enums.py       # Cache key prefix enum
└── redis/
    ├── cache.py   # RedisCache(BaseCache)
    └── client.py  # RedisCacheClient
```

### Cache Key Structure

```
{prefix}:{tenant_id}:{resource_id}
{prefix}:{tenant_id}:list:{hash_of_params}
```

Prefixes are defined in `CacheKeyPrefix` enum (one per resource type).

### Invalidation Strategy

- **On write** (create/update/delete): Invalidate specific resource key + list cache for that resource type
- **On permission change**: Invalidate resource and related list caches
- **On tag change**: Invalidate resource and tag-related caches
- **TTL**: All cache entries have a configurable TTL (default: 5 minutes)

### Handler Integration

Handlers receive a `CacheClient` via dependency injection. Cache operations are explicit:

```python
# Read-through
cached = self.cache.get(key)
if cached:
    return cached
result = self.db.query(...)
self.cache.set(key, result, ttl=300)
return result

# Invalidate on write
self.db.add(resource)
self.cache.delete(key)
self.cache.delete_pattern(f"{prefix}:{tenant_id}:list:*")
```

## Consequences

### Positive

- Significant latency reduction for hot read paths
- Per-resource invalidation prevents stale data
- Redis is lightweight and widely available
- fakeredis enables full cache testing without Redis running
- Cache logic is explicit — no magic decorators

### Negative

- Cache invalidation complexity grows with cross-resource dependencies
- List cache invalidation uses pattern-based deletion (potential for over-invalidation)
- Every handler must manually manage cache (no automatic cache layer)
- Testing requires 3 test variants per resource: CRUD, RBAC, Caching

## Alternatives Considered

1. **No caching** — Unacceptable latency for Agent Service config lookups
2. **In-memory cache (functools.lru_cache)** — Doesn't work across multiple workers/pods
3. **Automatic ORM-level caching** — Too opaque, hard to control invalidation
4. **CDN/API gateway caching** — Doesn't help for authenticated, tenant-scoped data
