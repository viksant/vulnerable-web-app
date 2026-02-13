import { Navigate } from "react-router-dom";
import { isAuthenticated, getCurrentUser } from "../utils/auth";

/**
 * Route guard that redirects to /login if user is not authenticated.
 * Optionally restricts access to specific roles.
 *
 * @param {object} props
 * @param {React.ReactNode} props.children - The protected content.
 * @param {string[]} [props.roles] - Allowed roles. If empty, any authenticated user is allowed.
 */
export default function ProtectedRoute({ children, roles = [] }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  if (roles.length > 0) {
    const user = getCurrentUser();
    if (!roles.includes(user?.role)) {
      return <Navigate to="/" replace />;
    }
  }

  return children;
}
