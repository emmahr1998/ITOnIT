# ITOnIT — Frontend

React + TypeScript single-page app for the ITOnIT ticket system. See the
[repository root README](../README.md) for the full project overview,
architecture, environment variables, default accounts, and how to run the
backend this app talks to — this file only covers frontend-specific detail.

## Stack

React 19, TypeScript (`strict: true`), Vite, React Router v7, Axios,
lucide-react icons, CSS Modules (no UI/styling library). Linted with `oxlint`.

## Commands

```bash
npm install
npm run dev       # start the Vite dev server (default http://localhost:5173)
npm run build     # tsc -b && vite build — type-checks, then produces dist/
npm run lint      # oxlint
npm run preview   # serve the production build locally
```

## Environment variables

Copy `.env.example` to `.env.development` (already present with a sensible
local default) or `.env.local` and set:

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the FastAPI backend, no trailing slash (e.g. `http://localhost:8000`) |

Vite only exposes variables prefixed `VITE_` to client code, and every such
variable ends up in the built JS bundle — never put a secret in a `VITE_*`
variable.

## Structure

```
src/
├── api/          Axios client + one module per backend resource (tickets.ts, users.ts, ...)
├── auth/         AuthContext/AuthProvider (login/register/logout, token bootstrap), ProtectedRoute
├── components/
│   ├── common/   Shared UI primitives (StatCard, Modal, EmptyState, badges, ...)
│   ├── admin/    Admin-only widgets (CreateUserModal, TitleResourceManager, ...)
│   ├── layout/   AppLayout, Sidebar, NavBar
│   └── tickets/  Ticket-detail sub-sections (comments, attachments, history, sidebar)
├── pages/        One component per route (Dashboard, TicketList, Login, Register, Landing, admin/*)
├── router/       AppRouter — all route definitions and role gating
├── types/        TypeScript types mirroring the backend's Pydantic schemas
├── utils/        Small pure helpers (e.g. high-priority ticket calculation)
└── styles/       global.css — design tokens and shared classes (buttons, fields, tables)
```

Every page/component pairs with its own `*.module.css` file (CSS Modules,
scoped class names) rather than a global stylesheet or a component library.
