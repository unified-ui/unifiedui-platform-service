# Tooling Guide — Platform Service

This document describes the development tooling, workflows, and quality gates for the unified-ui Platform Service.

## Prerequisites

| Tool | Version | Installation |
|------|---------|--------------|
| Python | 3.13+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| pre-commit | latest | `pip install pre-commit` |
| commitlint | latest | `npm install -g @commitlint/cli @commitlint/config-conventional` |
| Docker | latest | [docker.com](https://www.docker.com/) |

## Quick Commands

```bash
# Development
uv sync                                       # Install/update dependencies
uv sync --frozen                              # Install from lockfile (CI)
uv run uvicorn unifiedui.app:app --reload     # Start with hot reload

# Testing
pytest tests/ -n auto --no-header -q                              # Run all tests (parallel)
pytest tests/ -n auto --cov=unifiedui --cov-report=html           # With coverage
pytest tests/ -n auto --cov=unifiedui --cov-fail-under=80         # CI coverage gate

# Code Quality
ruff check .                                  # Lint
ruff format .                                 # Format
ruff check . && ruff format --check .         # CI check (lint + format verify)
mypy unifiedui/                               # Type check

# Database
alembic upgrade head                          # Apply migrations
alembic revision --autogenerate -m "desc"     # Create migration

# Docker
docker compose -f docker/local/infra/docker-compose.yml up -d    # Start infrastructure
docker compose -f docker/local/backend/docker-compose.yml up      # Local dev (Docker)
docker build -f docker/Dockerfile -t platform-service .           # Production build

# Pre-commit
pre-commit run --all-files                    # Run all hooks manually
```

## Pre-commit Hooks

Install hooks once per clone:

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

Hooks run automatically on `git commit`. Manual run:

```bash
pre-commit run --all-files
```

### Configured Hooks

| Hook | Source | Purpose |
|------|--------|---------|
| trailing-whitespace | pre-commit-hooks | Remove trailing whitespace |
| end-of-file-fixer | pre-commit-hooks | Ensure files end with newline |
| check-yaml | pre-commit-hooks | Validate YAML syntax |
| check-json | pre-commit-hooks | Validate JSON syntax |
| check-added-large-files | pre-commit-hooks | Prevent large files (>1MB) |
| check-merge-conflict | pre-commit-hooks | Detect merge conflict markers |
| detect-private-key | pre-commit-hooks | Prevent accidental key commits |
| ruff (lint) | ruff-pre-commit | Lint with auto-fix |
| ruff-format | ruff-pre-commit | Code formatting |
| commitizen | commitizen | Enforce Conventional Commits |

## Commit Convention

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Examples**:
```
feat(handlers): add chat agent cloning endpoint
fix(auth): handle expired refresh tokens
docs(api): update OpenAPI schema for credentials
chore(deps): update fastapi to 0.125.0
```

## Code Quality Gates

### Linting & Formatting (Ruff)

Configuration: `pyproject.toml` → `[tool.ruff]`

Enabled rules:
- `E` / `W` — pycodestyle (errors/warnings)
- `F` — pyflakes
- `I` — isort (import sorting)
- `N` — pep8-naming
- `UP` — pyupgrade
- `B` — flake8-bugbear
- `SIM` — flake8-simplify
- `TC` — flake8-type-checking
- `RUF` — ruff-specific rules

### Type Checking (mypy)

Recommended strict configuration:

```ini
[mypy]
python_version = 3.13
strict = true
ignore_missing_imports = true
```

### Testing

- Minimum coverage: **80%**
- Test location: `tests/` directory
- Naming: `test_{resource}[_rbac|_caching].py`
- Parallelization: `-n auto` (pytest-xdist)

## CI/CD Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| `ci-tests-and-lint.yml` | push/PR | Lint, format, tests with coverage ≥ 80% |
| `ci-pr-branch-check.yml` | PR | Branch naming + target validation |
| `codeql.yml` | push/PR/weekly | Security scanning |
| `auto-labeler.yml` | PR | Label PRs based on changed files |
| `pr-size-labeler.yml` | PR | Label PRs by size (XS/S/M/L/XL) |
| `release-drafter.yml` | push to main | Auto-draft GitHub releases |
| `stale.yml` | daily | Mark/close stale issues and PRs |

## Security

- **Dependabot** updates dependencies weekly (Mondays 09:00 CET)
- **CodeQL** scans for vulnerabilities on every push and weekly
- **Ruff** includes security rules via flake8-bugbear
- **pre-commit** hooks detect private keys and merge conflicts

## IDE Configuration

### VS Code

Recommended extensions:
- `ms-python.python`
- `charliermarsh.ruff`
- `EditorConfig.EditorConfig`

Settings (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "ruff.lint.args": ["--config=pyproject.toml"]
}
```

### PyCharm

- Enable Ruff plugin
- Set Python 3.13 interpreter from `.venv`
- Enable EditorConfig support
