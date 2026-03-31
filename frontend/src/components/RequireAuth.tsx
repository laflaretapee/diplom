import { Spin } from 'antd';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { canAccessPath, getDefaultRouteForRole } from '../auth/routes';
import { useAuthStore } from '../auth/store';

export function RequireAuth() {
  const location = useLocation();
  const status = useAuthStore((state) => state.status);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);

  if (status === 'bootstrapping') {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <Spin size="large" tip="Восстанавливаем сессию" />
      </div>
    );
  }

  const isAuthenticated = status === 'authenticated' && Boolean(token) && Boolean(role);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!canAccessPath(role, location.pathname)) {
    return <Navigate to={getDefaultRouteForRole(role)} replace />;
  }

  return <Outlet />;
}
