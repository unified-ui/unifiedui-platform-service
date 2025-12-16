# AIHub RBAC (Role-Based Access Control) Konzept

## Überblick

Dieses Dokument beschreibt das RBAC-System für AIHub, das Permissions auf drei Ebenen unterstützt:
1. **User-Level**: Direkte Permissions für einzelne Benutzer
2. **Identity Groups**: Permissions über Identity Provider Groups (z.B. Microsoft Entra ID)
3. **Custom Groups**: AIHub-eigene Gruppen mit zugewiesenen Permissions

## Permission Format

### Pattern
```
<resource>:<action>
<resource>/{id}:<action>
<resource>/*:<action>
```

### Beispiele
- `applications:create` — Neue Applications erstellen
- `applications/*:*` — Voller Zugriff auf alle Applications
- `applications/abc123:read` — Lesen einer spezifischen Application
- `*:*` — Super-Admin (alle Ressourcen, alle Aktionen)

### Resource Types
- `applications` — Chat-Anwendungen
- `conversations` — Konversationen
- `autonom-agents` — Autonome Agents
- `custom-groups` — Custom Identity Groups
- `keystore-secrets` — Secrets/API Keys
- `widgets` — Custom Widgets

### Actions
- `create` — Ressource erstellen
- `read` — Ressource lesen
- `update` — Ressource aktualisieren
- `delete` — Ressource löschen
- `invoke` — Ressource aufrufen (z.B. Agent invoken)
- `*` — Alle Aktionen

## Data Models

### 1. Permissions Collection

Permissions werden als separate Dokumente gespeichert, die auf User, Identity Groups oder Custom Groups verweisen.

```json
{
  "_id": "perm_123",
  "tenant_id": "tenant_xyz",
  "permission": "applications/abc123:read",
  "resource_type": "applications",
  "resource_id": "abc123",
  "action": "read",
  "scope": "specific",
  
  "assigned_to": {
    "type": "custom_group",
    "id": "group_456"
  },
  
  "created_at": "2025-12-16T10:00:00Z",
  "created_by": "user_789",
  "updated_at": "2025-12-16T10:00:00Z",
  "updated_by": "user_789"
}
```

**Felder:**
- `permission`: Vollständiger Permission-String
- `resource_type`: Ressourcen-Typ für effizienten Index
- `resource_id`: Spezifische Resource ID (null bei `create` oder `*`)
- `action`: Die erlaubte Aktion
- `scope`: `global` (`*:*`), `resource_type` (`applications:create`), `resource_wildcard` (`applications/*:*`), `specific` (`applications/abc:read`)
- `assigned_to.type`: `user`, `identity_group`, `custom_group`
- `assigned_to.id`: ID des Benutzers oder der Gruppe

**Indexes:**
```javascript
// Compound index für schnelle Permission-Lookups
{ "tenant_id": 1, "assigned_to.type": 1, "assigned_to.id": 1 }

// Index für Resource-basierte Queries
{ "tenant_id": 1, "resource_type": 1, "resource_id": 1 }

// Index für Scope-Queries
{ "tenant_id": 1, "scope": 1, "resource_type": 1 }
```

### 2. Users Collection (Extended)

User-Dokumente speichern keine direkten Permissions, sondern nur Gruppenmitgliedschaften.

```json
{
  "_id": "user_123",
  "tenant_id": "tenant_xyz",
  "identity": {
    "provider": "entra_id",
    "provider_user_id": "entra_user_456",
    "email": "user@example.com",
    "name": "Max Mustermann"
  },
  
  "identity_groups": [
    "entra_group_789",
    "entra_group_012"
  ],
  
  "custom_groups": [
    "custom_group_345",
    "custom_group_678"
  ],
  
  "created_at": "2025-12-16T10:00:00Z",
  "updated_at": "2025-12-16T10:00:00Z"
}
```

### 3. Computed Permissions Cache Collection

**Performance-kritisch**: Pre-computed Permissions pro User für schnelle Authorisierung.

```json
{
  "_id": "cache_user_123",
  "tenant_id": "tenant_xyz",
  "user_id": "user_123",
  
  "permissions": [
    "applications:create",
    "applications/abc123:read",
    "applications/abc123:update",
    "conversations/*:*",
    "autonom-agents/xyz789:read"
  ],
  
  "resource_access": {
    "applications": {
      "global": false,
      "wildcard": false,
      "specific": ["abc123", "def456"]
    },
    "conversations": {
      "global": false,
      "wildcard": true,
      "specific": []
    },
    "autonom-agents": {
      "global": false,
      "wildcard": false,
      "specific": ["xyz789"]
    }
  },
  
  "computed_at": "2025-12-16T10:00:00Z",
  "expires_at": "2025-12-16T10:15:00Z"
}
```

