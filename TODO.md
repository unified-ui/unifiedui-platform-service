# TODOs



- Identity:
    - Bekommt man die Extra-Gruppen in den Token?
    - Token-Validation
    - ID aus Token für Cache
    - Frontend -> MSAL Flow für Token

- tenant
    - CRUD
    - Gibt TenantID, ClientID und ClientSecret für Service Principal an
        - SP muss Benutzer und Gruppen lesen können
    - hier vielleicht doch eher immer mit den UserToken arbeiten? der kann doch Gruppen und so auslesen?
    - und beim anmelden einen tenant anlegen; man kann aber auch neuen anlegen

- custom_groups
    - CRUD

- Permissions
    - CRUD

- Credentials
    - CRUD

- Applications
    - CRUD
    - Config
        - N8N Connection
    - Cache

- Conversations
    - CRUD + get_messages_until (siehe agentmemory-py!)
    - invoke -> use n8n chat-model
        - wie macht man es, wenn eine rückfrage gestellt wird? geht ja in einem Workflow
