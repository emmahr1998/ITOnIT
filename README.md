# ITOnIT

ITOnIT is a full-stack IT management system developed as a Computer Science final project.

The idea behind the project is to make everyday IT operations easier to manage. Instead of handling support requests through emails, messages, and spreadsheets, ITOnIT provides one place where employees can report problems, technicians can manage their assigned work, and administrators can oversee the organization's IT operations.

The system includes ticket management, IT inventory tracking, user management, and reporting. It also supports multiple organizations, with each company having its own users, tickets, and inventory.

ITOnIT is available as both a web application and a Windows desktop application.

## Main Features

### Ticket Management
- Create and manage IT support tickets.
- Assign tickets to technicians.
- Track ticket status, priority, and category.
- Add comments and file attachments.
- View ticket history and changes.
- Filter and search tickets.

### Inventory Management
- Manage IT equipment and stock.
- Track individual assets and bulk inventory.
- Assign and reserve equipment for support tickets.
- Record inventory transactions.
- Monitor available quantities, low stock, and warranty information.

### Users and Permissions

ITOnIT uses role-based access control (RBAC). Each user has access to the features relevant to their responsibilities.

| Role | Responsibilities |
|---|---|
| Employee | Create tickets and follow their progress |
| Technician | Manage assigned tickets, update statuses, and work with inventory |
| Company Administrator | Manage users, tickets, inventory, and company settings |
| System Administrator | Manage organizations through a separate platform administration interface |

### Multi-Company Support

ITOnIT was designed to support multiple organizations using the same application.

Each company has its own workspace, and data is separated between organizations. Users can only access information belonging to their company, according to their permissions.

### Dashboard and Reports

The application provides dashboards with information such as ticket status, priorities, assigned work, and inventory statistics.

The information displayed depends on the user's role.

### Web and Desktop Applications

The frontend is built with React and TypeScript.

The desktop version uses Electron and shares the same frontend, allowing users to access ITOnIT through a Windows application.

Both versions communicate with the FastAPI backend.

## Technologies

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React, TypeScript |
| Database | Microsoft SQL Server |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| Authentication | JWT, Argon2 |
| Desktop Application | Electron |
| API Communication | REST API, Axios |
| Frontend Build Tool | Vite |
| Testing | Pytest |
| Version Control | Git, GitHub |

## Project Structure

```text
ITOnIT/
├── backend/             FastAPI application
│   ├── app/
│   │   ├── api/         API endpoints
│   │   ├── models/      Database models
│   │   ├── schemas/     Request and response schemas
│   │   ├── services/    Business logic
│   │   ├── repositories/
│   │   └── core/        Configuration and security
│   ├── alembic/         Database migrations
│   └── tests/           Backend tests
│
├── frontend/            React and TypeScript application
│   └── src/
│       ├── api/
│       ├── components/
│       ├── pages/
│       ├── auth/
│       └── styles/
│
├── desktop/             Electron desktop application
│
└── docs/                Project documentation
```

## Getting Started

### Requirements

Before running the project, make sure you have:

- Python 3.12 or newer
- Node.js 20 or newer
- Microsoft SQL Server (Express is supported)
- Microsoft ODBC Driver for SQL Server
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/emmahr1998/ITOnIT.git
cd ITOnIT
```

### 2. Backend Setup

Open a terminal in the backend directory:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Create a `.env` file based on `.env.example` and configure your database connection and application settings.

Make sure SQL Server is running and the database exists before applying migrations.

### 3. Database Setup

Create the database in SQL Server:

```sql
CREATE DATABASE ITOnIT;
```

Apply the database migrations:

```bash
python -m alembic upgrade head
```

For initial setup, the project also includes a seed script:

```bash
python -m app.scripts.seed_initial_data
```

**Note:** Apply migrations only to a database you intend to initialize or update. For an existing database, review the migration history and any required data-repair steps first.

### 4. Run the Backend

From the `backend` directory:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

`http://127.0.0.1:8000`

FastAPI also provides interactive API documentation through Swagger:

`http://127.0.0.1:8000/docs`

### 5. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
```

Configure the backend URL in your frontend environment:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Start the development server:

```bash
npm run dev
```

Open:

`http://localhost:5173`

## Desktop Application

The Windows desktop application is built with Electron and uses the same React frontend.

To run it in development mode, first start the backend.

From the `frontend` directory:

```bash
npm run dev:desktop
```

Then open another terminal in the `desktop` directory:

```bash
npm install
npm run dev
```

To build the Windows application:

```bash
npm run dist
```

The desktop application requires a running backend and database connection. They are not included in the Electron installer.

## Testing

The backend uses Pytest for automated testing.

Run the tests from the `backend` directory:

```bash
pytest
```

Check backend code quality:

```bash
ruff check app tests scripts
```

For frontend checks, run:

```bash
cd frontend
npx tsc -b
npm run lint
npm run build
```

## Security

The project includes several security measures:

- JWT-based authentication with access and refresh tokens.
- Password hashing using Argon2.
- Role-based permissions.
- Company-level data isolation.
- Protected API endpoints.
- Separate platform administration.
- Input validation using Pydantic.

These measures are intended to restrict access to the appropriate users and organizations.

## Documentation

Additional technical documentation is available in the [`docs/`](docs/) directory.

Some useful files:

- [`BACKEND_ARCHITECTURE.md`](docs/BACKEND_ARCHITECTURE.md) — Backend architecture and design.
- [`BACKEND_API_GUIDE.md`](docs/BACKEND_API_GUIDE.md) — API endpoints and permissions.
- [`database-design.md`](docs/database-design.md) — Database structure and relationships.
- [`BACKEND_DIAGRAMS.md`](docs/BACKEND_DIAGRAMS.md) — Architecture and flow diagrams.
- [`TECH_DEBT.md`](docs/TECH_DEBT.md) — Known limitations and future improvements.

## Project Status

ITOnIT was developed as an academic project to demonstrate the design and implementation of a full-stack application.

The project covers backend development, frontend development, database design, authentication, role-based permissions, multi-tenant architecture, and desktop integration.

Some features and deployment configurations are intended for demonstration and development purposes rather than unrestricted production use.

## Authors

Developed as a Computer Science final project.