**TTL Index:**
```javascript
{ "expires_at": 1 }, { expireAfterSeconds: 0 }
```

**Felder:**
- `permissions`: Flache Liste aller resolved Permissions
- `resource_access`: Strukturierte Darstellung für schnelle List-Filter
  - `global`: Hat User `*:*`?
  - `wildcard`: Hat User `resource/*:*`?
  - `specific`: Array von spezifischen Resource IDs

## Permission Resolution Algorithm

### Schritt 1: Cache Check
```python
def get_user_permissions(user_id: str, tenant_id: str) -> PermissionCache:
    # 1. Check Cache
    cache = db.permission_cache.find_one({
        "user_id": user_id,
        "tenant_id": tenant_id,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if cache:
        return cache
    
    # 2. Compute Permissions
    return compute_and_cache_permissions(user_id, tenant_id)
```

### Schritt 2: Permission Computation
```python
def compute_and_cache_permissions(user_id: str, tenant_id: str) -> PermissionCache:
    user = db.users.find_one({"_id": user_id, "tenant_id": tenant_id})
    
    # Sammle alle Gruppen-IDs
    all_groups = []
    
    # 1. Direct User Permissions
    all_groups.append({"type": "user", "id": user_id})
    
    # 2. Identity Group Permissions
    for group_id in user.get("identity_groups", []):
        all_groups.append({"type": "identity_group", "id": group_id})
    
    # 3. Custom Group Permissions
    for group_id in user.get("custom_groups", []):
        all_groups.append({"type": "custom_group", "id": group_id})
    
    # Query alle Permissions für diese Gruppen
    permissions = db.permissions.find({
        "tenant_id": tenant_id,
        "assigned_to": {"$in": all_groups}
    })
    
    # Compute permission structure
    permission_list = []
    resource_access = {}
    
    for perm in permissions:
        permission_list.append(perm["permission"])
        
        resource_type = perm["resource_type"]
        if resource_type not in resource_access:
            resource_access[resource_type] = {
                "global": False,
                "wildcard": False,
                "specific": []
            }
        
        # Check for global access (*:*)
        if perm["scope"] == "global":
            resource_access[resource_type]["global"] = True
        
        # Check for wildcard (applications/*:*)
        elif perm["scope"] == "resource_wildcard":
            resource_access[resource_type]["wildcard"] = True
        
        # Add specific resource IDs
        elif perm["scope"] == "specific" and perm["resource_id"]:
            if perm["resource_id"] not in resource_access[resource_type]["specific"]:
                resource_access[resource_type]["specific"].append(perm["resource_id"])
    
    # Cache für 15 Minuten
    cache_doc = {
        "_id": f"cache_{user_id}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "permissions": permission_list,
        "resource_access": resource_access,
        "computed_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(minutes=15)
    }
    
    db.permission_cache.replace_one(
        {"_id": cache_doc["_id"]},
        cache_doc,
        upsert=True
    )
    
    return cache_doc
```

## List Filtering Strategy

### Problem
Bei `GET /api/v1/applications/` muss die Query nur die Applications zurückgeben, auf die der User Zugriff hat.

### Lösung: MongoDB $in Query mit Pre-computed IDs

```python
def list_applications(user_id: str, tenant_id: str, filters: dict = None):
    # 1. Get user permissions from cache
    perm_cache = get_user_permissions(user_id, tenant_id)
    
    # 2. Check if user has global or wildcard access
    app_access = perm_cache["resource_access"].get("applications", {})
    
    if app_access.get("global"):
        # User has *:* - no filtering needed
        query = {"tenant_id": tenant_id}
    elif app_access.get("wildcard"):
        # User has applications/*:* - no filtering needed
        query = {"tenant_id": tenant_id}
    else:
        # User has only specific IDs
        accessible_ids = app_access.get("specific", [])
        if not accessible_ids:
            return []  # No access
        
        query = {
            "tenant_id": tenant_id,
            "_id": {"$in": accessible_ids}
        }
    
    # 3. Apply additional filters
    if filters:
        query.update(filters)
    
    # 4. Execute query
    return db.applications.find(query)
```

### Performance Characteristics

**Best Case (Wildcard/Global):**
- Single query: `db.applications.find({"tenant_id": "xyz"})`
- Index used: `tenant_id`
- Complexity: O(n) where n = total applications in tenant

**Specific Access:**
- Single query: `db.applications.find({"tenant_id": "xyz", "_id": {"$in": [...]}})`
- Index used: `_id` (compound with `tenant_id`)
- Complexity: O(k) where k = number of accessible IDs

