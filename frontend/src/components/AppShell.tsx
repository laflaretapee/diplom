import {
  AppstoreOutlined,
  DashboardOutlined,
  InboxOutlined,
  LogoutOutlined,
  OrderedListOutlined,
  RobotOutlined,
  SolutionOutlined,
} from '@ant-design/icons';
import { Button, Layout, Menu, Space, Tag, Typography, theme } from 'antd';
import type { MenuProps } from 'antd';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { queryClient } from '../app/queryClient';
import { roleMeta } from '../auth/roleMeta';
import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';

const menuItemsByRole: Record<Role, MenuProps['items']> = {
  super_admin: [
    { key: '/dashboard', icon: <DashboardOutlined />, label: 'Дашборд' },
    { key: '/assistant', icon: <RobotOutlined />, label: 'ИИ-аналитик' },
    { key: '/dishes', icon: <AppstoreOutlined />, label: 'Блюда' },
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/franchisee', icon: <OrderedListOutlined />, label: 'Франчайзи' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'Заказы' },
  ],
  franchisee: [
    { key: '/dashboard', icon: <DashboardOutlined />, label: 'Дашборд' },
    { key: '/assistant', icon: <RobotOutlined />, label: 'ИИ-аналитик' },
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'Заказы' },
  ],
  point_manager: [
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'История заказов' },
    { key: '/queue', icon: <OrderedListOutlined />, label: 'Очередь' },
  ],
  staff: [
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'История заказов' },
    { key: '/queue', icon: <OrderedListOutlined />, label: 'Очередь' },
  ],
};

export function AppShell() {
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const location = useLocation();
  const name = useAuthStore((state) => state.name);
  const role = useAuthStore((state) => state.role);
  const logout = useAuthStore((state) => state.logout);

  if (!role) {
    return <Navigate to="/login" replace />;
  }

  const meta = roleMeta[role];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
  };

  const handleLogout = async () => {
    await logout();
    queryClient.clear();
    navigate('/login', { replace: true });
  };

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      <Layout.Sider
        breakpoint="lg"
        collapsedWidth={0}
        theme="dark"
        width={264}
        style={{
          background: '#0E0E0E',
          borderRight: '1px solid rgba(79, 69, 56, 0.35)',
        }}
      >
        <div style={{ padding: 24, color: '#ffffff' }}>
          <Space align="center" size={12}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                display: 'grid',
                placeItems: 'center',
                background: 'linear-gradient(135deg, #FFD598 0%, #E8B86D 100%)',
                color: '#281800',
                boxShadow: '0 10px 30px rgba(232, 184, 109, 0.18)',
              }}
            >
              <DashboardOutlined />
            </div>
            <div>
              <Typography.Title level={3} style={{ color: '#E8B86D', margin: 0 }}>
                Japonica
              </Typography.Title>
              <Typography.Text
                style={{
                  color: 'rgba(211, 196, 179, 0.68)',
                  fontSize: 10,
                  letterSpacing: '0.18em',
                  textTransform: 'uppercase',
                }}
              >
                CRM система
              </Typography.Text>
            </div>
          </Space>
          <Typography.Text
            style={{
              color: 'rgba(229, 226, 225, 0.72)',
              display: 'block',
              marginTop: 18,
            }}
          >
            {meta.focus}
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItemsByRole[role]}
          onClick={handleMenuClick}
          style={{
            background: '#0E0E0E',
            borderInlineEnd: 'none',
          }}
        />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: 'rgba(14, 14, 14, 0.72)',
            borderBottom: `1px solid rgba(79, 69, 56, 0.35)`,
            backdropFilter: 'blur(18px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingInline: 24,
          }}
        >
          <Space size={12} wrap>
            <Tag
              color="default"
              style={{
                marginInlineEnd: 0,
                background: '#201F1F',
                borderColor: '#4F4538',
                color: meta.accent,
                fontFamily: '"JetBrains Mono", monospace',
              }}
            >
              {meta.label}
            </Tag>
            <Typography.Text strong style={{ color: '#E5E2E1' }}>
              {name ?? 'Неизвестный пользователь'}
            </Typography.Text>
          </Space>
          <Space size={12}>
            <Typography.Text style={{ color: '#BFB6A8' }}>{meta.description}</Typography.Text>
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={() => {
                void handleLogout();
              }}
              style={{ color: '#FFB4AB' }}
            >
              Выйти
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content
          style={{
            padding: 24,
            background:
              'radial-gradient(circle at top left, rgba(232, 184, 109, 0.08), transparent 28%), linear-gradient(180deg, #131313 0%, #0E0E0E 100%)',
          }}
        >
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
