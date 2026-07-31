# ITOnIT Backend — Diagrams

All diagrams are Mermaid, generated from the actual code (models, routes, services) — not
guessed. See `docs/BACKEND_ARCHITECTURE.md` for the file/function references behind each one.

## 1. Overall architecture

```mermaid
flowchart TD
    Client["Client / React frontend / Swagger"]

    subgraph FastAPI["FastAPI app (app/main.py)"]
        Routes["Routes\napp/api/routes/*.py"]
        Deps["Dependencies\napp/dependencies/*.py\n(auth, roles, DB session)"]
        Schemas["Pydantic schemas\napp/schemas/*.py"]
    end

    subgraph Domain["Business logic"]
        Services["Services\napp/services/*.py\n(rules, transactions, exceptions)"]
        Repos["Repositories\napp/repositories/*.py\n(SQLAlchemy queries)"]
    end

    subgraph Data["Data layer"]
        Models["SQLAlchemy models\napp/models/*.py"]
        DB[("SQL Server")]
        Disk[("Local disk\nstorage/attachments/")]
    end

    Client -->|HTTP request| Routes
    Routes --> Deps
    Deps -->|401 / 403| Client
    Routes --> Schemas
    Schemas -->|422 on invalid input| Client
    Routes --> Services
    Services --> Repos
    Repos --> Models
    Models --> DB
    Services -->|file bytes| Disk
    Services -->|ORM objects| Schemas
    Schemas -->|JSON response| Client
```

## 2. Authentication flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as auth.py route
    participant A as AuthService
    participant S as core/security.py
    participant DB as SQL Server (users table)

    C->>R: POST /auth/login {username, password}
    R->>A: login(username, password)
    A->>DB: get_by_username_or_email(username)
    DB-->>A: User row (or none)
    A->>S: verify_password(password, user.password_hash)
    S-->>A: True / False
    alt user not found, wrong password, or inactive
        A-->>R: raise InvalidCredentialsError
        R-->>C: 401 Invalid username or password
    else success
        A->>S: create_access_token(sub=user.id)
        A->>S: create_refresh_token(sub=user.id)
        S-->>A: access token, refresh token
        A-->>R: TokenResponse
        R-->>C: 200 {access, refresh, token_type}
    end

    Note over C: later requests
    C->>R: GET /auth/me  (Authorization: Bearer <access>)
    R->>S: decode_access_token(token)
    S-->>R: TokenPayload (sub, type=access)
    R->>DB: get_by_id(sub)
    DB-->>R: User row
    R-->>C: 200 CurrentUserResponse

    Note over C: refreshing
    C->>R: POST /auth/refresh {refresh}
    R->>A: refresh_access_token(refresh)
    A->>S: decode_refresh_token(refresh)
    alt type != "refresh", expired, or user inactive/missing
        S-->>A: raises
        A-->>R: raise InvalidRefreshTokenError
        R-->>C: 401 Invalid or expired refresh token
    else success
        A->>S: create_access_token(sub=user.id)
        S-->>A: new access token
        A-->>R: RefreshResponse
        R-->>C: 200 {access, token_type}
    end
