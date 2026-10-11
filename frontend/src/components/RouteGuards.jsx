import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuthStore } from "../store/authStore";

function FullPageLoader() {
  return <div className="full-page-loader">Loading...</div>;
}

// Only logged-in users may see the nested routes.
export function ProtectedRoute() {
  const status = useAuthStore((state) => state.status);
  const location = useLocation();

  if (status === "loading") return <FullPageLoader />;
  if (status === "unauthenticated") {
    // remember where the user wanted to go, so login can send them back
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

// Login and signup are only for logged-out users.
export function PublicOnlyRoute() {
  const status = useAuthStore((state) => state.status);
  const location = useLocation();

  if (status === "loading") return <FullPageLoader />;
  if (status === "authenticated") {
    return <Navigate to={location.state?.from ?? "/dashboard"} replace />;
  }
  return <Outlet />;
}
