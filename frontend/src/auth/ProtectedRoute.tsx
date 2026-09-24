import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import type { Role } from "../types/auth";
import { useAuth } from "./useAuth";

interface ProtectedRouteProps {
  children: ReactNode;
  /**
   * If given, only these roles may view this route - anyone authenticated
   * but not in this list is redirected to the dashboard instead of the
   * page they asked for. Omit to allow any authenticated user through.
   *
   * No page currently passes this prop (there's only one shared dashboard
   * so far), but the mechanism is ready for role-specific pages added in
   * a later phase.
   */
  allowedRoles?: Role[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { user, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingSpinner label="Checking your session..." />;
  }

  if (status === "unauthenticated" || !user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // The platform-level System Administrator has no tenant home at all - every
  // page behind this guard assumes a company_id the backend will never give
  // that account (see get_current_company_id's docstring), so it's sent to
  // its own console unconditionally, regardless of allowedRoles. This is
  // checked before allowedRoles below, not folded into it, since no tenant
  // route should ever need to opt this role back in.
  if (user.role === "System Administrator") {
    return <Navigate to="/platform" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
