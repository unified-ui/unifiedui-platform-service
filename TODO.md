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
- refactoring
    - db client wird in users.py noch initialisiert -> sollte injected werden!
    - cache > dependencies:
        - wenn type is None -> sollte cache auf None sein und nicht redis initialisiert werden!
    - db > 

- immer wenn was auf permissions PUT PATCH POST DELETE gemahct wird:
    - clear cache: "*user:{user_id}"

- Caching
    - tenants in handler rein
        - und wichtig: users.py wird noch außerhalb ge
    - cusgroups

- Credentials
    - CRUD
    - metadaten in db; key in secrets vault
    - key auch cachen, aber mit encryption key (aus env)


    - testen
    - permissions checken

- bei check_permission muss noch irgendwie die "id" mit rein -> dann kann man checken, ob man auf die ID berechtigt ist!

- Routes für credentials checken
    - ganze logik muss in handler!
    - CREDENTIALS_CREATOR
    - required_permissions updaten!
- Applications
    - CRUD
    - Config
        - N8N Connection
    - Cache

- Conversations
    - CRUD + get_messages_until (siehe agentmemory-py!)
    - invoke -> use n8n chat-model
        - wie macht man es, wenn eine rückfrage gestellt wird? geht ja in einem Workflow

- autonomous agents
- nur: entity_members -> dort role mit enum
- Die Routes mit Postman testen und refactoren
    - permissions zu rollen ändern
    - name auf permisison raus (nur role als name)
    - ...
- tests bauen
    - in memory db konfigurieren für tests
    - die routes testen
- Spec-Driven Vibe-Coding machen (in einem Spec projekt etc beschreiben)
## TODO


- tests bauen
    - insbesondere permissions testen!
        - principal IDs kann man "erfinden" (einfach string)
        - IdentityUser können wir über JWT "mocken" bzw wir könnten
    - caching testen! cache-invalidierung
    - wir fahren infrastruktur hoch für On-Prem Komponenten
    - und es wird auf Azure Test-Komponenten für Integration tests geben
        - integration testen

- alle tests bauen
- bauen tests für /aihub/utils/*
- bauen factory tests für (nur initialisierung und ob interface functions vorhanden sind)
    - /aihub/core/caching
        - + /aihub/caching
    - /aihub/core/identity
        - + /aihub/identity
    - /aihub/core/middleware
        - + /aihub/middleware
    - /aihub/core/vault
        - + /aihub/vault

- alle test datein checken
    - ist in list resource getestet, ob man nur seine frigegebenen resourcen sieht?
    - checken, dass in den handler kein authoritation (außer bei lsit) durchgeführt wird!
    - in den apis definitionen nochmal alle rollenzugriffe checken (admin darf löschen; write nicht!)
    - ob wirklich alle tests implementiert sind und wie
    - ggf refactoren

- check_permissions optimieren
    - bei /{id} immer nur filtern und count ausgeben -> wenn count > 0, dann ja, sonst nein
        - also so schnell wie möglich
    - in check_permissions mit caching arbeiten; wenn user berechtigt -> super; wenn nicht wird nochmal in DB geschaut (vielleicht...)

---

**Integrations**

- invoke N8N etc

**Optimizations**

- chat service als microservice in selber struktur (nur app-core und app-chat) auslagern
    - besser skalierbar
