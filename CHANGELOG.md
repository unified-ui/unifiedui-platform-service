# Changelog

All notable changes to the unified-ui Platform Service will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

### Added

- FastAPI application with full RBAC and multi-tenant architecture
- 16 resource entities: Tenants, Organizations, Chat Agents, Autonomous Agents, ReACT Agents, Credentials, Conversations, Chat Widgets, Tools, Tags, Custom Groups, Tenant AI Models, Principals, Recent Visits, User Favorites, Dashboard
- Permission-based access control with tenant-level roles and resource-level permissions
- 9 identity provider integrations (Microsoft Entra ID, Google OAuth, AWS Cognito, Okta, LDAP, Kerberos, SAML, Generic OIDC, Mock)
- Redis caching layer with per-resource invalidation
- Dual vault architecture (Azure Key Vault + HashiCorp Vault + dotenv fallback)
- Document database support (MongoDB / Azure Cosmos DB) for messages
- Global search across all resources
- Dashboard with resource statistics
- Comprehensive test suite (1900+ tests, 80%+ coverage)
- CI/CD pipelines (tests, lint, CodeQL, dependency review, auto-labeling)
- Pre-commit hooks (ruff, commitlint, security checks)
- Docker support for local development and production deployment
