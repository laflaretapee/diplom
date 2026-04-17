import {
  AppstoreOutlined,
  DashboardOutlined,
  FileTextOutlined,
  InboxOutlined,
  LogoutOutlined,
  MenuOutlined,
  OrderedListOutlined,
  ProjectOutlined,
  RobotOutlined,
  SolutionOutlined,
} from '@ant-design/icons';
import { Button, Drawer, Layout, Menu, Space, Tag, Typography, theme } from 'antd';
import type { MenuProps } from 'antd';
import { useEffect, useState } from 'react';
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { queryClient } from '../app/queryClient';
import { roleMeta } from '../auth/roleMeta';
import { useAuthStore } from '../auth/store';
import type { Role } from '../auth/types';
import { useIsMobileLayout } from '../hooks/useIsMobileLayout';

const menuItemsByRole: Record<Role, MenuProps['items']> = {
  super_admin: [
    { key: '/dashboard', icon: <DashboardOutlined />, label: 'Дашборд' },
    { key: '/assistant', icon: <RobotOutlined />, label: 'ИИ-аналитик' },
    { key: '/dishes', icon: <AppstoreOutlined />, label: 'Блюда' },
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/documents', icon: <FileTextOutlined />, label: 'Документы' },
    { key: '/kanban', icon: <ProjectOutlined />, label: 'Канбан' },
    { key: '/franchisee', icon: <OrderedListOutlined />, label: 'Франчайзи' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'Заказы' },
  ],
  franchisee: [
    { key: '/dashboard', icon: <DashboardOutlined />, label: 'Дашборд' },
    { key: '/assistant', icon: <RobotOutlined />, label: 'ИИ-аналитик' },
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/documents', icon: <FileTextOutlined />, label: 'Документы' },
    { key: '/kanban', icon: <ProjectOutlined />, label: 'Канбан' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'Заказы' },
  ],
  point_manager: [
    { key: '/warehouse', icon: <InboxOutlined />, label: 'Склад' },
    { key: '/documents', icon: <FileTextOutlined />, label: 'Документы' },
    { key: '/kanban', icon: <ProjectOutlined />, label: 'Канбан' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'История заказов' },
    { key: '/queue', icon: <OrderedListOutlined />, label: 'Очередь' },
  ],
  staff: [
    { key: '/documents', icon: <FileTextOutlined />, label: 'Документы' },
    { key: '/orders/history', icon: <SolutionOutlined />, label: 'История заказов' },
    { key: '/queue', icon: <OrderedListOutlined />, label: 'Очередь' },
  ],
};

function resolveSelectedKey(pathname: string): string {
  if (pathname.startsWith('/kanban')) {
    return '/kanban';
  }
  if (pathname.startsWith('/documents')) {
    return '/documents';
  }
  return pathname;
}

