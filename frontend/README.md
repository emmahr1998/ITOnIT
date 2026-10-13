# ITOnIT — Frontend

React + TypeScript single-page app for the ITOnIT multi-tenant ticket and
inventory system. See the [repository root README](../README.md) for the full
project overview, architecture, environment variables, default accounts, and
how to run the backend this app talks to — this file only covers
frontend-specific detail.

## Stack

React 19, TypeScript (`strict: true`), Vite, React Router v7, Axios,
lucide-react icons, CSS Modules (no UI/styling library). Linted with `oxlint`.

## Commands

```bash
npm install
npm run dev            # start the Vite dev server in web mode (default http://localhost:5173)
npm run dev:desktop    # start the Vite dev server in desktop mode (VITE_APP_MODE=desktop, strict port)
npm run build          # tsc -b && vite build — type-checks, then produces dist/ (web)
npm run build:desktop  # tsc -b && vite build --mode desktop — produces dist-desktop/, consumed by desktop/
npm run lint           # oxlint
npm run preview        # serve the production (web) build locally
```

## Web mode vs. desktop mode

The same source builds two ways, switched by `VITE_APP_MODE`:

- **Web** (`VITE_APP_MODE` unset or `web`) — `/` shows the public landing
  page; the login screen remembers the last-used company code in
  `sessionStorage` (cleared when the tab closes).
- **Desktop** (`VITE_APP_MODE=desktop`) — used only by the Electron shell in
  `desktop/`. `/` redirects straight to the company login instead of the
  public site, and the login screen remembers the last-used company code in
  `localStorage` instead (survives app restarts). The desktop shell itself —
  the Electron main process, packaging, and the `app://itonit` production
  origin — lives entirely in `desktop/`, not here; this package only produces
  the renderer bundle it loads.

## Environment variables

Copy `.env.example` to `.env.development` (already present with a sensible
local default) or `.env.local`, and set:

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the FastAPI backend, no trailing slash (e.g. `http://localhost:8000`) |
| `VITE_APP_MODE` | `web` (default/unset) or `desktop` — see above. `.env.desktop` (committed, non-secret) sets this to `desktop` for `npm run dev:desktop`/`build:desktop` |

Vite only exposes variables prefixed `VITE_` to client code, and every such
variable ends up in the built JS bundle — never put a secret in a `VITE_*`
variable.

## Structure

```
src/
├── api/          Axios client + one module per backend resource (tickets.ts, users.ts, ...)
├── auth/         AuthContext/AuthProvider (login/register/logout, token bootstrap),
│                 ProtectedRoute (tenant), PlatformProtectedRoute (System Administrator)
├── components/
│   ├── common/   Shared UI primitives (StatCard, Modal, EmptyState, badges, ...)
│   ├── admin/    Admin-only widgets (CreateUserModal, TitleResourceManager, inventory modals, ...)
│   ├── layout/   AppLayout, Sidebar, NavBar
│   └── tickets/  Ticket-detail sub-sections (comments, attachments, history, inventory, sidebar)
├── pages/        One component per route (Dashboard, TicketList, Login, Register, Landing, admin/*, platform/*)
├── router/       AppRouter — all route definitions and role gating
├── types/        TypeScript types mirroring the backend's Pydantic schemas
├── utils/        Small pure helpers (e.g. high-priority ticket calculation, warranty-expiring threshold)
└── styles/       global.css — design tokens and shared classes (buttons, fields, tables)
```

Every page/component pairs with its own `*.module.css` file (CSS Modules,
scoped class names) rather than a global stylesheet or a component library.

There is no automated component/E2E test framework for the frontend in V1 —
`tsc -b`, `oxlint`, and a full production build are its automated checks (see
the root README's "Running tests" section); UI behavior is verified manually.
