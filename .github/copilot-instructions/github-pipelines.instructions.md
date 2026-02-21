---
applyTo: '.github/**'
---

# GitHub Pipelines — Platform Service

## Workflow Naming Convention

All workflow files follow a prefix-based naming convention:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `ci-` | Continuous Integration (lint, test, build) | `ci-tests-and-lint.yml` |
| `cd-` | Continuous Deployment (deploy to environments) | `cd-deploy-staging.yml` |
| `ci-int-tests-` | Integration test suites | `ci-int-tests-database.yml` |
| `ci-e2e-tests-` | End-to-end test suites | `ci-e2e-tests-api.yml` |

The `name:` field inside each workflow MUST match the filename (without `.yml`).

---

## Current Workflows

### ci-tests-and-lint.yml

**Triggers**: push, pull_request, workflow_dispatch

| Job | What it does |
|-----|-------------|
| **lint** | `ruff check .` + `ruff format --check .` |
| **test** | `pytest -n auto --cov=unifiedui --cov-fail-under=80` with coverage artifact upload |

**Coverage threshold**: 80% enforced via `--cov-fail-under=80`. CI fails if coverage drops below.

### ci-pr-branch-check.yml

**Triggers**: pull_request to `main`

Validates that PRs to `main` originate from a `release/*` branch.

---

## Adding a New Workflow

1. Choose the correct prefix (`ci-`, `cd-`, `ci-int-tests-`, `ci-e2e-tests-`)
2. Create `.github/workflows/{prefix}{descriptive-name}.yml`
3. Set `name:` to match filename without extension
4. Add appropriate triggers (`on:`)
5. Update this instruction file

---

## Tool Versions

| Tool | Version | Config |
|------|---------|--------|
| Python | 3.13 | `pyproject.toml` |
| uv | latest | `astral-sh/setup-uv@v4` |
| ruff | ≥0.15.2 | `[tool.ruff]` in `pyproject.toml` |
| pytest | ≥8.0 | `[tool.pytest.ini_options]` in `pyproject.toml` |
| pytest-xdist | ≥3.5 | `-n auto` for parallel tests |
| pytest-cov | ≥4.1 | `--cov-fail-under=80` |

---

## Coverage Policy

- **Minimum threshold**: 80% (enforced in CI)
- **Run locally**: `uv run pytest tests/ -n auto --cov=unifiedui --cov-report=term-missing`
- **HTML report**: Generated in `htmlcov/` (gitignored)
- Coverage artifacts are uploaded per CI run and retained for 7 days

---

## Secrets

No GitHub secrets are currently required. If adding Codecov integration later, set `CODECOV_TOKEN` as a repository secret. The CI workflows function without it.