export function AppShell() {
  const { token } = theme.useToken();
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobileLayout('lg');
  const name = useAuthStore((state) => state.name);
  const role = useAuthStore((state) => state.role);
  const logout = useAuthStore((state) => state.logout);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  if (!role) {
    return <Navigate to="/login" replace />;
  }

  const meta = roleMeta[role];

  useEffect(() => {
    setIsMenuOpen(false);
  }, [isMobile, location.pathname]);

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    setIsMenuOpen(false);
    navigate(key);
  };

  const handleLogout = async () => {
    await logout();
    queryClient.clear();
    setIsMenuOpen(false);
    navigate('/login', { replace: true });
  };

  const brandBlock = (
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
          flexShrink: 0,
        }}
      >
        <DashboardOutlined />
      </div>
      <div style={{ minWidth: 0 }}>
        <Typography.Title level={isMobile ? 5 : 3} style={{ color: '#E8B86D', margin: 0 }}>
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
  );

  const navigationMenu = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[resolveSelectedKey(location.pathname)]}
      items={menuItemsByRole[role]}
      onClick={handleMenuClick}
      style={{
        background: '#0E0E0E',
        borderInlineEnd: 'none',
      }}
    />
  );

  return (
    <Layout style={{ minHeight: '100vh', background: token.colorBgLayout }}>
      {!isMobile ? (
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
            {brandBlock}
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
          {navigationMenu}
        </Layout.Sider>
      ) : null}
      <Layout>
        <Layout.Header
          style={{
            background: 'rgba(14, 14, 14, 0.72)',
            borderBottom: `1px solid rgba(79, 69, 56, 0.35)`,
            backdropFilter: 'blur(18px)',
            display: 'flex',
            alignItems: 'stretch',
            paddingInline: isMobile ? 16 : 24,
            paddingBlock: isMobile ? 12 : 14,
            height: 'auto',
            minHeight: isMobile ? 78 : 72,
            position: 'sticky',
            top: 0,
            zIndex: 20,
          }}
        >
          <Space direction="vertical" size={isMobile ? 10 : 8} style={{ width: '100%' }}>
            <div
              style={{
                display: 'flex',
                alignItems: isMobile ? 'flex-start' : 'center',
                justifyContent: 'space-between',
                gap: 12,
                flexWrap: 'wrap',
                width: '100%',
              }}
            >
              <Space align="center" size={12} style={{ minWidth: 0 }}>
                {isMobile ? (
                  <Button
                    type="text"
                    icon={<MenuOutlined />}
                    onClick={() => setIsMenuOpen(true)}
                    style={{
                      color: '#E5E2E1',
                      border: '1px solid rgba(79, 69, 56, 0.45)',
                      background: '#181818',
                      flexShrink: 0,
                    }}
                    aria-label="Открыть меню"
                  />
                ) : null}
                {brandBlock}
              </Space>

              <Space align="center" size={8} wrap>
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
                <Button
                  type="text"
                  icon={<LogoutOutlined />}
                  onClick={() => {
                    void handleLogout();
                  }}
                  style={{ color: '#FFB4AB', paddingInline: isMobile ? 8 : 12 }}
                >
                  {isMobile ? null : 'Выйти'}
                </Button>
              </Space>
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                gap: 12,
                flexWrap: 'wrap',
                width: '100%',
              }}
            >
              <Typography.Text style={{ color: '#BFB6A8', maxWidth: isMobile ? '100%' : '70%' }}>
                {meta.description}
              </Typography.Text>
              {isMobile ? (
                <Typography.Text style={{ color: 'rgba(229, 226, 225, 0.72)' }}>
                  {meta.focus}
                </Typography.Text>
              ) : null}
            </div>
          </Space>
        </Layout.Header>
        <Layout.Content
          style={{
            padding: isMobile ? 16 : 24,
            background:
              'radial-gradient(circle at top left, rgba(232, 184, 109, 0.08), transparent 28%), linear-gradient(180deg, #131313 0%, #0E0E0E 100%)',
          }}
        >
          <Outlet />
        </Layout.Content>
      </Layout>
      <Drawer
        placement="left"
        open={isMobile && isMenuOpen}
        onClose={() => setIsMenuOpen(false)}
        closable={false}
        width={288}
        styles={{
          header: {
            padding: 16,
            background: '#0E0E0E',
            borderBottom: '1px solid rgba(79, 69, 56, 0.35)',
          },
          body: {
            padding: 0,
            background: '#0E0E0E',
          },
          content: {
            background: '#0E0E0E',
          },
        }}
        title={brandBlock}
      >
        <div style={{ padding: '0 16px 16px', borderBottom: '1px solid rgba(79, 69, 56, 0.35)' }}>
          <Typography.Text
            style={{
              color: 'rgba(229, 226, 225, 0.72)',
              display: 'block',
              marginBottom: 8,
            }}
          >
            {meta.focus}
          </Typography.Text>
          <Typography.Text style={{ color: '#BFB6A8' }}>{meta.description}</Typography.Text>
        </div>
        {navigationMenu}
        <div style={{ padding: 16, borderTop: '1px solid rgba(79, 69, 56, 0.35)' }}>
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Tag
              color="default"
              style={{
                marginInlineEnd: 0,
                background: '#201F1F',
                borderColor: '#4F4538',
                color: meta.accent,
                fontFamily: '"JetBrains Mono", monospace',
                alignSelf: 'flex-start',
              }}
            >
              {meta.label}
            </Tag>
            <Typography.Text strong style={{ color: '#E5E2E1' }}>
              {name ?? 'Неизвестный пользователь'}
            </Typography.Text>
            <Button
              danger
              block
              icon={<LogoutOutlined />}
              onClick={() => {
                void handleLogout();
              }}
            >
              Выйти
            </Button>
          </Space>
        </div>
      </Drawer>
    </Layout>
  );
}
