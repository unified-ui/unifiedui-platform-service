# TODOs

## Done

- Identity:
    - Bekommt man die Extra-Gruppen in den Token?
        - nein, aber über API
        - tenantID (tid) bekommt man aus dem JWT Token
    - Token-Validation
    - ID + tenantID aus Token für Cache
    - Frontend -> MSAL Flow für Token

- identity provider (Extra ID) implementieren
- routes für identity impl
- user MUSS get_id -> haben
- tenant
    - CRUD
    - Gibt TenantID, ClientID und ClientSecret für Service Principal an
        - SP muss Benutzer und Gruppen lesen können
    - hier vielleicht doch eher immer mit den UserToken arbeiten? der kann doch Gruppen und so auslesen?
    - und beim anmelden einen tenant anlegen; man kann aber auch neuen anlegen

- Permissions
    - CRUD

- cache implementieren
    - cache
    - in tenants einbauen und testen
    - chacing strategie: tenantid immer in den key -> wenn was an permissions gemacht wird -> einfach alles aus was mit dem tenantid im key ist aus dem cache killen (step 1; später besser!)

- software tests für tenants, inkl cache
- neuen branch erstellen: feature/change-database-v2

- ppostgres mit einbauen als core für access und list operations
    - permissions
    - appplications
    - conversations
    - credentials
    - JSON-DB nur bei
        - messages
        - traces
        - also überall, wo man immer auf eine id zugreift und nur eintweder ein doc oder mehrere docs, aber zu einem objekt zugreift
    - TODOs
        - Datenmodell überlegen

- in IdentityUser die tenants und roles reinbringen (aber nur wichtige infos!)
- refactoring:
    - has_permissions refactoren und auslagern -> am besten in middleware decorator!
    - caching besser implementieren!!! für tenants, groups, permissions!!! und clear

- custom_groups (/api/v1/tenants/{id}/custom/groups)
    - CRUD

- identity/users/{id}
- identity/groups/{id}
- next_link bei /users testen -> funktioniert das?

## TODO




- refactoring
    - db client wird in users.py noch initialisiert -> sollte injected werden!
- Caching
    - tenants in handler rein
        - und wichtig: users.py wird noch außerhalb ge
    - cusgroups

- Spec-Driven Vibe-Coding machen (in einem Spec projekt etc beschreiben)

- permissions mit zweitem account testen auf
    - tenant
    - custom groups



- Credentials
    - CRUD
    - metadaten in db; key in secrets vault
    - key auch cachen, aber mit encryption key (aus env)

- Applications
    - CRUD
    - Config
        - N8N Connection
    - Cache

- Conversations
    - CRUD + get_messages_until (siehe agentmemory-py!)
    - invoke -> use n8n chat-model
        - wie macht man es, wenn eine rückfrage gestellt wird? geht ja in einem Workflow

---

- /tenants/{id}/principals
    - noch im identity provider (idp) get_user_by_id und get_group_by_id implementieren um die Namen zu fetchen!