**Cache Hit:**
- Permission resolution: O(1) (cached)
- No additional permission queries needed

**Cache Miss:**
- Permission resolution: O(m) where m = number of groups user belongs to
- One query to permissions collection
- One cache write

## Authorization Checks

### Single Resource Access Check

```python
def check_permission(
    user_id: str,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    action: str
) -> bool:
    perm_cache = get_user_permissions(user_id, tenant_id)
    
    # Check for exact match
    exact_perm = f"{resource_type}/{resource_id}:{action}"
    if exact_perm in perm_cache["permissions"]:
        return True
    
    # Check for wildcard action
    wildcard_action = f"{resource_type}/{resource_id}:*"
    if wildcard_action in perm_cache["permissions"]:
        return True
    
    # Check for resource wildcard
    resource_wildcard = f"{resource_type}/*:{action}"
    if resource_wildcard in perm_cache["permissions"]:
        return True
    
    resource_wildcard_all = f"{resource_type}/*:*"
    if resource_wildcard_all in perm_cache["permissions"]:
        return True
    
    # Check for global permission
    if "*:*" in perm_cache["permissions"]:
        return True
    
    return False
```

### FastAPI Dependency

```python
from fastapi import Depends, HTTPException, status
from functools import wraps

def require_permission(resource_type: str, action: str):
    """
    Decorator für FastAPI Routes, die spezifische Permissions prüfen.
    
    Usage:
        @router.get("/applications/{app_id}")
        @require_permission("applications", "read")
        async def get_application(app_id: str, request: Request):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = kwargs.get("request")
            user = request.state.user
            
            # Extract resource_id from path parameters
            resource_id = kwargs.get(f"{resource_type[:-1]}_id")  # e.g., app_id -> application_id
            
            if not check_permission(
                user_id=user.id,
                tenant_id=user.tenant_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {resource_type}/{resource_id}:{action}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

## Cache Invalidation Strategy

### Invalidation Triggers

1. **Permission Changes**
   - Permission hinzugefügt/entfernt
   - Gruppenmitgliedschaft geändert
   - Custom Group erstellt/gelöscht

2. **User Changes**
   - User zu Custom Group hinzugefügt/entfernt
   - Identity Groups aktualisiert (z.B. via Sync)

### Invalidation Implementation

```python
def invalidate_user_permission_cache(user_id: str, tenant_id: str):
    db.permission_cache.delete_one({
        "user_id": user_id,
        "tenant_id": tenant_id
    })

def invalidate_group_permission_cache(group_id: str, group_type: str, tenant_id: str):
    # Finde alle User, die zu dieser Gruppe gehören
    if group_type == "custom_group":
        users = db.users.find({
            "tenant_id": tenant_id,
            "custom_groups": group_id
        })
    else:  # identity_group
        users = db.users.find({
            "tenant_id": tenant_id,
            "identity_groups": group_id
        })
    
    # Invalidiere Cache für alle betroffenen User
    user_ids = [u["_id"] for u in users]
    db.permission_cache.delete_many({
        "user_id": {"$in": user_ids},
        "tenant_id": tenant_id
    })
```

### API Endpoints für Permission Management

```python
# After creating/updating/deleting permissions
@router.put("/api/v1/permissions/")
async def update_permissions(request: PermissionUpdateRequest):
    # Update permissions
    ...
    
    # Invalidate affected caches
    if request.assigned_to.type == "user":
        invalidate_user_permission_cache(request.assigned_to.id, request.tenant_id)
    else:
        invalidate_group_permission_cache(
            request.assigned_to.id,
            request.assigned_to.type,
            request.tenant_id
        )
```

## Performance Optimizations

### 1. Redis Cache Layer (Optional)

Für sehr hohe Last kann ein Redis-Cache vor MongoDB geschaltet werden:

```python
def get_user_permissions_with_redis(user_id: str, tenant_id: str) -> PermissionCache:
    cache_key = f"perm:{tenant_id}:{user_id}"
    
    # 1. Check Redis
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # 2. Check MongoDB
    mongo_cache = db.permission_cache.find_one({
        "user_id": user_id,
        "tenant_id": tenant_id,
        "expires_at": {"$gt": datetime.utcnow()}
    })
    
    if mongo_cache:
        redis_client.setex(cache_key, 300, json.dumps(mongo_cache))  # 5 min TTL
        return mongo_cache
    
    # 3. Compute and cache
    computed = compute_and_cache_permissions(user_id, tenant_id)
    redis_client.setex(cache_key, 300, json.dumps(computed))
    return computed
