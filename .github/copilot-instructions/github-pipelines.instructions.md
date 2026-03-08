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

The `name:` field inside each workflow uses the format `CI — Description` or `CD — Description`.

---

## Current Workflows

### ci-tests-and-lint.yml

**Name**: `CI — Tests & Lint`
**Triggers**: push to `main`/`develop`, pull_request, workflow_dispatch

| Job | What it does |
|-----|-------------|
| **lint** | `ruff check .` + `ruff format --check .` |
| **test** | `pytest -n auto --cov=unifiedui --cov-fail-under=80` with coverage artifact upload |

**Coverage threshold**: 80% enforced via `--cov-fail-under=80`. CI fails if coverage drops below.

### ci-pr-branch-check.yml

**Name**: `CI — PR Branch Check`
**Triggers**: pull_request (opened, synchronize, reopened, edited)

| Job | What it does |
|-----|-------------|
| **branch-naming** | Validates `<type>/` prefix convention (`feat/`, `fix/`, `docs/`, etc.) |
| **branch-target** | Enforces: `develop` or `hotfix/*` → `main`; typed branches → `develop` |

### codeql.yml

**Name**: `CodeQL Security Scan`
**Triggers**: push/PR to `main`/`develop`, weekly schedule (Monday 06:00 UTC)

Runs CodeQL analysis with `security-extended` and `security-and-quality` query suites.

### auto-labeler.yml

**Name**: `Auto Labeler`
**Triggers**: pull_request_target (opened, synchronize, reopened)

Labels PRs based on changed files using `.github/labeler.yml` config. Labels: `api`, `handlers`, `database`, `core`, `schema`, `tests`, `documentation`, `ci`, `docker`, `dependencies`.

### pr-size-labeler.yml

**Name**: `PR Size Labeler`
**Triggers**: pull_request_target (opened, synchronize, reopened)

Labels PRs by size: `size/XS` (≤10), `size/S` (≤100), `size/M` (≤500), `size/L` (≤1000), `size/XL` (>1000).

### release-drafter.yml

**Name**: `Release Drafter`
**Triggers**: push to `main`, workflow_dispatch

Auto-drafts GitHub releases using `.github/release-drafter.yml` config. Categorizes changes by labels (features, bug fixes, maintenance, documentation, security).

### stale.yml

**Name**: `Stale Issues`
**Triggers**: daily schedule (06:00 UTC), workflow_dispatch

Marks issues stale after 60 days, closes after 14 more. Marks PRs stale after 30 days, closes after 7 more. Exempts: `pinned`, `security`, `bug`, `enhancement`, `work-in-progress`.

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.github/dependabot.yml` | Weekly dependency updates (pip, github-actions, docker) |
| `.github/labeler.yml` | File-path-to-label mappings for auto-labeler |
| `.github/release-drafter.yml` | Release notes template and version resolver |
| `.github/CODEOWNERS` | Default reviewers for PRs |

---

## Adding a New Workflow

1. Choose the correct prefix (`ci-`, `cd-`)
2. Create `.github/workflows/{prefix}{descriptive-name}.yml`
3. Set `name:` to `CI — Description` or `CD — Description`
4. Add appropriate triggers (`on:`)
5. Update this instruction file

---

## Tool Versions

| Tool | Version | Config |
|------|---------|--------|
| Python | 3.13 | `pyproject.toml` |
| uv | latest | `astral-sh/setup-uv@v7` |
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
