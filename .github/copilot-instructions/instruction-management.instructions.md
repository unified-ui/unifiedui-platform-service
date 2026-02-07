# Instruction Management

## When to Update Instructions

### Update docs when:
- **New resource entity added** → Update `project-structure`, `api-routes`, `handlers`, `database`, `testing`
- **New auth pattern or decorator** → Update `auth-permissions.instructions.md`
- **New infrastructure component** → Update `infrastructure.instructions.md`
- **New test pattern established** → Update `testing.instructions.md`
- **Folder structure changed** → Update `project-structure.instructions.md`
- **New central handler** (like ResourcePermissionsHandler) → Update `handlers.instructions.md`
- **New enum added to enums.py** → Update `database.instructions.md`

### Never update docs for:
- Bug fixes
- Simple field additions or removals
- One-off endpoint-specific logic
- Refactoring that doesn't change patterns
- Test additions following existing patterns

---

## Review Checklist

After completing work, ask:

1. Did I create a new **reusable pattern** that others should follow? → Document it.
2. Did I add a new **resource entity**? → Update all relevant files.
3. Did I change **how auth/permissions work**? → Update auth-permissions.
4. Did I add new **infrastructure** (new cache strategy, new vault type)? → Update infrastructure.
5. Did I establish a new **test pattern** different from the three-file pattern? → Update testing.

---

## File Responsibilities

| File | Documents |
|------|-----------|
| `copilot-instructions.md` | Project overview, golden rules, naming, quick reference |
| `project-structure.instructions.md` | Folder tree, core vs impl, dependencies, adding new entities |
| `api-routes.instructions.md` | Route patterns, decorators, URL conventions, exception mapping |
| `handlers.instructions.md` | Handler patterns, central handlers, validators, cache invalidation |
| `database.instructions.md` | Models, enums, mixins, resource table, member table pattern |
| `auth-permissions.instructions.md` | Three decorators, permission flow, role hierarchy, service keys |
| `infrastructure.instructions.md` | Cache, vault, identity, document DB, config |
| `testing.instructions.md` | Three-file pattern, fixtures, RBAC tests, caching tests, running tests |

---

## Editing Rules

- Keep instruction files **concise and pattern-focused**
- Use code examples that match actual codebase patterns
- Include the "WHY" only when the pattern is non-obvious
- Cross-reference other instruction files via relative links
- Keep each file under 300 lines if possible
