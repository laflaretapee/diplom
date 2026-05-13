import type { Role } from './types';

const ROLE_PATHS: Record<Role, string[]> = {
  super_admin: [
    '/dashboard',
    '/assistant',
    '/dishes',
    '/warehouse',
    '/documents',
    '/kanban',
    '/franchisee',
    '/orders',
    '/orders/history',
    '/diary',
  ],
  franchisee: [
    '/dashboard',
    '/assistant',
    '/warehouse',
    '/documents',
    '/kanban',
    '/orders',
    '/orders/history',
    '/diary',
  ],
  point_manager: ['/orders', '/warehouse', '/documents', '/kanban', '/orders/history', '/queue', '/diary'],
  staff: ['/orders', '/documents', '/orders/history', '/queue', '/diary'],
};

export function getOrdersRouteForRole(role: Role | null): string {
  if (role === 'point_manager' || role === 'staff') {
    return '/queue';
  }

  return '/orders/history';
}

export function getDefaultRouteForRole(role: Role | null): string {
  if (role === 'point_manager' || role === 'staff') {
    return '/orders';
  }

  return '/dashboard';
}

export function canAccessPath(role: Role | null, pathname: string): boolean {
  if (!role) {
    return false;
  }

  const normalizedPath = pathname === '/' ? pathname : pathname.replace(/\/+$/, '');
  return ROLE_PATHS[role].some((allowedPath) => {
    if (normalizedPath === allowedPath) {
      return true;
    }

    return normalizedPath.startsWith(`${allowedPath}/`);
  });
}

export function resolvePostLoginPath(
  requestedPath: string | null | undefined,
  role: Role,
): string {
  if (!requestedPath || requestedPath === '/' || requestedPath === '/login') {
    return getDefaultRouteForRole(role);
  }

  if (requestedPath === '/orders') {
    return getOrdersRouteForRole(role);
  }

  return canAccessPath(role, requestedPath) ? requestedPath : getDefaultRouteForRole(role);
}
