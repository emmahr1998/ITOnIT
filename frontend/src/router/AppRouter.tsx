import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "../components/layout/AppLayout";
import { ProtectedRoute } from "../auth/ProtectedRoute";
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
import { AboutPage } from "../pages/AboutPage";

const CREATE_TICKET_ROLES = ["Employee", "Company Administrator"] as const;
const ADMIN_ROLES = ["Company Administrator"] as const;

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

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
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
