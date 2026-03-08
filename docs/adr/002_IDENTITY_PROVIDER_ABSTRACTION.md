# ADR 002: Identity Provider Abstraction

## Status

**Accepted** — 2025-12-07

## Context

unified-ui must support authentication across diverse enterprise environments. Different organizations use different identity providers:

- Microsoft Entra ID (Azure AD) — common in Microsoft-centric enterprises
- Google OAuth — common in Google Workspace organizations
- AWS Cognito — common in AWS-heavy environments
- Okta, LDAP, Kerberos, SAML — various enterprise standards
- Generic OIDC — catch-all for standard-compliant providers

We need an architecture that:

- Supports all providers without code duplication
- Makes adding new providers straightforward
- Keeps the auth middleware provider-agnostic
- Supports the OAuth 2.0 On-Behalf-Of (OBO) flow for downstream API calls

## Decision

We use the **Strategy Pattern** with a factory to abstract identity providers:

### Architecture

```
core/identity/
├── providers.py          # ABC: IdentityProvider interface
├── token_verifier.py     # ABC: TokenVerifier interface
├── users.py              # ContextIdentityUser model
├── obo_token_exchange.py # OBO flow abstraction
├── factory.py            # IdentityProviderFactory (creates provider by config)
└── enums.py              # IdentityProviderType enum

identity/
├── extra_id/             # Microsoft Entra ID implementation
│   ├── provider.py       # EntraIDProvider(IdentityProvider)
│   └── token.py          # EntraIDTokenVerifier(TokenVerifier)
├── google/               # Google OAuth implementation
├── aws_cognito/          # AWS Cognito implementation
├── okta/                 # Okta implementation
├── ldap/                 # LDAP implementation
├── kerberos/             # Kerberos implementation
├── saml/                 # SAML implementation
├── oidc/                 # Generic OIDC implementation
└── mock/                 # Mock provider for testing
```

### Key Interfaces

- **`IdentityProvider`** — Resolves user info, groups, and principals from the identity system
- **`TokenVerifier`** — Validates and decodes JWT tokens (JWKS-based)
- **`IdentityProviderFactory`** — Creates the correct provider based on `Settings.IDENTITY_PROVIDER`

### Auth Middleware

The auth middleware (`core/middleware/apis/v1/auth.py`) is provider-agnostic. It:

1. Extracts the Bearer token from the request
2. Delegates validation to the configured `TokenVerifier`
3. Resolves `ContextIdentityUser` via the `IdentityProvider`
4. Injects the user context into the request

## Consequences

### Positive

- Adding a new identity provider = one new directory with two files
- Auth middleware never changes when adding providers
- Mock provider enables full test isolation without external dependencies
- Configuration-driven — switch providers via environment variable

### Negative

- 9 provider implementations to maintain (though most are thin wrappers)
- `IdentityProviderFactory` at 635 lines is large (candidate for refactoring)
- Not all providers support all features equally (e.g., OBO flow is Entra ID-specific)

## Alternatives Considered

1. **Single provider (Entra ID only)** — Too limiting for a platform-agnostic product
2. **External auth gateway (Keycloak, Auth0)** — Adds infrastructure dependency, limits self-hosted flexibility
3. **Middleware per provider** — Would create code duplication in route decorators