```

### 2. Background Permission Sync

Für Identity Groups kann ein Background Job regelmäßig die Gruppenmitgliedschaften synchronisieren:

```python
async def sync_identity_groups_background():
    """
    Läuft alle 5 Minuten und synchronisiert Identity Provider Groups.
    """
    while True:
        tenants = db.tenants.find({})
        
        for tenant in tenants:
            # Query Identity Provider API
            provider_groups = await get_identity_provider_groups(tenant)
            
            # Update users with new group memberships
            for user in db.users.find({"tenant_id": tenant["_id"]}):
                new_groups = get_user_groups_from_provider(user, provider_groups)
                
                if set(new_groups) != set(user.get("identity_groups", [])):
                    db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"identity_groups": new_groups}}
                    )
                    
                    # Invalidate permission cache
                    invalidate_user_permission_cache(user["_id"], tenant["_id"])
        
        await asyncio.sleep(300)  # 5 minutes
```

### 3. Batch Permission Checks

Für List-Operationen mit vielen Ressourcen:

```python
def batch_check_permissions(
    user_id: str,
    tenant_id: str,
    resource_type: str,
    resource_ids: List[str],
    action: str
) -> Dict[str, bool]:
    """
    Prüft Permissions für mehrere Resources auf einmal.
    Gibt ein Dictionary zurück: {resource_id: has_permission}
    """
    perm_cache = get_user_permissions(user_id, tenant_id)
    
    # Check for global/wildcard access
    if "*:*" in perm_cache["permissions"]:
        return {rid: True for rid in resource_ids}
    
    if f"{resource_type}/*:*" in perm_cache["permissions"]:
        return {rid: True for rid in resource_ids}
    
    if f"{resource_type}/*:{action}" in perm_cache["permissions"]:
        return {rid: True for rid in resource_ids}
    
    # Check specific permissions
    accessible = perm_cache["resource_access"].get(resource_type, {}).get("specific", [])
    return {rid: (rid in accessible) for rid in resource_ids}
```

## Security Considerations

### 1. Permission Inheritance

**Hierarchie:**
```
*:* (Super Admin)
  ↓
applications/*:* (All Applications)
  ↓
applications/abc:* (All Actions on Specific App)
  ↓
applications/abc:read (Specific Action)
```

Permission Checks sollten von spezifisch zu allgemein prüfen.

### 2. Deny Rules (Optional)

Für erweiterte Sicherheit können explizite Deny-Rules implementiert werden:

```json
{
  "_id": "deny_perm_123",
  "tenant_id": "tenant_xyz",
  "permission": "applications/sensitive_app:*",
  "effect": "deny",
  "assigned_to": {
    "type": "user",
    "id": "user_123"
  }
}
```

**Check Logic:**
1. Check Deny Rules first
2. If denied, return false
3. Check Allow Rules
4. If allowed, return true
5. Default: Deny

### 3. Audit Logging

Alle Permission-Changes und Access-Denials sollten geloggt werden:

```json
{
  "_id": "audit_123",
  "tenant_id": "tenant_xyz",
  "event_type": "permission_check",
  "result": "denied",
  "user_id": "user_123",
  "resource": "applications/abc:delete",
  "timestamp": "2025-12-16T10:00:00Z",
  "ip_address": "192.168.1.1"
}
```

## Migration Strategy

### Phase 1: Basic Implementation
- Permission Collection
- Basic Permission Resolution
- Cache in MongoDB

### Phase 2: Performance Optimization
- Redis Cache Layer
- Computed Permission Cache
- Batch Operations

### Phase 3: Advanced Features
- Deny Rules
- Time-based Permissions
- Conditional Permissions (IP-based, etc.)

## Zusammenfassung

**Vorteile dieses Ansatzes:**
✅ MongoDB-nativ (kein JOIN-Pattern erforderlich)
✅ Performant durch Caching (MongoDB + optional Redis)
✅ Skalierbar durch pre-computed Permissions
✅ Flexibel (User, Identity Groups, Custom Groups)
✅ Erweiterbar (Deny Rules, Audit Logging, etc.)
✅ List-Filtering durch $in mit spezifischen IDs

**Trade-offs:**
⚠️ Cache-Invalidation Complexity bei Group-Changes
⚠️ Speicher-Overhead durch Permission Cache Collection
⚠️ Eventual Consistency (TTL-basierter Cache)

**Empfehlung:**
Dieser Ansatz ist ideal für AIHub, da er MongoDB-Best-Practices folgt und durch Caching sehr performant ist. Die Cache-Invalidation ist beherrschbar, und die Erweiterbarkeit ermöglicht zukünftige Features wie Deny-Rules oder Time-based Permissions.
