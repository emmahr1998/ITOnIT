import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { useAuth } from "./useAuth";

/**
 * Platform-console equivalent of ProtectedRoute (see that file). Gates
 * every /platform/* page behind an authenticated System Administrator
 * instead of a tenant user - a deliberately separate guard rather than an
 * allowedRoles prop on ProtectedRoute, since the two consoles redirect
 * unauthenticated visitors to different login screens (/platform/login
 * here, /login there) and send a disallowed role to a different home
 * (/dashboard here is the *rejection* target, not the login target - see
 * ProtectedRoute's own System-Administrator redirect for the reverse case).
 * That split keeps both directions redirect-loop-free: neither guard's
 * unauthenticated target is ever wrapped by the other guard.
 */
export function PlatformProtectedRoute({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();

  if (status === "loading") {
    return <LoadingSpinner label="Checking your session..." />;
  }

  if (status === "unauthenticated" || !user) {
    return <Navigate to="/platform/login" replace />;
  }

  if (user.role !== "System Administrator") {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
