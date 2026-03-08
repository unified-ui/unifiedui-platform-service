# Organization + Tenant Konzept

> **Status:** Draft
> **Erstellt:** 21. Februar 2026
> **Autor:** Copilot + Enrico

---

## Inhaltsverzeichnis

1. [Executive Summary](#1-executive-summary)
2. [Ist-Analyse](#2-ist-analyse)
3. [Anforderungen](#3-anforderungen)
4. [Konzept-Übersicht](#4-konzept-übersicht)
5. [Datenmodell](#5-datenmodell)
6. [Identity Provider Integration](#6-identity-provider-integration)
7. [Login & Onboarding Flow](#7-login--onboarding-flow)
8. [Rollen & Berechtigungen](#8-rollen--berechtigungen)
9. [API Design](#9-api-design)
10. [Environment Promotion (Future)](#10-environment-promotion-future)
11. [SaaS vs Self-Hosted Unterschiede](#11-saas-vs-self-hosted-unterschiede)
12. [Migration](#12-migration)
13. [Offene Fragen](#13-offene-fragen)

---

## 1. Executive Summary

Dieses Konzept führt eine **Organization**-Schicht ein, die zwischen Identity Provider und Tenants steht. Eine Organization repräsentiert eine Firma/Kunde und gruppiert mehrere Tenants (= Environments/Projekte wie dev/test/prod). Dies ermöglicht:

- **Self-Hosted:** Eine Firma deployed unified-ui, hat eine Organization mit mehreren Tenants (Environments)
- **SaaS:** Jeder Kunde = eine Organization mit eigenen Tenants
- **Identity Provider Agnostisch:** Funktioniert mit Entra ID, Google, AWS Cognito, LDAP, etc.

**Kernprinzip:** Ein Identity Provider Tenant (z.B. Entra ID Tenant) ist immer genau einer Organization zugeordnet.

---

## 2. Ist-Analyse

### 2.1 Aktueller Datenfluss

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AKTUELLER ZUSTAND                                │
└─────────────────────────────────────────────────────────────────────────┘

1. User öffnet Frontend
   │
   ▼
2. MSAL Login (Entra ID) → Token
   │
   ▼
3. API Call mit Bearer Token
   │
   ▼
4. IdentityTokenFactory.create(token)
   ├── Erkennt Issuer (https://sts.windows.net/...)
   └── Erstellt ExtraIDIdentityTokenSerializer
   │
   ▼
5. ContextIdentityUser wird erstellt
   ├── identity: Token-Daten (id, name, mail, tid)
   ├── idp: ExtraIDIdentityProvider (für Graph API Calls)
   └── groups: Fetched von IDP + Custom Groups aus DB
   │
   ▼
6. GET /api/v1/identity/me
   └── Gibt zurück: user info + tenants mit roles
   │
   ▼
7. Wenn keine Tenants → User kann neuen Tenant erstellen
   └── Wird automatisch GLOBAL_ADMIN

```

### 2.2 Aktuelle Datenbank-Struktur (vereinfacht)

```
┌──────────────┐       ┌────────────────────┐       ┌─────────────────┐
│   Tenant     │──1:N──│   TenantMember     │──N:1──│    Principal    │
├──────────────┤       ├────────────────────┤       ├─────────────────┤
│ id           │       │ id                 │       │ tenant_id (PK)  │
│ name         │       │ tenant_id (FK)     │       │ principal_id(PK)│
│ description  │       │ principal_id       │       │ principal_type  │
│ created_at   │       │ role               │       │ display_name    │
│ updated_at   │       │ created_at         │       │ mail            │
│ created_by   │       │ updated_at         │       │ ...             │
│ updated_by   │       └────────────────────┘       └─────────────────┘
└──────────────┘

TenantRolesEnum:
- READER
- GLOBAL_ADMIN
- CHAT_AGENTS_ADMIN / CREATOR
- CREDENTIALS_ADMIN / CREATOR
- AUTONOMOUS_AGENTS_ADMIN / CREATOR
- ... (weitere resource-spezifische Rollen)
```

### 2.3 Identity Provider Integration

**Aktuell unterstützt:**
- Microsoft Entra ID (primär)
- Mock Provider (Tests)

**Geplant:**
- Google Identity
- AWS Cognito
- LDAP/Active Directory
- Atlassian
- Keycloak
- Custom OAuth2/OIDC

**Wichtige Token-Claims (Entra ID Beispiel):**
```json
{
  "iss": "https://sts.windows.net/{tenant-id}/",
  "oid": "user-object-id",      // User ID
  "tid": "entra-tenant-id",     // Identity Provider Tenant ID
  "name": "Max Mustermann",
  "mail": "max@company.com",
  "upn": "max@company.com"
}
```

### 2.4 Probleme im aktuellen System

1. **Kein Konzept für "Firma/Organization"** - Tenants sind flach, keine Hierarchie
2. **Kein Environment-Konzept** - dev/test/prod nicht unterscheidbar
3. **Kein zentraler Admin** - Wer darf neue Tenants erstellen?
4. **Self-Hosted Bootstrap** - Wie wird der erste Admin definiert?
5. **Multi-IDP Support** - Wie können mehrere IDPs einer Org zugeordnet werden?

---

## 3. Anforderungen

### 3.1 Funktionale Anforderungen

| ID | Anforderung | Priorität |
|----|-------------|-----------|
| F1 | Eine Organization pro Identity Provider Tenant | Must |
| F2 | Tenants sind Environments innerhalb einer Organization | Must |
| F3 | Environments: Sandbox (dev/test) und Production | Must |
| F4 | Org-Admins können Tenants erstellen/löschen | Must |
| F5 | Org-Admins können User zur Organization einladen/berechtigen | Must |
| F6 | Jeder User kann sich anmelden, aber ohne Org-Zugriff sieht er nichts | Must |
| F7 | Self-Hosted: Initial-Admin via Environment Variable | Must |
| F8 | SaaS: Organization-Beantragung (später) | Could |
| F9 | Environment Promotion (Agent von Dev → Prod kopieren) | Should (später) |
| F10 | Billing auf Organization-Ebene | Should |

### 3.2 Nicht-funktionale Anforderungen

| ID | Anforderung |
|----|-------------|
| NF1 | Identity Provider agnostisch (Entra, Google, LDAP, etc.) |
| NF2 | Keine Änderung der Frontend-Auth-Logik (MSAL bleibt) |
| NF3 | Bestehende Tenant-Berechtigungen bleiben erhalten (Migration) |
| NF4 | Performance: Max. 2 DB-Queries für Auth-Check |

---

## 4. Konzept-Übersicht

### 4.1 Neue Hierarchie

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NEUES MODELL                                  │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────┐
                    │     Identity Provider       │
                    │  (Entra ID, Google, LDAP)   │
                    │         tid: ABC-123        │
                    └─────────────┬───────────────┘
                                  │
                                  │ 1:1 Mapping
                                  ▼
                    ┌─────────────────────────────┐
                    │       Organization          │
                    │     "ACME Corporation"      │
                    │   identity_tenant_id: ABC-123│
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │  Tenant   │ │  Tenant   │ │  Tenant   │
            │   "Dev"   │ │  "Test"   │ │  "Prod"   │
            │  SANDBOX  │ │  SANDBOX  │ │ PRODUCTION│
            └───────────┘ └───────────┘ └───────────┘
```

### 4.2 Kernkonzepte

**Organization:**
- Repräsentiert eine Firma/Kunde
- Ist 1:1 mit einem Identity Provider Tenant verknüpft
- Hat eigene Settings (Billing, Limits, etc.)
- Enthält mehrere Tenants

**Tenant (Environment):**
- Gehört zu genau einer Organization
- Hat einen Typ: `SANDBOX` oder `PRODUCTION`
- Kann optional eine `previous_stage` haben (für Promotion)
- Alle bestehenden Ressourcen (Agents, Credentials, etc.) bleiben Tenant-scoped

**OrganizationMember:**
- Verknüpft User/Groups mit Organization
- Definiert Org-Level Rollen (ORG_ADMIN, ORG_MEMBER)

**TenantMember (bestehend):**
- Bleibt unverändert für Tenant-Level Berechtigungen
- User müssen Org-Zugriff UND Tenant-Zugriff haben

---

## 5. Datenmodell

### 5.1 Neue Entities

```sql
-- Neue Tabelle: Organization
CREATE TABLE organizations (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,          -- URL-freundlicher Name
    description VARCHAR(2000),

    -- Identity Provider Mapping
    identity_provider VARCHAR(50) NOT NULL,     -- ENTRA_ID, GOOGLE, LDAP, etc.
    identity_tenant_id VARCHAR(255) NOT NULL,   -- z.B. Entra Tenant ID

    -- Settings
    subscription_tier VARCHAR(50) DEFAULT 'free',  -- free, pro, enterprise
    max_tenants INTEGER DEFAULT 5,
    max_users INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,

    -- Audit
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50),

    -- Constraint: Ein IDP Tenant = Eine Organization
    CONSTRAINT uq_org_idp UNIQUE (identity_provider, identity_tenant_id)
);

-- Neue Tabelle: OrganizationMember
CREATE TABLE organization_members (
    id VARCHAR(36) PRIMARY KEY,
    organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    principal_id VARCHAR(50) NOT NULL,          -- User ID oder Group ID
    principal_type VARCHAR(20) NOT NULL,        -- IDENTITY_USER, IDENTITY_GROUP
    role VARCHAR(50) NOT NULL,                  -- ORG_ADMIN, ORG_MEMBER, ORG_READER

    -- Audit
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(50),
    updated_by VARCHAR(50),

    CONSTRAINT uq_org_member UNIQUE (organization_id, principal_id, role)
);

-- Erweiterung: Tenant
ALTER TABLE tenants ADD COLUMN organization_id VARCHAR(36) REFERENCES organizations(id);
ALTER TABLE tenants ADD COLUMN environment_type VARCHAR(20) DEFAULT 'SANDBOX';  -- SANDBOX, PRODUCTION
ALTER TABLE tenants ADD COLUMN previous_stage_id VARCHAR(36) REFERENCES tenants(id);  -- Für Promotion
ALTER TABLE tenants ADD COLUMN is_default BOOLEAN DEFAULT FALSE;  -- Default Tenant der Org
```

### 5.2 Neue Enums

```python
# In enums.py

class OrganizationRoleEnum(StrEnum):
    """Organization-level roles."""
    ORG_ADMIN = "ORG_ADMIN"           # Voller Zugriff auf Org + alle Tenants
    ORG_MEMBER = "ORG_MEMBER"         # Kann auf zugewiesene Tenants zugreifen
    ORG_READER = "ORG_READER"         # Nur Lesen auf Org-Ebene

    @classmethod
    def all(cls) -> list[str]:
        return [role.value for role in OrganizationRoleEnum]


class EnvironmentTypeEnum(StrEnum):
    """Tenant environment types."""
    SANDBOX = "SANDBOX"      # Dev/Test - weniger Restrictions
    PRODUCTION = "PRODUCTION"  # Prod - strikte Validierung

    @classmethod
    def all(cls) -> list[str]:
        return [env.value for env in EnvironmentTypeEnum]


class IdentityProviderTypeEnum(StrEnum):
    """Supported identity providers."""
    ENTRA_ID = "ENTRA_ID"
    GOOGLE = "GOOGLE"
    AWS_COGNITO = "AWS_COGNITO"
    LDAP = "LDAP"
    KEYCLOAK = "KEYCLOAK"
    ATLASSIAN = "ATLASSIAN"
    CUSTOM_OIDC = "CUSTOM_OIDC"

    @classmethod
    def all(cls) -> list[str]:
        return [provider.value for provider in IdentityProviderTypeEnum]
```

### 5.3 SQLAlchemy Models

```python
# In models.py

class Organization(Base, IdMixin, AuditMixin):
    """Organization entity representing a company/customer."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))

    # Identity Provider Mapping
    identity_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    identity_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Settings
    subscription_tier: Mapped[str] = mapped_column(String(50), default="free")
    max_tenants: Mapped[int] = mapped_column(Integer, default=5)
    max_users: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )
    tenants: Mapped[list["Tenant"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("identity_provider", "identity_tenant_id", name="uq_org_idp"),
        Index("ix_org_slug", "slug"),
    )


class OrganizationMember(Base, IdMixin, AuditMixin):
    """Organization membership and roles."""

    __tablename__ = "organization_members"

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    principal_id: Mapped[str] = mapped_column(String(50), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(20), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("organization_id", "principal_id", "role", name="uq_org_member"),
        Index("ix_org_member_principal", "principal_id"),
    )


# Erweiterung Tenant (bestehend)
class Tenant(Base, IdNameDescriptionMixin):
    __tablename__ = "tenants"

    # NEU: Organization reference
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True  # Nullable für Migration
    )

    # NEU: Environment type
    environment_type: Mapped[str] = mapped_column(String(20), default="SANDBOX")

    # NEU: Previous stage for promotion
    previous_stage_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True
    )

    # NEU: Default tenant flag
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="tenants")
    members: Mapped[list["TenantMember"]] = relationship(...)  # Bestehend
```

### 5.4 Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENTITY RELATIONSHIPS                           │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   Organization   │
├──────────────────┤
│ id (PK)          │
│ name             │
│ slug (unique)    │
│ identity_provider│◄────┐
│ identity_tenant_id     │  Unique Constraint:
│ subscription_tier│     │  (identity_provider, identity_tenant_id)
│ max_tenants      │     │
│ max_users        │     │
│ is_active        │─────┘
└────────┬─────────┘
         │
         │ 1:N
         ▼
┌──────────────────┐              ┌────────────────────┐
│ OrganizationMember│              │       Tenant       │
├──────────────────┤              ├────────────────────┤
│ id (PK)          │              │ id (PK)            │
│ organization_id  │◄─────1:N────►│ organization_id(FK)│
│ principal_id     │              │ name               │
│ principal_type   │              │ environment_type   │
│ role             │              │ previous_stage_id  │
└──────────────────┘              │ is_default         │
                                  └─────────┬──────────┘
                                            │
                                            │ 1:N (bestehend)
                                            ▼
                                  ┌────────────────────┐
                                  │    TenantMember    │
                                  ├────────────────────┤
                                  │ id (PK)            │
                                  │ tenant_id (FK)     │
                                  │ principal_id       │
                                  │ role               │
                                  └────────────────────┘
```

---

## 6. Identity Provider Integration

### 6.1 Generisches Mapping

Das System muss verschiedene Identity Provider unterstützen. Die Kernidee: **Jeder IDP liefert eine eindeutige Tenant-ID**, die zur Organization gemappt wird.

| Identity Provider | Tenant ID Quelle | User ID Quelle |
|-------------------|------------------|----------------|
| Entra ID | `tid` Claim | `oid` Claim |
| Google Workspace | `hd` (hosted domain) | `sub` Claim |
| AWS Cognito | User Pool ID | `sub` Claim |
| LDAP/AD | DN des Base-Containers | `uid` oder `sAMAccountName` |
| Keycloak | Realm Name | `sub` Claim |
| Atlassian | Cloud ID | Account ID |
| Custom OIDC | Configurable Claim | `sub` Claim |

### 6.2 Token-Verarbeitung (generisch)

```python
class BaseIdentityToken(ABC):
    """Abstrahiert die IDP-spezifischen Token-Details."""

    @abstractmethod
    def get_id(self) -> str:
        """User-eindeutige ID."""
        pass

    @abstractmethod
    def get_identity_tenant_id(self) -> str:
        """IDP-Tenant-eindeutige ID → wird zu Organization gemappt."""
        pass

    @abstractmethod
    def get_identity_provider(self) -> str:
        """IDP-Typ (ENTRA_ID, GOOGLE, etc.)."""
        pass

    # Weitere Methoden (name, mail, etc.)
```

### 6.3 Organization Lookup Flow

```
1. User Token kommt rein
2. IdentityTokenFactory.create(token) → BaseIdentityToken
3. Token liefert:
   - identity_provider: "ENTRA_ID"
   - identity_tenant_id: "abc-123-def"
4. Organization Lookup:
   SELECT * FROM organizations
   WHERE identity_provider = 'ENTRA_ID'
   AND identity_tenant_id = 'abc-123-def'
5a. Organization gefunden → User hat Org-Kontext
5b. Organization NICHT gefunden → Onboarding Flow
```

---

## 7. Login & Onboarding Flow

### 7.1 Deployment Konfiguration

```bash
# Environment Variables für Self-Hosted
DEPLOYMENT_MODE=self-hosted          # 'saas' oder 'self-hosted'
SYSTEM_ADMIN_EMAILS=admin@company.com,backup@company.com  # Initial Admins

# Optional: Auto-create Organization
AUTO_CREATE_ORGANIZATION=true
DEFAULT_ORGANIZATION_NAME="My Company"
```

### 7.2 Self-Hosted: Erster Login

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SELF-HOSTED: ERSTER LOGIN                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────────┐
│  Frontend   │     │    API      │     │           Database              │
└──────┬──────┘     └──────┬──────┘     └───────────────┬─────────────────┘
       │                   │                            │
       │  1. Login         │                            │
       │  (MSAL/IDP)       │                            │
       ├──────────────────►│                            │
       │                   │                            │
       │  2. GET /identity/me                           │
       ├──────────────────►│                            │
       │                   │  3. Lookup Organization    │
       │                   │  by (provider, tenant_id)  │
       │                   ├───────────────────────────►│
       │                   │                            │
       │                   │  4. Org nicht gefunden     │
       │                   │◄───────────────────────────┤
       │                   │                            │
       │                   │  5. Check: SYSTEM_ADMIN_EMAILS.includes(user.mail)?
       │                   │                            │
       │                   │  6. JA → Auto-Create:      │
       │                   │     - Organization         │
       │                   │     - OrganizationMember   │
       │                   │       (user as ORG_ADMIN)  │
       │                   │     - Default Tenant       │
       │                   │     - TenantMember         │
       │                   │       (user as GLOBAL_ADMIN)│
       │                   ├───────────────────────────►│
       │                   │                            │
       │  7. Response:     │                            │
       │  {                │                            │
       │    user: {...},   │                            │
       │    organization:  │                            │
       │      {name, tenants: [...]},                   │
       │    tenants: [{id, name, roles}]                │
       │  }                │                            │
       │◄──────────────────┤                            │
       │                   │                            │
       │  8. Redirect to   │                            │
       │  default tenant   │                            │
       │                   │                            │
```

### 7.3 Self-Hosted: Nachfolgende User

```
┌─────────────────────────────────────────────────────────────────────────┐
│                SELF-HOSTED: USER OHNE ORG-ZUGRIFF                       │
└─────────────────────────────────────────────────────────────────────────┘

1. User "new.user@company.com" loggt sich ein
2. Organization wird gefunden (gleicher Entra Tenant)
3. Check: Ist User OrganizationMember? → NEIN
4. Response:
   {
     user: {...},
     organization: null,  // Kein Zugriff
     tenants: []
   }
5. Frontend zeigt: "Kein Zugriff. Bitte ORG_ADMIN kontaktieren."

────────────────────────────────────────────────────────────────────────────

                    ORG_ADMIN FÜGT USER HINZU

1. ORG_ADMIN öffnet Organization Settings
2. Sucht User via IDP API (GET /identity/users?search=new.user)
3. Fügt User als OrganizationMember hinzu (ORG_MEMBER)
4. Weist User zu Tenants zu (TenantMember mit Rollen)
5. User loggt sich erneut ein → hat Zugriff
```

### 7.4 SaaS Mode (Zukunft)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SAAS: NEUKUNDE ONBOARDING                            │
└─────────────────────────────────────────────────────────────────────────┘

1. Kunde besucht unified-ui.com
2. Klickt "Free Trial starten"
3. Login mit Entra ID / Google / etc.
4. System erkennt: Neue Organization nötig
5. Onboarding Wizard:
   - Organization Name eingeben
   - Ersten Tenant erstellen (z.B. "Production")
   - Terms akzeptieren
6. Organization + Tenant werden erstellt
7. User wird ORG_ADMIN + GLOBAL_ADMIN
```

### 7.5 Detaillierter Login Flow (Code-Level)

```python
# In identity handler oder middleware

async def process_identity_me(user: ContextIdentityUser) -> IdentityMeResponse:
    """Process /identity/me request with organization awareness."""

    identity_provider = user.identity.get_identity_provider()
    identity_tenant_id = user.identity.get_identity_tenant_id()
    user_id = user.identity.get_id()
    user_mail = user.identity.get_mail()

    # 1. Lookup Organization
    org = await organization_handler.get_by_idp(
        identity_provider=identity_provider,
        identity_tenant_id=identity_tenant_id
    )

    # 2. Organization nicht gefunden → Prüfe System Admin
    if org is None:
        if is_system_admin(user_mail):
            # Auto-create Organization
            org = await organization_handler.create_initial_organization(
                identity_provider=identity_provider,
                identity_tenant_id=identity_tenant_id,
                admin_user_id=user_id,
                admin_mail=user_mail,
                admin_name=user.identity.get_display_name()
            )
        else:
            # Keine Berechtigung → leere Response
            return IdentityMeResponse(
                user=user.get_user_info(),
                organization=None,
                tenants=[]
            )

    # 3. Prüfe OrganizationMember
    org_member = await organization_handler.get_member(
        organization_id=org.id,
        principal_id=user_id
    )

    if org_member is None:
        # User hat keinen Org-Zugriff
        return IdentityMeResponse(
            user=user.get_user_info(),
            organization=OrganizationResponse(
                id=org.id,
                name=org.name,
                # Keine sensitiven Daten ohne Berechtigung
            ),
            has_access=False,
            tenants=[]
        )

    # 4. User hat Org-Zugriff → Hole Tenants mit Berechtigungen
    tenants = await tenant_handler.get_user_tenants_with_permissions(
        organization_id=org.id,
        user_id=user_id,
        group_ids=user.group_ids
    )

    return IdentityMeResponse(
        user=user.get_user_info(),
        organization=OrganizationResponse(
            id=org.id,
            name=org.name,
            role=org_member.role,
            settings=org.settings if org_member.role == "ORG_ADMIN" else None
        ),
        has_access=True,
        tenants=tenants
    )


def is_system_admin(email: str) -> bool:
    """Check if user is in SYSTEM_ADMIN_EMAILS config."""
    system_admins = settings.system_admin_emails or []
    return email.lower() in [e.lower() for e in system_admins]
```

---

## 8. Rollen & Berechtigungen

### 8.1 Rollen-Hierarchie

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         ROLLEN-HIERARCHIE                               │
└─────────────────────────────────────────────────────────────────────────┘

SYSTEM LEVEL (Environment Config)
├── SYSTEM_ADMIN_EMAILS
│   └── Kann erste Organization erstellen
│   └── Nur relevant für Self-Hosted Initial Setup

ORGANIZATION LEVEL
├── ORG_ADMIN
│   ├── Full Access auf alle Tenants der Organization
│   ├── Kann Tenants erstellen/löschen
│   ├── Kann OrganizationMembers verwalten
│   └── Kann Organization Settings ändern
│
├── ORG_MEMBER
│   ├── Kann auf zugewiesene Tenants zugreifen
│   └── Zugriffsrechte definiert durch TenantMember
│
└── ORG_READER
    └── Nur Lesen auf Org-Übersicht (für Auditing/Monitoring)

TENANT LEVEL (bestehend, unverändert)
├── GLOBAL_ADMIN
│   └── Full Access auf den Tenant
│
├── RESOURCE_ADMIN (z.B. CHAT_AGENTS_ADMIN)
│   └── Admin-Zugriff auf spezifische Ressource
│
├── RESOURCE_CREATOR (z.B. CHAT_AGENTS_CREATOR)
│   └── Kann Ressourcen erstellen, eigene verwalten
│
└── READER
    └── Nur Lesen
```

### 8.2 Berechtigungs-Matrix

| Aktion | ORG_ADMIN | ORG_MEMBER | ORG_READER |
|--------|-----------|------------|------------|
| Organization Settings lesen | ✅ | ❌ | ✅ |
| Organization Settings ändern | ✅ | ❌ | ❌ |
| Tenants erstellen/löschen | ✅ | ❌ | ❌ |
| Org Members verwalten | ✅ | ❌ | ❌ |
| Tenant Members verwalten | ✅ (alle) | ✅ (eigene) | ❌ |
| Auf Tenant zugreifen | ✅ (alle) | Per TenantMember | ❌ |
| Billing/Subscription verwalten | ✅ | ❌ | ❌ |

### 8.3 Permission Check Flow

```python
# Middleware für API Requests

async def check_organization_access(request: Request, required_role: str = None):
    """Check if user has organization access."""
    user: ContextIdentityUser = request.state.user

    # Hole Organization aus Token
    identity_provider = user.identity.get_identity_provider()
    identity_tenant_id = user.identity.get_identity_tenant_id()

    org = await get_organization_by_idp(identity_provider, identity_tenant_id)

    if not org:
        raise HTTPException(404, "Organization not found")

    # Prüfe Membership
    member = await get_org_member(org.id, user.identity.get_id())

    if not member:
        raise HTTPException(403, "No organization access")

    if required_role and member.role != required_role:
        if member.role != "ORG_ADMIN":  # ORG_ADMIN hat immer Zugriff
            raise HTTPException(403, f"Required role: {required_role}")

    # Speichere in Request State
    request.state.organization = org
    request.state.org_member = member
```

---

## 9. API Design

### 9.1 Neue Endpoints

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          NEUE API ENDPOINTS                             │
└─────────────────────────────────────────────────────────────────────────┘

# Organization Management
GET    /api/v1/organization                      # Get current organization
PATCH  /api/v1/organization                      # Update organization (ORG_ADMIN)
GET    /api/v1/organization/settings             # Get organization settings
PATCH  /api/v1/organization/settings             # Update settings (ORG_ADMIN)

# Organization Members
GET    /api/v1/organization/members              # List org members
POST   /api/v1/organization/members              # Add org member (ORG_ADMIN)
PATCH  /api/v1/organization/members/{id}         # Update member role (ORG_ADMIN)
DELETE /api/v1/organization/members/{id}         # Remove member (ORG_ADMIN)

# Tenants (erweitert, nicht mehr global)
GET    /api/v1/organization/tenants              # List tenants in org
POST   /api/v1/organization/tenants              # Create tenant (ORG_ADMIN)
DELETE /api/v1/organization/tenants/{tenant_id}  # Delete tenant (ORG_ADMIN)

# Bestehende Tenant-Endpoints bleiben für Tenant-interne Operationen
GET    /api/v1/tenants/{tenant_id}/...           # Bestehende Resource APIs
```

### 9.2 Response Schema Änderungen

```python
# Neue Response für /identity/me

class IdentityMeResponse(BaseModel):
    """Enhanced identity response with organization context."""

    # User Info (bestehend)
    id: str
    display_name: str
    mail: str | None
    identity_provider: str

    # NEU: Organization Context
    organization: OrganizationContext | None
    has_organization_access: bool

    # Tenants (erweitert)
    tenants: list[TenantWithRoles]

    # Groups (bestehend)
    groups: list[IdentityGroupResponse]


class OrganizationContext(BaseModel):
    """Organization info for current user."""

    id: str
    name: str
    slug: str
    role: str  # ORG_ADMIN, ORG_MEMBER, ORG_READER

    # Settings nur für ORG_ADMIN
    settings: OrganizationSettings | None = None


class TenantWithRoles(BaseModel):
    """Tenant with user's roles."""

    id: str
    name: str
    description: str | None
    environment_type: str  # SANDBOX, PRODUCTION
    is_default: bool
    roles: list[str]  # Tenant-level roles
```

---

## 10. Environment Promotion (Future)

### 10.1 Konzept

Environment Promotion ermöglicht das Kopieren von Ressourcen zwischen Tenants (z.B. Dev → Prod).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ENVIRONMENT PROMOTION                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Dev Tenant │────►│ Test Tenant │────►│ Prod Tenant │
│  (SANDBOX)  │     │  (SANDBOX)  │     │ (PRODUCTION)│
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │
      │   promote_to      │    promote_to     │
      └──────────────────►│──────────────────►│
```

### 10.2 Tenant Relationship

```python
class Tenant(Base):
    # ...
    previous_stage_id: Mapped[str | None]  # z.B. Dev → Test, Test → Prod

    # Beispiel Konfiguration:
    # - Dev: previous_stage_id = None
    # - Test: previous_stage_id = Dev.id
    # - Prod: previous_stage_id = Test.id
```

### 10.3 Promotion API (Future)

```
POST /api/v1/tenants/{source_tenant_id}/promote
{
    "target_tenant_id": "...",
    "resources": ["chat_agents", "credentials"],  # Was kopieren?
    "resource_ids": ["agent-1", "agent-2"],       # Spezifische IDs (optional)
    "overwrite_existing": false
}
```

---

## 11. SaaS vs Self-Hosted Unterschiede

### 11.1 Konfigurationsmatrix

| Aspekt | Self-Hosted | SaaS |
|--------|-------------|------|
| DEPLOYMENT_MODE | `self-hosted` | `saas` |
| SYSTEM_ADMIN_EMAILS | Initial Admin(s) | Unified-UI Team |
| AUTO_CREATE_ORGANIZATION | `true` | `false` |
| Organization Erstellung | Automatisch beim ersten Login | Via Signup/Beantragung |
| Billing | Nein (selbst gehostet) | Pro Organization |
| Multi-Organization | Nein (immer eine) | Ja (pro Kunde) |
| Identity Provider | Ein IDP | Beliebig pro Org |

### 11.2 Feature Flags

```python
# In config.py

class Settings(BaseSettings):
    # Deployment Mode
    deployment_mode: str = "self-hosted"  # "saas" oder "self-hosted"

    # Self-Hosted Settings
    system_admin_emails: list[str] = []
    auto_create_organization: bool = True
    default_organization_name: str = "Default Organization"

    # SaaS Settings (optional)
    signup_enabled: bool = False
    trial_days: int = 14

    @property
    def is_saas(self) -> bool:
        return self.deployment_mode == "saas"

    @property
    def is_self_hosted(self) -> bool:
        return self.deployment_mode == "self-hosted"
```

---

## 12. Migration

### 12.1 Migrationsstrategie

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MIGRATION (bestehende Daten)                       │
└─────────────────────────────────────────────────────────────────────────┘

Phase 1: Schema Migration
─────────────────────────
1. Neue Tabellen erstellen (organizations, organization_members)
2. Tenant-Tabelle erweitern (organization_id, environment_type, etc.)
3. organization_id ist nullable für Rückwärtskompatibilität

Phase 2: Daten Migration
────────────────────────
1. Für jeden existierenden Tenant:
   - Erstelle Organization (falls noch nicht für IDP Tenant vorhanden)
   - Setze tenant.organization_id
   - Migriere GLOBAL_ADMINs zu OrganizationMembers

Phase 3: Neue Logik aktivieren
──────────────────────────────
1. Feature Flag: USE_ORGANIZATION_HIERARCHY = true
2. Neue Auth-Middleware aktivieren
3. Frontend auf neue /identity/me Response anpassen

Phase 4: Cleanup
────────────────
1. organization_id required machen (NOT NULL)
2. Alte Code-Pfade entfernen
```

### 12.2 Alembic Migration Script

```python
# alembic/versions/xxxx_add_organizations.py

def upgrade():
    # 1. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        # ... weitere Spalten
    )

    # 2. Create organization_members table
    op.create_table(
        'organization_members',
        # ...
    )

    # 3. Add columns to tenants
    op.add_column('tenants', sa.Column('organization_id', sa.String(36), nullable=True))
    op.add_column('tenants', sa.Column('environment_type', sa.String(20), default='SANDBOX'))
    op.add_column('tenants', sa.Column('is_default', sa.Boolean, default=False))

    # 4. Add foreign key
    op.create_foreign_key(
        'fk_tenants_organization',
        'tenants', 'organizations',
        ['organization_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Reverse migration
    pass
```

### 12.3 Daten-Migration Script

```python
# scripts/migrate_to_organizations.py

async def migrate_tenants_to_organizations():
    """Migrate existing tenants to organization structure."""

    async with db_client.get_session() as session:
        # Get all tenants without organization
        tenants = await session.execute(
            select(Tenant).where(Tenant.organization_id.is_(None))
        )

        # Group tenants by creator's identity tenant
        # (Annahme: created_by ist user_id, wir müssen IDP tenant rausfinden)

        for tenant in tenants.scalars():
            # 1. Finde den Creator's IDP Tenant
            # (Kompliziert - benötigt Principal lookup oder Token history)

            # 2. Erstelle oder finde Organization
            org = await get_or_create_organization(
                identity_provider="ENTRA_ID",  # Annahme
                identity_tenant_id=creator_idp_tenant,
                name=f"Organization for {tenant.name}"
            )

            # 3. Link Tenant to Organization
            tenant.organization_id = org.id
            tenant.is_default = True  # Erster Tenant ist default

            # 4. Migrate GLOBAL_ADMINs to OrganizationMembers
            global_admins = await session.execute(
                select(TenantMember)
                .where(TenantMember.tenant_id == tenant.id)
                .where(TenantMember.role == "GLOBAL_ADMIN")
            )

            for admin in global_admins.scalars():
                await create_org_member(
                    organization_id=org.id,
                    principal_id=admin.principal_id,
                    role="ORG_ADMIN"
                )

        await session.commit()
```

---

## 13. Offene Fragen

### 13.1 Zu klären

| # | Frage | Optionen | Empfehlung |
|---|-------|----------|------------|
| 1 | Soll ein User in mehreren Organizations sein können (SaaS)? | Ja (Consultant-Szenario) / Nein | **Ja** - via verschiedene IDP Accounts |
| 2 | Was passiert wenn SYSTEM_ADMIN_EMAIL User gelöscht wird? | Anderer Admin / Config Update nötig | Config Update |
| 3 | Sollen Custom Groups org-weit oder tenant-weit sein? | Org-weit / Tenant-weit (aktuell) | **Tenant-weit** (bleibt) |
| 4 | Wie werden IDP Groups zu Org Members? | Automatisch / Manuell | **Manuell** (explizit hinzufügen) |
| 5 | Brauchen wir "Invite by Email" ohne IDP? | Ja / Nein | **Später** - aktuell IDP-only |
| 6 | Service Principal Support für M2M Auth? | Pro Org / Pro Tenant | **Pro Tenant** (bleibt, mit Org-Kontext) |

### 13.2 Implementierungsreihenfolge

1. **Phase 1: Core Organization** (Sprint 1)
   - Organization Model + Migration
   - OrganizationMember Model
   - Basic CRUD Handlers

2. **Phase 2: Auth Integration** (Sprint 2)
   - Middleware anpassen
   - /identity/me erweitern
   - Self-Hosted Bootstrap Flow

3. **Phase 3: Frontend Integration** (Sprint 3)
   - Org Settings UI
   - User Management UI
   - Tenant Dropdown mit Org-Kontext

4. **Phase 4: Advanced Features** (Sprint 4+)
   - Environment Types
   - Promotion (Basic)
   - SaaS Signup Flow

---

## Nächste Schritte

1. **Review dieses Konzepts** - Feedback sammeln
2. **Offene Fragen klären** - Entscheidungen treffen
3. **Technical Spike** - Proof of Concept für kritische Pfade
4. **Detailed Design** - API Specs, Frontend Mockups
5. **Implementation** - Gemäß Phasenplan

---

*Dieses Dokument wird iterativ erweitert basierend auf Feedback und Entscheidungen.*
