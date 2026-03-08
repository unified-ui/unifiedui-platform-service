# Setup Guide

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL
- Redis (optional, for caching)

## Quick Start

```sh
uv sync
source .venv/bin/activate
uvicorn unifiedui.app:app --reload --host 0.0.0.0 --port 8000
```

[OpenAPI Docs](http://localhost:8000/docs)

## Running Tests

```sh
pytest tests/ -n auto --no-header -q
```

## Linting & Formatting

```sh
ruff check .
ruff format --check .
```

---

## Azure App Registration (OBO Flow)

The platform service uses the OAuth 2.0 On-Behalf-Of (OBO) flow to securely access the Microsoft Graph API on behalf of authenticated users. The frontend sends an API-scoped access token; the backend verifies it via JWKS and exchanges it for a Graph token.

### How It Works

```
Frontend (MSAL)                   Platform Service                    Microsoft Entra ID
     |                                  |                                     |
     |-- API-scoped token ------------->|                                     |
     |   (aud=api://{client_id})        |                                     |
     |                                  |-- Verify signature (JWKS) --------->|
     |                                  |<-- Token verified ------------------|
     |                                  |                                     |
     |                                  |-- OBO exchange (user token -------->|
     |                                  |   + client_secret)                  |
     |                                  |<-- Graph access token --------------|
     |                                  |                                     |
     |                                  |-- Graph API calls (user info, ----->|
     |                                  |   groups, tenants)                  |
     |<-- Response ---------------------|                                     |
```

### Step 1: Create the App Registration

1. Go to [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → **New registration**
2. Name: `unified-ui` (or your project name)
3. Supported account types: **Single tenant** (or as needed)
4. Redirect URI: **Single-page application (SPA)** → `http://localhost:5173`
5. Click **Register**

Note the following values:
- **Application (client) ID** → used as `IDENTITY_CLIENT_ID` and `VITE_MSAL_CLIENT_ID`
- **Directory (tenant) ID** → used as `IDENTITY_TENANT_ID`

### Step 2: Expose an API

1. Go to **Expose an API** in the App Registration
2. Click **Add a scope**
3. Set the Application ID URI to `api://{client_id}` (auto-suggested)
4. Add scope:
   - Scope name: `access_as_user`
   - Who can consent: **Admins and users**
   - Admin consent display name: `Access unified-ui as user`
   - Admin consent description: `Allows the frontend to call the unified-ui backend on behalf of the signed-in user`
5. Click **Add scope**

The full scope URI is: `api://{client_id}/access_as_user`

### Step 3: Create a Client Secret

1. Go to **Certificates & secrets** → **Client secrets** → **New client secret**
2. Add a description and expiration
3. Copy the **Value** immediately (it won't be shown again) → used as `IDENTITY_CLIENT_SECRET`

### Step 4: Configure API Permissions

1. Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**
2. Add these permissions:
   - `User.Read` — Sign in and read user profile
   - `User.ReadBasic.All` — Read all users' basic profiles
   - `GroupMember.Read.All` — Read group memberships
   - `Group.Read.All` — Read all groups
3. Click **Grant admin consent for {tenant}** (requires Global Admin)
4. Verify all permissions show a green checkmark under "Status"

### Step 5: Configure the Platform Service

Copy `.env.example` to `.env` and set the identity variables:

```env
IDENTITY_CLIENT_ID=your-app-registration-client-id
IDENTITY_CLIENT_SECRET=your-app-registration-client-secret
IDENTITY_TENANT_ID=your-azure-ad-tenant-id
IDENTITY_JWKS_URL=https://login.microsoftonline.com/common/discovery/v2.0/keys
IDENTITY_TOKEN_ALGORITHMS=["RS256"]
IDENTITY_VERIFY_SIGNATURE=true
```

### Step 6: Configure the Frontend

In the frontend service `.env`:

```env
VITE_MSAL_CLIENT_ID=your-app-registration-client-id
VITE_MSAL_AUTHORITY=https://login.microsoftonline.com/your-tenant-id
VITE_MSAL_API_SCOPE=api://your-client-id/access_as_user
```

### Verification Checklist

After setup, verify:

- [ ] App Registration has `api://{client_id}/access_as_user` scope exposed
- [ ] Client secret is created and configured in `IDENTITY_CLIENT_SECRET`
- [ ] Graph delegated permissions added: `User.Read`, `User.ReadBasic.All`, `GroupMember.Read.All`, `Group.Read.All`
- [ ] Admin consent granted (green checkmarks in API Permissions)
- [ ] SPA redirect URI matches frontend URL (e.g. `http://localhost:5173`)
- [ ] `IDENTITY_VERIFY_SIGNATURE=true` in platform service `.env`
- [ ] Frontend `VITE_MSAL_API_SCOPE` matches the exposed scope URI

---

## Google Identity Platform (Google Workspace)

### How It Works

```
Frontend (Google Sign-In)         Platform Service                    Google APIs
     |                                  |                                     |
     |-- Google ID token -------------->|                                     |
     |   (aud=google_client_id)         |                                     |
     |                                  |-- Verify signature (JWKS) --------->|
     |                                  |   googleapis.com/oauth2/v3/certs    |
     |                                  |<-- Token verified ------------------|
     |                                  |                                     |
     |                                  |-- Admin Directory API ------------->|
     |                                  |   (service account token)           |
     |                                  |<-- Users/Groups data ---------------|
     |<-- Response ---------------------|                                     |
```

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a new project (or select existing)
2. Enable the **Admin SDK API** (search for it in "APIs & Services" → "Library")

### Step 2: Create OAuth 2.0 Client ID (for frontend)

1. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Application type: **Web application**
3. Authorized JavaScript origins: `http://localhost:5173` (and production URL)
4. Authorized redirect URIs: `http://localhost:5173` (and production URL)
5. Click **Create**

Note the **Client ID** → used as `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend)

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. User type: **Internal** (for Google Workspace) or **External** (for all Google accounts)
3. Add required scopes: `openid`, `email`, `profile`
4. Add test users if you selected External

### Step 4: Create a Service Account (for backend Admin SDK access)

1. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **Service Account**
2. Name: `unified-ui-admin` (or your project name)
3. Grant role: no roles needed at project level
4. Click **Done**
5. Go to the service account → **Keys** → **Add Key** → **Create new key** → **JSON**
6. Download the key file

### Step 5: Delegate Domain-Wide Authority (Google Workspace only)

1. In Google Cloud Console, go to the service account → copy the **Unique ID** (Client ID)
2. Go to [Google Workspace Admin Console](https://admin.google.com/) → **Security** → **API controls** → **Domain-wide delegation**
3. Click **Add new** and enter:
   - Client ID: the service account's Unique ID
   - OAuth scopes: `https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/admin.directory.group.readonly`
4. Click **Authorize**

### Step 6: Generate a Service Account Access Token

Use the service account key JSON to generate an access token (this should be automated in production):

```sh
gcloud auth activate-service-account --key-file=path/to/key.json
gcloud auth print-access-token --scopes=https://www.googleapis.com/auth/admin.directory.user.readonly,https://www.googleapis.com/auth/admin.directory.group.readonly
```

### Step 7: Configure the Platform Service

```env
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_SERVICE_ACCOUNT_TOKEN=your-service-account-access-token
IDENTITY_VERIFY_SIGNATURE=true
```

### Step 8: Configure the Frontend

```env
VITE_AUTH_PROVIDER=google
VITE_GOOGLE_CLIENT_ID=your-google-oauth-client-id
```

### Verification Checklist (Google)

- [ ] Google Cloud project created with Admin SDK API enabled
- [ ] OAuth 2.0 Client ID created with correct origins/redirect URIs
- [ ] Consent screen configured with `openid`, `email`, `profile` scopes
- [ ] Service account created with domain-wide delegation (Workspace only)
- [ ] `GOOGLE_CLIENT_ID` set in both backend and frontend `.env`
- [ ] `GOOGLE_SERVICE_ACCOUNT_TOKEN` set in backend `.env`
- [ ] Frontend `VITE_AUTH_PROVIDER=google`

---

## AWS Cognito

### How It Works

```
Frontend (Cognito Hosted UI)      Platform Service                    AWS Cognito
     |                                  |                                     |
     |-- Redirect to Hosted UI -------->|                                     |
     |<-- Authorization code -----------|                                     |
     |-- Exchange code for tokens ----->|                                     |
     |<-- ID token + access token ------|                                     |
     |                                  |                                     |
     |-- Cognito ID token ------------->|                                     |
     |   (aud=cognito_client_id)        |                                     |
     |                                  |-- Verify signature (JWKS) --------->|
     |                                  |   cognito-idp.{region}.amazonaws..  |
     |                                  |<-- Token verified ------------------|
     |                                  |                                     |
     |                                  |-- cognito-idp (boto3) ------------->|
     |                                  |   ListUsers, ListGroups, etc.       |
     |                                  |<-- Users/Groups data ---------------|
     |<-- Response ---------------------|                                     |
```

### Step 1: Create a Cognito User Pool

1. Go to [AWS Console](https://console.aws.amazon.com/) → **Amazon Cognito** → **Create user pool**
2. Configure sign-in: **Email** + **Username** (or as needed)
3. Password policy: set as required
4. MFA: optional (recommended for production)
5. Required attributes: `email`, `name` (or `given_name` + `family_name`)
6. Click **Create user pool**

Note the following:
- **User Pool ID** (e.g. `us-east-1_abc123`) → used as `AWS_COGNITO_USER_POOL_ID`
- **Region** (e.g. `us-east-1`) → used as `AWS_COGNITO_REGION`

### Step 2: Create an App Client

1. In the User Pool → **App integration** → **Create app client**
2. App type: **Public client** (for SPA frontend)
3. App client name: `unified-ui-frontend`
4. Authentication flows: **ALLOW_USER_SRP_AUTH**, **ALLOW_REFRESH_TOKEN_AUTH**
5. Do NOT generate a client secret (public client)
6. Click **Create**

Note the **App Client ID** → used as `AWS_COGNITO_CLIENT_ID` and `VITE_COGNITO_CLIENT_ID`

### Step 3: Configure Hosted UI Domain

1. In the User Pool → **App integration** → **Domain**
2. Choose a Cognito domain: `your-app-name.auth.{region}.amazoncognito.com`
3. Or configure a custom domain

Note the domain → used as `VITE_COGNITO_DOMAIN`

### Step 4: Configure Callback URLs

1. In the App Client → **Hosted UI** → Edit
2. Allowed callback URLs: `http://localhost:5173/auth/callback/cognito` (and production URL)
3. Allowed sign-out URLs: `http://localhost:5173/login` (and production URL)
4. OAuth 2.0 grant types: **Authorization code grant**
5. OpenID Connect scopes: `openid`, `email`, `profile`

### Step 5: Create IAM Credentials (for backend Admin API access)

1. Go to **IAM** → **Users** → **Create user**
2. Name: `unified-ui-cognito-admin`
3. Attach policy: **AmazonCognitoPowerUser** (or a custom policy with `cognito-idp:ListUsers`, `cognito-idp:AdminGetUser`, `cognito-idp:ListGroups`, `cognito-idp:ListUsersInGroup`, `cognito-idp:AdminListGroupsForUser`)
4. Create **Access Key** → type: **Application running outside AWS**
5. Save the Access Key ID and Secret Access Key

### Step 6: Configure the Platform Service

```env
AWS_COGNITO_REGION=us-east-1
AWS_COGNITO_USER_POOL_ID=us-east-1_abc123
AWS_COGNITO_CLIENT_ID=your-cognito-app-client-id
AWS_COGNITO_ACCESS_KEY_ID=your-iam-access-key-id
AWS_COGNITO_SECRET_ACCESS_KEY=your-iam-secret-access-key
IDENTITY_VERIFY_SIGNATURE=true
```

### Step 7: Configure the Frontend

```env
VITE_AUTH_PROVIDER=aws_cognito
VITE_COGNITO_REGION=us-east-1
VITE_COGNITO_USER_POOL_ID=us-east-1_abc123
VITE_COGNITO_CLIENT_ID=your-cognito-app-client-id
VITE_COGNITO_DOMAIN=your-app.auth.us-east-1.amazoncognito.com
```

### Verification Checklist (AWS Cognito)

- [ ] User Pool created with email + required attributes
- [ ] App Client created (public, no secret) with correct auth flows
- [ ] Hosted UI domain configured
- [ ] Callback URLs set: `http://localhost:5173/auth/callback/cognito`
- [ ] Sign-out URLs set: `http://localhost:5173/login`
- [ ] OAuth scopes: `openid`, `email`, `profile`
- [ ] IAM user created with Cognito admin permissions
- [ ] `AWS_COGNITO_*` environment variables set in backend `.env`
- [ ] `VITE_AUTH_PROVIDER=aws_cognito` and `VITE_COGNITO_*` set in frontend `.env`

---

## LDAP

### How It Works

```
Frontend (Gateway)                Platform Service                    LDAP Server
     |                                  |                                     |
     |-- Gateway-issued JWT ----------->|                                     |
     |   (iss=ldap://{server})          |                                     |
     |                                  |-- Verify expiry (no JWKS) --------->|
     |                                  |                                     |
     |                                  |-- LDAP bind (service account) ----->|
     |                                  |   ldap3 SUBTREE search              |
     |                                  |<-- Users/Groups data ---------------|
     |<-- Response ---------------------|                                     |
```

The LDAP integration expects an API gateway (e.g. Kong, Nginx with auth module) to authenticate users against the LDAP directory and issue a JWT with LDAP user claims. The platform service trusts this gateway-issued token (no JWKS signature verification) and uses a service account bind to query users and groups from the LDAP directory.

### Prerequisites

- An LDAP directory (OpenLDAP, Active Directory, 389 Directory Server, etc.)
- An API gateway that authenticates users via LDAP and issues JWTs with `iss` starting with `ldap://` or `ldaps://`
- A service account (bind DN + password) with read access to user and group entries
- Python package `ldap3` installed: `uv add ldap3`

### Step 1: Create a Service Account in LDAP

1. Create a dedicated bind user (e.g. `cn=unified-ui,ou=service-accounts,dc=example,dc=com`)
2. Grant read access to the user and group OUs
3. Note the **Bind DN** and **Password**

### Step 2: Configure the API Gateway

Configure your gateway to:
1. Authenticate users against the LDAP directory
2. Issue JWTs with the following claims:
   - `iss`: `ldap://{your-ldap-server}` or `ldaps://{your-ldap-server}`
   - `sub` or `uid`: unique user identifier
   - `cn` or `name`: display name
   - `mail` or `email`: email address
   - `givenName`: first name (optional)
   - `sn`: last name (optional)
   - `o` or `dn`: organization/DN (optional, used as tenant ID)

### Step 3: Configure the Platform Service

```env
LDAP_SERVER_URL=ldaps://ldap.example.com:636
LDAP_BIND_DN=cn=unified-ui,ou=service-accounts,dc=example,dc=com
LDAP_BIND_PASSWORD=your-service-account-password
LDAP_BASE_DN=dc=example,dc=com
LDAP_USER_SEARCH_FILTER=(objectClass=person)
LDAP_GROUP_SEARCH_FILTER=(objectClass=groupOfNames)
LDAP_USE_SSL=true
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `LDAP_SERVER_URL` | Yes | – | LDAP server URL (`ldap://` or `ldaps://`) |
| `LDAP_BIND_DN` | Yes | – | Service account distinguished name |
| `LDAP_BIND_PASSWORD` | Yes | – | Service account password |
| `LDAP_BASE_DN` | Yes | – | Base DN for searches (e.g. `dc=example,dc=com`) |
| `LDAP_USER_SEARCH_FILTER` | No | `(objectClass=person)` | LDAP filter for user entries |
| `LDAP_GROUP_SEARCH_FILTER` | No | `(objectClass=groupOfNames)` | LDAP filter for group entries |
| `LDAP_USE_SSL` | No | `true` | Use SSL/TLS for LDAP connection |

### Verification Checklist (LDAP)

- [ ] LDAP server reachable from platform service network
- [ ] Service account bind DN + password configured
- [ ] Base DN matches your directory structure
- [ ] API gateway issues JWTs with `iss` starting with `ldap://` or `ldaps://`
- [ ] `ldap3` Python package installed
- [ ] `LDAP_*` environment variables set in backend `.env`

---

## Kerberos

### How It Works

```
Frontend (Gateway)                Platform Service                    KDC / LDAP
     |                                  |                                     |
     |-- Kerberos ticket (SPNEGO) ----->| Gateway                             |
     |-- Gateway-issued JWT ----------->|                                     |
     |   (iss=krb://{realm})            |                                     |
     |                                  |-- Verify expiry (no JWKS) --------->|
     |                                  |                                     |
     |                                  |-- LDAP (SASL/Kerberos) ------------>|
     |                                  |   Query AD for users/groups         |
     |                                  |<-- Users/Groups data ---------------|
     |<-- Response ---------------------|                                     |
```

The Kerberos integration assumes an API gateway handles SPNEGO/Kerberos ticket exchange and converts it to a JWT. The platform service trusts this gateway-issued token and queries an LDAP backend (typically Active Directory) using SASL/Kerberos authentication for user and group lookups.

### Prerequisites

- A Kerberos KDC (MIT Kerberos or Active Directory)
- An API gateway with SPNEGO/Kerberos support that issues JWTs with `iss` starting with `krb://`
- An LDAP directory (usually AD) accessible via SASL/Kerberos for user/group queries
- A keytab file for the service principal

### Step 1: Create a Service Principal

1. Create a service principal in your KDC (e.g. `HTTP/unified-ui.example.com@EXAMPLE.COM`)
2. Generate a keytab file:
   ```sh
   kadmin -q "ktadd -k /etc/krb5.keytab HTTP/unified-ui.example.com@EXAMPLE.COM"
   ```
3. Ensure the keytab is readable by the platform service process

### Step 2: Configure the API Gateway

Configure your gateway to:
1. Negotiate SPNEGO authentication with clients
2. Validate Kerberos tickets against the KDC
3. Issue JWTs with the following claims:
   - `iss`: `krb://{realm}` (e.g. `krb://EXAMPLE.COM`)
   - `sub` or `principal`: Kerberos principal name
   - `realm`: Kerberos realm
   - `cn` or `name`: display name (optional)
   - `givenName` or `given_name`: first name (optional)
   - `sn` or `family_name`: last name (optional)
   - `mail` or `email`: email address (optional)

### Step 3: Configure the Platform Service

```env
KERBEROS_REALM=EXAMPLE.COM
KERBEROS_KDC_HOST=kdc.example.com
KERBEROS_SERVICE_PRINCIPAL=HTTP/unified-ui.example.com@EXAMPLE.COM
KERBEROS_KEYTAB_PATH=/etc/krb5.keytab
KERBEROS_LDAP_URL=ldap://ad.example.com:389
KERBEROS_LDAP_BASE_DN=dc=example,dc=com
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `KERBEROS_REALM` | Yes | – | Kerberos realm (e.g. `EXAMPLE.COM`) |
| `KERBEROS_KDC_HOST` | No | – | KDC hostname (for diagnostics/ticket operations) |
| `KERBEROS_SERVICE_PRINCIPAL` | No | – | Service principal name |
| `KERBEROS_KEYTAB_PATH` | No | – | Path to keytab file |
| `KERBEROS_LDAP_URL` | Yes* | – | LDAP/AD URL for user/group queries |
| `KERBEROS_LDAP_BASE_DN` | Yes* | – | Base DN for LDAP searches |

\* Required for user/group lookups. Without LDAP, only token-based identity is available.

### Verification Checklist (Kerberos)

- [ ] KDC reachable from platform service network
- [ ] Service principal created and keytab generated
- [ ] API gateway handles SPNEGO and issues JWTs with `iss=krb://{realm}`
- [ ] LDAP/AD accessible for user/group queries (if needed)
- [ ] `KERBEROS_*` environment variables set in backend `.env`

---

## SAML 2.0

### How It Works

```
Frontend (SP)                     Platform Service                    SAML IdP
     |                                  |                                     |
     |-- Redirect to IdP SSO URL ----->|                                      |
     |<-- SAML Assertion (POST) -------|                                      |
     |-- Assertion-converted JWT ------>|                                     |
     |   (iss=saml_entity_id)           |                                     |
     |                                  |-- Verify expiry (no JWKS) --------->|
     |                                  |                                     |
     |                                  |-- Extract groups from claims ------>|
     |                                  |   (assertion-based, no directory)    |
     |<-- Response ---------------------|                                     |
```

The SAML integration expects an SP proxy (or API gateway) to handle the SAML assertion exchange and convert the SAML assertion into a JWT. The platform service trusts this converted token and extracts user identity and group membership directly from the assertion claims — there is no separate directory API call.

### Prerequisites

- A SAML 2.0 Identity Provider (Okta, ADFS, Shibboleth, Keycloak, etc.)
- An SP proxy or API gateway that converts SAML assertions to JWTs with `iss` matching the `SAML_ENTITY_ID`
- The IdP must include user attributes (name, email, groups) in the assertion

### Step 1: Configure the SAML IdP

1. Create a new SAML application in your IdP
2. Configure the following:
   - **SP Entity ID**: Your service identifier (e.g. `https://unified-ui.example.com/saml`)
   - **ACS URL**: Your SP proxy's assertion consumer service URL
   - **NameID Format**: `emailAddress` or `persistent`
3. Configure attribute statements to include:
   - `uid` → unique user id
   - `email` → user email
   - `displayName` → display name
   - `firstName` → first name
   - `lastName` → last name
   - `groups` → group memberships (multi-valued)

### Step 2: Configure the Platform Service

```env
SAML_ENTITY_ID=https://unified-ui.example.com/saml
SAML_SSO_URL=https://idp.example.com/sso/saml
SAML_CERTIFICATE=base64-encoded-idp-certificate
SAML_METADATA_URL=https://idp.example.com/metadata
SAML_ATTRIBUTE_MAP_ID=uid
SAML_ATTRIBUTE_MAP_EMAIL=email
SAML_ATTRIBUTE_MAP_DISPLAY_NAME=displayName
SAML_ATTRIBUTE_MAP_FIRST_NAME=firstName
SAML_ATTRIBUTE_MAP_LAST_NAME=lastName
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `SAML_ENTITY_ID` | Yes | – | SP Entity ID (must match `iss` in converted JWT) |
| `SAML_SSO_URL` | No | – | IdP SSO URL (for SP-initiated login) |
| `SAML_CERTIFICATE` | No | – | Base64-encoded IdP signing certificate |
| `SAML_METADATA_URL` | No | – | IdP metadata URL for auto-configuration |
| `SAML_ATTRIBUTE_MAP_ID` | No | `uid` | Claim name for user ID |
| `SAML_ATTRIBUTE_MAP_EMAIL` | No | `email` | Claim name for email |
| `SAML_ATTRIBUTE_MAP_DISPLAY_NAME` | No | `displayName` | Claim name for display name |
| `SAML_ATTRIBUTE_MAP_FIRST_NAME` | No | `firstName` | Claim name for first name |
| `SAML_ATTRIBUTE_MAP_LAST_NAME` | No | `lastName` | Claim name for last name |

### Verification Checklist (SAML)

- [ ] SAML IdP configured with correct SP Entity ID and ACS URL
- [ ] Attribute statements include uid, email, displayName, firstName, lastName, groups
- [ ] SP proxy or gateway converts SAML assertions to JWTs with `iss` = `SAML_ENTITY_ID`
- [ ] `SAML_*` environment variables set in backend `.env`
- [ ] Attribute map matches your IdP's claim names (adjust `SAML_ATTRIBUTE_MAP_*` if needed)

---

## Okta

### How It Works

```
Frontend (Okta SDK)               Platform Service                    Okta
     |                                  |                                     |
     |-- Redirect to Okta login ------->|                                     |
     |<-- Authorization code -----------|                                     |
     |-- Exchange code for tokens ----->|                                     |
     |<-- ID token + access token ------|                                     |
     |                                  |                                     |
     |-- Okta ID token ---------------->|                                     |
     |   (aud=okta_client_id)           |                                     |
     |                                  |-- Verify signature (JWKS) --------->|
     |                                  |   {okta_domain}/oauth2/.../v1/keys  |
     |                                  |<-- Token verified ------------------|
     |                                  |                                     |
     |                                  |-- Okta Management API v1 ---------->|
     |                                  |   /api/v1/users, /api/v1/groups     |
     |                                  |<-- Users/Groups data ---------------|
     |<-- Response ---------------------|                                     |
```

### Step 1: Create an Okta Application

1. Go to [Okta Admin Console](https://admin.okta.com/) → **Applications** → **Create App Integration**
2. Sign-in method: **OIDC - OpenID Connect**
3. Application type: **Single-Page Application**
4. Grant types: **Authorization Code** (with PKCE)
5. Sign-in redirect URIs: `http://localhost:5173/auth/callback/okta` (and production URL)
6. Sign-out redirect URIs: `http://localhost:5173/login` (and production URL)
7. Controlled access: Assign to appropriate groups

Note the **Client ID** → used as `OKTA_CLIENT_ID`

### Step 2: Create an API Token (for backend Management API)

1. Go to **Security** → **API** → **Tokens** → **Create Token**
2. Name: `unified-ui-platform`
3. Copy the token → used as `OKTA_API_TOKEN`

> **Note**: API tokens inherit the permissions of the admin who creates them. Use a service admin with appropriate read permissions.

### Step 3: Configure Authorization Server (optional)

By default, Okta uses the `default` authorization server. If you have a custom one:
1. Go to **Security** → **API** → **Authorization Servers**
2. Note the authorization server **ID** → used as `OKTA_AUTHORIZATION_SERVER_ID`

### Step 4: Configure the Platform Service

```env
OKTA_DOMAIN=your-org.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_API_TOKEN=your-okta-api-token
OKTA_AUTHORIZATION_SERVER_ID=default
IDENTITY_VERIFY_SIGNATURE=true
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `OKTA_DOMAIN` | Yes | – | Okta org domain (e.g. `your-org.okta.com`) |
| `OKTA_CLIENT_ID` | Yes | – | OIDC application client ID |
| `OKTA_API_TOKEN` | Yes | – | Okta API token (SSWS) for Management API |
| `OKTA_AUTHORIZATION_SERVER_ID` | No | `default` | Authorization server ID |

### Step 5: Configure the Frontend

```env
VITE_AUTH_PROVIDER=okta
VITE_OKTA_DOMAIN=your-org.okta.com
VITE_OKTA_CLIENT_ID=your-okta-client-id
```

### Verification Checklist (Okta)

- [ ] Okta SPA application created with PKCE enabled
- [ ] Redirect URIs configured for development and production
- [ ] API token created with appropriate admin permissions
- [ ] `OKTA_*` environment variables set in backend `.env`
- [ ] `VITE_AUTH_PROVIDER=okta` and `VITE_OKTA_*` set in frontend `.env`
- [ ] `IDENTITY_VERIFY_SIGNATURE=true` in backend `.env`

---

## Generic OIDC

### How It Works

```
Frontend (OIDC Client)            Platform Service                    OIDC Provider
     |                                  |                                     |
     |-- Redirect to authorize -------->|                                     |
     |<-- Authorization code -----------|                                     |
     |-- Exchange code for tokens ----->|                                     |
     |<-- ID token + access token ------|                                     |
     |                                  |                                     |
     |-- OIDC ID token ---------------->|                                     |
     |   (aud=oidc_client_id)           |                                     |
     |                                  |-- Verify signature (JWKS) --------->|
     |                                  |   {issuer}/.well-known/jwks.json    |
     |                                  |<-- Token verified ------------------|
     |                                  |                                     |
     |                                  |-- UserInfo endpoint --------------->|
     |                                  |   (fallback: token claims)          |
     |                                  |<-- User data -----------------------|
     |<-- Response ---------------------|                                     |
```

The Generic OIDC integration supports any OpenID Connect compliant provider (Keycloak, Auth0, Authentik, Zitadel, Dex, etc.). It uses JWKS for token verification and the UserInfo endpoint for user profile data.

### Step 1: Register an Application with your OIDC Provider

1. Create a new OIDC/OAuth2 application (type: SPA or Public)
2. Configure:
   - **Redirect URIs**: `http://localhost:5173/auth/callback/oidc` (and production URL)
   - **Post-logout redirect**: `http://localhost:5173/login`
   - **Grant types**: Authorization Code (with PKCE)
   - **Scopes**: `openid`, `profile`, `email`
3. Note the **Client ID** and **Issuer URL**
4. If your provider requires a client secret for token exchange, note the **Client Secret**

### Step 2: Gather Provider Endpoints

Most OIDC providers expose a discovery document at `{issuer_url}/.well-known/openid-configuration` containing:
- **JWKS URL**: for signature verification (auto-derived from issuer if not set)
- **UserInfo URL**: for user profile data (optional, falls back to token claims)

### Step 3: Configure the Platform Service

```env
OIDC_ISSUER_URL=https://auth.example.com/realms/my-realm
OIDC_CLIENT_ID=your-oidc-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_JWKS_URL=https://auth.example.com/realms/my-realm/protocol/openid-connect/certs
OIDC_USERINFO_URL=https://auth.example.com/realms/my-realm/protocol/openid-connect/userinfo
OIDC_SCOPES=openid profile email
IDENTITY_VERIFY_SIGNATURE=true
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `OIDC_ISSUER_URL` | Yes | – | OIDC provider issuer URL (must match `iss` claim) |
| `OIDC_CLIENT_ID` | Yes | – | OIDC application client ID |
| `OIDC_CLIENT_SECRET` | No | – | Client secret (if required by provider) |
| `OIDC_JWKS_URL` | No | `{issuer}/.well-known/jwks.json` | JWKS endpoint URL (auto-derived) |
| `OIDC_USERINFO_URL` | No | – | UserInfo endpoint for profile data |
| `OIDC_SCOPES` | No | `openid profile email` | Space-separated scopes |

### Step 4: Configure the Frontend

```env
VITE_AUTH_PROVIDER=oidc
VITE_OIDC_ISSUER_URL=https://auth.example.com/realms/my-realm
VITE_OIDC_CLIENT_ID=your-oidc-client-id
```

### Provider-Specific Examples

**Keycloak:**
```env
OIDC_ISSUER_URL=https://keycloak.example.com/realms/unified-ui
OIDC_CLIENT_ID=unified-ui-frontend
OIDC_JWKS_URL=https://keycloak.example.com/realms/unified-ui/protocol/openid-connect/certs
OIDC_USERINFO_URL=https://keycloak.example.com/realms/unified-ui/protocol/openid-connect/userinfo
```

**Auth0:**
```env
OIDC_ISSUER_URL=https://your-tenant.auth0.com/
OIDC_CLIENT_ID=your-auth0-client-id
OIDC_JWKS_URL=https://your-tenant.auth0.com/.well-known/jwks.json
OIDC_USERINFO_URL=https://your-tenant.auth0.com/userinfo
```

**Authentik:**
```env
OIDC_ISSUER_URL=https://authentik.example.com/application/o/unified-ui/
OIDC_CLIENT_ID=your-authentik-client-id
```

### Verification Checklist (Generic OIDC)

- [ ] OIDC application registered with correct redirect URIs
- [ ] Grant type: Authorization Code with PKCE
- [ ] Scopes: `openid`, `profile`, `email`
- [ ] `OIDC_ISSUER_URL` matches the `iss` claim in issued tokens
- [ ] `OIDC_*` environment variables set in backend `.env`
- [ ] `VITE_AUTH_PROVIDER=oidc` and `VITE_OIDC_*` set in frontend `.env`
- [ ] `IDENTITY_VERIFY_SIGNATURE=true` in backend `.env`

---

## Multi-IDP Configuration Summary

| Environment Variable | Service | Required For |
|---|---|---|
| `VITE_AUTH_PROVIDER` | Frontend | All (values: `microsoft`, `google`, `aws_cognito`, `ldap`, `kerberos`, `saml`, `okta`, `oidc`) |
| `IDENTITY_VERIFY_SIGNATURE` | Backend | All JWKS-based IDPs (`true` recommended) |
| `IDENTITY_CLIENT_ID` | Backend | Microsoft Entra ID |
| `IDENTITY_CLIENT_SECRET` | Backend | Microsoft Entra ID (OBO) |
| `IDENTITY_TENANT_ID` | Backend | Microsoft Entra ID |
| `VITE_MSAL_CLIENT_ID` | Frontend | Microsoft Entra ID |
| `VITE_MSAL_AUTHORITY` | Frontend | Microsoft Entra ID |
| `VITE_MSAL_API_SCOPE` | Frontend | Microsoft Entra ID |
| `GOOGLE_CLIENT_ID` | Backend | Google Identity |
| `GOOGLE_SERVICE_ACCOUNT_TOKEN` | Backend | Google Identity |
| `VITE_GOOGLE_CLIENT_ID` | Frontend | Google Identity |
| `AWS_COGNITO_REGION` | Backend | AWS Cognito |
| `AWS_COGNITO_USER_POOL_ID` | Backend | AWS Cognito |
| `AWS_COGNITO_CLIENT_ID` | Backend | AWS Cognito |
| `AWS_COGNITO_ACCESS_KEY_ID` | Backend | AWS Cognito |
| `AWS_COGNITO_SECRET_ACCESS_KEY` | Backend | AWS Cognito |
| `VITE_COGNITO_REGION` | Frontend | AWS Cognito |
| `VITE_COGNITO_USER_POOL_ID` | Frontend | AWS Cognito |
| `VITE_COGNITO_CLIENT_ID` | Frontend | AWS Cognito |
| `VITE_COGNITO_DOMAIN` | Frontend | AWS Cognito |
| `LDAP_SERVER_URL` | Backend | LDAP |
| `LDAP_BIND_DN` | Backend | LDAP |
| `LDAP_BIND_PASSWORD` | Backend | LDAP |
| `LDAP_BASE_DN` | Backend | LDAP |
| `LDAP_USER_SEARCH_FILTER` | Backend | LDAP (optional) |
| `LDAP_GROUP_SEARCH_FILTER` | Backend | LDAP (optional) |
| `LDAP_USE_SSL` | Backend | LDAP (optional) |
| `KERBEROS_REALM` | Backend | Kerberos |
| `KERBEROS_KDC_HOST` | Backend | Kerberos (optional) |
| `KERBEROS_SERVICE_PRINCIPAL` | Backend | Kerberos (optional) |
| `KERBEROS_KEYTAB_PATH` | Backend | Kerberos (optional) |
| `KERBEROS_LDAP_URL` | Backend | Kerberos |
| `KERBEROS_LDAP_BASE_DN` | Backend | Kerberos |
| `SAML_ENTITY_ID` | Backend | SAML |
| `SAML_SSO_URL` | Backend | SAML (optional) |
| `SAML_CERTIFICATE` | Backend | SAML (optional) |
| `SAML_METADATA_URL` | Backend | SAML (optional) |
| `SAML_ATTRIBUTE_MAP_*` | Backend | SAML (optional, 5 fields) |
| `OKTA_DOMAIN` | Backend | Okta |
| `OKTA_CLIENT_ID` | Backend | Okta |
| `OKTA_API_TOKEN` | Backend | Okta |
| `OKTA_AUTHORIZATION_SERVER_ID` | Backend | Okta (optional) |
| `VITE_OKTA_DOMAIN` | Frontend | Okta |
| `VITE_OKTA_CLIENT_ID` | Frontend | Okta |
| `OIDC_ISSUER_URL` | Backend | Generic OIDC |
| `OIDC_CLIENT_ID` | Backend | Generic OIDC |
| `OIDC_CLIENT_SECRET` | Backend | Generic OIDC (optional) |
| `OIDC_JWKS_URL` | Backend | Generic OIDC (optional) |
| `OIDC_USERINFO_URL` | Backend | Generic OIDC (optional) |
| `OIDC_SCOPES` | Backend | Generic OIDC (optional) |
| `VITE_OIDC_ISSUER_URL` | Frontend | Generic OIDC |
| `VITE_OIDC_CLIENT_ID` | Frontend | Generic OIDC |
