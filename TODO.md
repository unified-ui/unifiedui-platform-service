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
- bauen mir nun unit tests für:
    - /aihub/core/caching
        - + /aihub/caching
    - /aihub/core/identity
        - + /aihub/identity
    - /aihub/core/middleware
        - + /aihub/middleware
    - /aihub/core/vault
        - + /aihub/vault
- schreibe mir eine CI GitHub Action pipeline, welche die tests auf github ausführt
    - wichtig: das projekt nutzt uv -> also install, tests etc mit uv (pytest) ausführen
## TODO

**Next Steps**
1. Test-Dateien checken
2. check_permissions optimieren
3. Frontend bis dato entwickeln (siehe unten)
4. Chat-Service entwickeln
    - N8N Integration Human-in-the-Loop (Chat-Response + Rückfragen) entwickeln
5. Weiteren Service als Human-in-the-Loop implementieren
6. N8N komplexeren Workflow implementieren (mit RAG Reasoning etc) implementieren
7. Autonomen Agent implementieren
8. Frontend erweitern
    - Chat Service
    - Autonom Agent

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

**Integrations**

- invoke N8N etc
- wenn über invoke die traces noch nicht mitgeliefert werden
    - an Message-Broker einen "Job" senden (gibt conversationID, MessageID und externeID an) und dann integriert consumer entsprechend die traces des runs

**Optimizations**

- chat service als microservice in selber struktur (nur app-core und app-chat) auslagern
    - besser skalierbar

**Frontend Entwicklung**

- Ein Design in einer FRONTEND/* mit Copilot ausarbeiten
    - mehrere Dateien, sodass man nach und nach implementieren und updaten kann
        - STRUCTURE.md (beschreibung der Projektstruktur)
        - COLOR_DESIGN.md (color theme etc)
        - PAGES.md (beschreibung)
        - PAGES/*
            - LOGIN_PAGE.md
            - ...
        - COMPONENTS/*
            - BUTTON.md
            - TOAST.md
            - MESSAGEBOX.md (so rechts oben als alert)
    - dieses design sehr gut beschreiben und mit Copilot in the Loop ausarbeiten
    - anschließend das Desgin mit Copilot erstellen, inkl. BE-Transaktionen

- Design ausarbeiten
    - hier fotos suchen / pinterest / design sachen
    - Design
        - Colors (Dark- und Light-Mode)
            - vieleicht Schwarz und Gift-Grün? sowas in die richtig
            - fest definierten Farb-Satz, den man ggf anpassne kann (nicht zu viele)
            - über ENV soll man sagen, welches Color-Theme man nutzen möchte
                - also Color-Theme dynamisch halten (und immer Light-Dark-Mode)
    - Layout Design
        - Header (rechts oben mit Profil + Tenants als DropDown + notifications icon)
    - Eine Best-Practice Projekt-Struktur aufbauen
        - Copilot-Instructions bauen
        - Struktur aufbauen
    - Components bauen
        - Framework mit Copilot auswählen
        - Standard Components aufbauen
            - Buttons
            - Toasts
                - types: DELETE, ?
            - DropDowns (searchable)
            - checkboxen
            - Toggle Buttons
            - TextBoxen
            - ???
        - LayoutComponents abuen
            - Sidebar
            - Header
            - MainLayout
    - Pages bauen
        - LoginPage
            - beim einloggen: wenn Benutzer keinen Tenant hat -> wird ein "default" erstellt
        - Dashboard Page
            - Kontept entwickeln
                - meine letzten Konversationen
                - meine letzten Applications
                - meine letzten Autonomen Agents
                - meine Favoriten (Applications, AutoAgents)
        - CredentialsPage
            - Liste
            - Details
                - Access (Als OverLay)
            - Form + Test-Connection
        - TenantSettings
            - IAM
                - Tenant Access
                - Custom Groups
        - ApplicationsPage
            - Liste
            - Details
                - Access (Als Overlay)
                - Liste Conversations
                    - Details / Messages
                        - Access
                        - Messages
            - Form + Credentials direkt dort anlegbar (mit default namen)
        - ConversationsPage
            - als Komponente -> einmal unter Application
            - einmal als page um alle conversations zu sehen
        - Autonomous Agents
            - Liste
            - Details
            - Tracing History
                - Liste
                - Details
        - Widget Designer
            - hier nur Placeholder
