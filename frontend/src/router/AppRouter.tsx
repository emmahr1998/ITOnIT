import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { PlatformLayout } from "../components/platform/PlatformLayout";
import { ProtectedRoute } from "../auth/ProtectedRoute";
import { PlatformProtectedRoute } from "../auth/PlatformProtectedRoute";
import { DashboardPage } from "../pages/DashboardPage";
import { LandingPage } from "../pages/LandingPage";
import { LoginPage } from "../pages/LoginPage";
import { RegisterPage } from "../pages/RegisterPage";
import { TicketListPage } from "../pages/TicketListPage";
import { TicketDetailPage } from "../pages/TicketDetailPage";
import { CreateTicketPage } from "../pages/CreateTicketPage";
import { UsersPage } from "../pages/admin/UsersPage";
import { CategoriesPage } from "../pages/admin/CategoriesPage";
import { DepartmentsPage } from "../pages/admin/DepartmentsPage";
import { LocationsPage } from "../pages/admin/LocationsPage";
import { PrioritiesPage } from "../pages/admin/PrioritiesPage";
import { InventoryPage } from "../pages/admin/InventoryPage";
import { InventoryCategoryPage } from "../pages/admin/InventoryCategoryPage";
import { CompanySettingsPage } from "../pages/admin/CompanySettingsPage";
import { AboutPage } from "../pages/AboutPage";
import { PlatformLoginPage } from "../pages/platform/PlatformLoginPage";
import { PlatformDashboardPage } from "../pages/platform/PlatformDashboardPage";
import { PlatformCompaniesPage } from "../pages/platform/PlatformCompaniesPage";
import { PlatformCompanyDetailPage } from "../pages/platform/PlatformCompanyDetailPage";
import { PlatformCreateCompanyPage } from "../pages/platform/PlatformCreateCompanyPage";

// The Electron build (VITE_APP_MODE=desktop, see companyStore.ts) enters at the
// company login instead of the public marketing site; the web build is unchanged.
const IS_DESKTOP = import.meta.env.VITE_APP_MODE === "desktop";

const CREATE_TICKET_ROLES = ["Employee", "Company Administrator"] as const;
const ADMIN_ROLES = ["Company Administrator"] as const;
// Inventory pages are read-only for Technician (see InventoryPage/
// InventoryCategoryPage's own canManage gating) but fully off-limits to
// Employee - matching the backend's _VIEW_ROLES on both /inventory-items
// and /inventory-categories.
const INVENTORY_VIEW_ROLES = ["Company Administrator", "Technician"] as const;

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={IS_DESKTOP ? <Navigate to="/login" replace /> : <LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/platform/login" element={<PlatformLoginPage />} />

        <Route
          element={
            <PlatformProtectedRoute>
              <PlatformLayout />
            </PlatformProtectedRoute>
          }
        >
          <Route path="/platform" element={<PlatformDashboardPage />} />
          <Route path="/platform/companies" element={<PlatformCompaniesPage />} />
          <Route path="/platform/companies/new" element={<PlatformCreateCompanyPage />} />
          <Route path="/platform/companies/:companyId" element={<PlatformCompanyDetailPage />} />
        </Route>

        <Route
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/tickets" element={<TicketListPage />} />
          <Route path="/tickets/:ticketId" element={<TicketDetailPage />} />

          <Route
            path="/tickets/new"
            element={
              <ProtectedRoute allowedRoles={[...CREATE_TICKET_ROLES]}>
                <CreateTicketPage />
              </ProtectedRoute>
            }
          />

          <Route
            path="/admin/users"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <UsersPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/categories"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <CategoriesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/departments"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <DepartmentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/locations"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <LocationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/priorities"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <PrioritiesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/inventory"
            element={
              <ProtectedRoute allowedRoles={[...INVENTORY_VIEW_ROLES]}>
                <InventoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/inventory-categories"
            element={
              <ProtectedRoute allowedRoles={[...INVENTORY_VIEW_ROLES]}>
                <InventoryCategoryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin/company-settings"
            element={
              <ProtectedRoute allowedRoles={[...ADMIN_ROLES]}>
                <CompanySettingsPage />
              </ProtectedRoute>
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