```

## 3. Database relationships (ERD)

```mermaid
erDiagram
    ROLES ||--o{ USERS : "has role"
    DEPARTMENTS ||--o{ USERS : "has member"
    USERS ||--o{ TICKETS : "created_by"
    USERS ||--o{ TICKETS : "assigned_technician"
    CATEGORIES ||--o{ TICKETS : "classifies"
    PRIORITIES ||--o{ TICKETS : "prioritizes"
    LOCATIONS ||--o{ TICKETS : "optionally locates"
    TICKETS ||--o{ COMMENTS : "has"
    TICKETS ||--o{ ATTACHMENTS : "has"
    TICKETS ||--o{ TICKET_HISTORY : "has"
    USERS ||--o{ COMMENTS : "authors"
    USERS ||--o{ ATTACHMENTS : "uploads"
    USERS ||--o{ TICKET_HISTORY : "changes"

    ROLES {
        int id PK
        varchar name UK
        varchar description
    }
    DEPARTMENTS {
        int id PK
        varchar title UK
        datetime created_at
        datetime updated_at
    }
    PRIORITIES {
        int id PK
        varchar title UK
        datetime created_at
        datetime updated_at
    }
    LOCATIONS {
        int id PK
        varchar title UK
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    CATEGORIES {
        int id PK
        varchar name UK
        varchar description
        boolean is_active
        datetime created_at
    }
    USERS {
        int id PK
        varchar username UK
        varchar first_name
        varchar last_name
        varchar email UK
        varchar password_hash
        varchar phone_number
        varchar theme
        int role_id FK
        int department_id FK
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    TICKETS {
        int id PK
        varchar ticket_number UK
        varchar title
        text description
        int location_id FK
        varchar status
        int priority_id FK
        int category_id FK
        int created_by_user_id FK
        int assigned_technician_id FK
        datetime resolved_at
        datetime closed_at
        datetime created_at
        datetime updated_at
    }
    COMMENTS {
        int id PK
        int ticket_id FK
        int author_user_id FK
        text content
        datetime created_at
        datetime updated_at
    }
    ATTACHMENTS {
        int id PK
        int ticket_id FK
        int uploaded_by_user_id FK
        varchar original_filename
        varchar stored_filename
        varchar file_path
        varchar content_type
        int file_size
        datetime created_at
    }
    TICKET_HISTORY {
        int id PK
        int ticket_id FK
        int changed_by_user_id FK
        varchar field_name
        varchar old_value
        varchar new_value
        datetime created_at
    }
```

## 4. Ticket lifecycle (status state machine)

```mermaid
stateDiagram-v2
    [*] --> NEW : POST /ticket-new
    NEW --> ASSIGNED : PATCH /tickets/{id}/assign\n(auto-transition, Manager/Admin)
    ASSIGNED --> IN_PROGRESS : PATCH /tickets/{id}/status\n(Technician/Manager/Admin)
    IN_PROGRESS --> WAITING_FOR_EMPLOYEE : PATCH .../status
    WAITING_FOR_EMPLOYEE --> IN_PROGRESS : PATCH .../status
    IN_PROGRESS --> RESOLVED : PATCH .../status\n(sets resolved_at)
    RESOLVED --> CLOSED : PATCH .../status\n(sets closed_at)
    CLOSED --> [*] : terminal - no reopening in current code
```

## 5. Ticket lifecycle (full sequence, one worked example)

```mermaid
sequenceDiagram
    participant Emp as Employee (John)
    participant Mgr as Manager
    participant Tech as Technician
    participant API as FastAPI routes
    participant TS as TicketService
    participant HS as HistoryService
    participant DB as SQL Server

    Emp->>API: POST /ticket-new
    API->>TS: create_ticket_new(John, payload)
    TS->>TS: _generate_ticket_number() → IT-2026-000001
    TS->>DB: INSERT ticket (status=NEW)
    TS->>HS: record(ticket_created)
    HS->>DB: INSERT ticket_history
    TS->>DB: COMMIT
    API-->>Emp: 201 ticket

    Emp->>API: POST /tickets/{id}/attachments (file)
    API->>DB: INSERT attachment metadata
    API->>HS: record(attachment_added)
    Note over API: physical file saved to storage/attachments/

    Mgr->>API: PATCH /tickets/{id}/assign
    API->>TS: assign_technician(Mgr, id, tech_id)
    TS->>DB: UPDATE assigned_technician_id
    TS->>HS: record(assigned_technician)
    TS->>TS: status NEW → ASSIGNED (auto)
    TS->>HS: record(status)
    TS->>DB: COMMIT

    Tech->>API: PATCH /tickets/{id}/status {IN_PROGRESS}
    API->>TS: change_status(Tech, id, IN_PROGRESS)
    TS->>DB: UPDATE status
    TS->>HS: record(status)
    TS->>DB: COMMIT

    Tech->>API: POST /tickets/{id}/comments
    API->>HS: record(comment_added)

    Tech->>API: PATCH /tickets/{id}/status {RESOLVED}
    API->>TS: change_status(Tech, id, RESOLVED)
    TS->>DB: UPDATE status, resolved_at
    TS->>HS: record(status)

    Mgr->>API: PATCH /tickets/{id}/status {CLOSED}
    API->>TS: change_status(Mgr, id, CLOSED)
    TS->>DB: UPDATE status, closed_at
    TS->>HS: record(status)
```

## 6. Attachment upload flow

```mermaid
flowchart TD
    A["Client: POST /tickets/{id}/attachments\nmultipart file"] --> B["get_viewable_ticket\n(can this user see the ticket?)"]
    B -->|no| B1["403 / 404"]
    B -->|yes| C["AttachmentService.upload_attachment"]
    C --> D{"empty file?"}
    D -->|yes| D1["400 InvalidAttachmentError"]
    D -->|no| E{"size > MAX_ATTACHMENT_SIZE_BYTES?"}
    E -->|yes| E1["400 InvalidAttachmentError"]
    E -->|no| F{"extension in allowlist?\n.png .jpg .jpeg .pdf .txt .docx .xlsx"}
    F -->|no| F1["400 InvalidAttachmentError"]
    F -->|yes| G["StorageService.generate_stored_filename\n(uuid4 + validated extension)"]
    G --> H["StorageService.save\nwrite bytes to storage/attachments/"]
    H --> I["Create Attachment row\n(original_filename, stored_filename, size, content_type)"]
    I --> J["HistoryService.record\n(attachment_added)"]
    J --> K["db.commit()"]
    K --> L["201 AttachmentResponse\n(never exposes stored_filename/file_path)"]
```

## 7. Request-processing flow (generic, applies to every endpoint)

```mermaid
flowchart TD
    Req["HTTP request arrives"] --> Match["FastAPI matches method + path\napp/api/router.py"]
    Match --> DB["Depends(get_db)\nopens one SQLAlchemy Session"]
    DB --> Auth["Depends(get_current_user /\nget_current_active_user)\ndecodes JWT, loads User"]
    Auth -->|fail| E401["401 Unauthorized"]
    Auth --> Role["Depends(require_roles(...))\nor get_viewable_ticket"]
    Role -->|fail| E403["403 Forbidden"]
    Role --> Body["Pydantic validates request body\nagainst the route's schema"]
    Body -->|fail| E422["422 Unprocessable Entity"]
    Body --> RouteFn["Route function body runs\n(a few lines - calls one Service method)"]
    RouteFn --> Service["Service applies business rules"]
    Service -->|domain exception| Except["route's except block\nmaps it to 400/404/409"]
    Service --> Repo["Repository builds/runs SQL"]
    Repo --> SQL[("SQL Server")]
    Service -->|mutation| History["HistoryService.record (if ticket-related)"]
    Service --> Commit["db.commit()"]
    Commit --> Serialize["response_model serializes\nthe ORM object(s) to JSON"]
    Serialize --> Resp["HTTP response returned"]
    Except --> Resp
    E401 --> Resp
    E403 --> Resp
    E422 --> Resp
```
