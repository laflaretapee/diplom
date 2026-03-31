import { useEffect, useState } from 'react';
import { Button, Result, Spin, Typography } from 'antd';
import { Navigate, Outlet, createBrowserRouter, RouterProvider } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { RequireAuth } from './components/RequireAuth';
import { getDefaultRouteForRole, getOrdersRouteForRole } from './auth/routes';
import { useAuthStore } from './auth/store';
import { AIAssistantPage } from './pages/AIAssistantPage';
import { DashboardPage } from './pages/DashboardPage';
import { DishesPage } from './pages/DishesPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { FranchiseeKanbanPage } from './pages/FranchiseeKanbanPage';
import { KanbanBoardPage } from './pages/KanbanBoardPage';
import { KanbanBoardsPage } from './pages/KanbanBoardsPage';
import { LoginPage } from './pages/LoginPage';
import { OrderHistoryPage } from './pages/OrderHistoryPage';
import { OrderQueuePage } from './pages/OrderQueuePage';
import { WarehousePage } from './pages/WarehousePage';

function RouteErrorFallback() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background:
          'radial-gradient(circle at top left, rgba(232, 184, 109, 0.08), transparent 28%), linear-gradient(180deg, #131313 0%, #0E0E0E 100%)',
      }}
    >
      <Result
        status="error"
        title="Не удалось открыть раздел"
        subTitle="Попробуйте обновить страницу или вернуться на главную."
        extra={
          <Button type="primary" onClick={() => window.location.assign('/')}>
            На главную
          </Button>
        }
      />
    </div>
  );
}

function RouteRoot() {
  const bootstrap = useAuthStore((state) => state.bootstrap);
  const status = useAuthStore((state) => state.status);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let active = true;

    void bootstrap().finally(() => {
      if (active) {
        setIsReady(true);
      }
    });

    return () => {
      active = false;
    };
  }, [bootstrap]);

  if (!isReady || status === 'bootstrapping') {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          gap: 12,
          background:
            'radial-gradient(circle at top left, rgba(232, 184, 109, 0.08), transparent 28%), linear-gradient(180deg, #131313 0%, #0E0E0E 100%)',
        }}
      >
        <div style={{ display: 'grid', placeItems: 'center', gap: 12 }}>
          <Spin size="large" tip="Восстанавливаем сессию" />
          <Typography.Text style={{ color: '#BFB6A8' }}>
            Проверяем refresh-сессию и права доступа
          </Typography.Text>
        </div>
      </div>
    );
  }

  return <Outlet />;
}

function HomeRedirect() {
  const status = useAuthStore((state) => state.status);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const isAuthenticated = status === 'authenticated' && Boolean(token) && Boolean(role);

  return <Navigate to={isAuthenticated ? getDefaultRouteForRole(role) : '/login'} replace />;
}

function OrdersRedirect() {
  const status = useAuthStore((state) => state.status);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);

  if (status !== 'authenticated' || !token || !role) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to={getOrdersRouteForRole(role)} replace />;
}

const router = createBrowserRouter([
  {
    path: '/',
    element: <RouteRoot />,
    errorElement: <RouteErrorFallback />,
    children: [
      { index: true, element: <HomeRedirect /> },
      { path: 'login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <AppShell />,
            children: [
              { path: 'dashboard', element: <DashboardPage /> },
              { path: 'assistant', element: <AIAssistantPage /> },
              { path: 'dishes', element: <DishesPage /> },
              { path: 'documents', element: <DocumentsPage /> },
              { path: 'kanban', element: <KanbanBoardsPage /> },
              { path: 'kanban/:boardId', element: <KanbanBoardPage /> },
              { path: 'franchisee', element: <FranchiseeKanbanPage /> },
              { path: 'orders', element: <OrdersRedirect /> },
              { path: 'orders/history', element: <OrderHistoryPage /> },
              { path: 'queue', element: <OrderQueuePage /> },
              { path: 'warehouse', element: <WarehousePage /> },
            ],
          },
        ],
      },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
