import { LockOutlined, MailOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Form, Input, Row, Space, Spin, Typography } from 'antd';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';

import { loginWithSession } from '../auth/api';
import { resolvePostLoginPath } from '../auth/routes';
import { useAuthStore } from '../auth/store';
import type { LoginRequest } from '../auth/types';
import { useIsMobileLayout } from '../hooks/useIsMobileLayout';

type LoginFormValues = LoginRequest;

function getAuthErrorMessage(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeError = error as { response?: { data?: { detail?: unknown } }; message?: unknown };
    const detail = maybeError.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (typeof maybeError.message === 'string' && maybeError.message.trim()) {
      return maybeError.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Не удалось выполнить вход. Проверьте логин и пароль.';
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobileLayout();
  const status = useAuthStore((state) => state.status);
  const token = useAuthStore((state) => state.token);
  const role = useAuthStore((state) => state.role);
  const login = useAuthStore((state) => state.login);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
  const isAuthenticated = status === 'authenticated' && Boolean(token) && Boolean(role);

  if (status === 'bootstrapping') {
    return (
      <Row justify="center" align="middle" style={{ minHeight: '100vh', padding: 24 }}>
        <Spin size="large" tip="Проверяем сессию" />
      </Row>
    );
  }

  if (isAuthenticated && role) {
    return <Navigate to={resolvePostLoginPath(from, role)} replace />;
  }

  const handleFinish = async (values: LoginFormValues) => {
    setSubmitError(null);
    setIsSubmitting(true);

    try {
      const response = await loginWithSession({
        email: values.email.trim(),
        password: values.password,
      });

      login(response);
      navigate(resolvePostLoginPath(from, response.user.role), { replace: true });
    } catch (error) {
      setSubmitError(getAuthErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Row justify="center" align="middle" style={{ minHeight: '100vh', padding: 24 }}>
      <Col xs={24} sm={22} md={18} lg={12} xl={9}>
        <Card
          bordered={false}
          style={{
            boxShadow: '0 18px 56px rgba(0, 0, 0, 0.28)',
            background: '#161616',
            border: '1px solid #2A2A2A',
          }}
          styles={{ body: { padding: isMobile ? 20 : 24 } }}
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Typography.Title level={isMobile ? 3 : 2} style={{ marginBottom: 0, color: '#E5E2E1' }}>
              Вход в Джейсан
            </Typography.Title>
            <Typography.Text style={{ color: '#BFB6A8' }}>
              Используйте свою рабочую учётную запись. После входа система откроет раздел,
              соответствующий вашей роли.
            </Typography.Text>
            {submitError ? <Alert type="error" message={submitError} showIcon /> : null}
            <Form<LoginFormValues>
              layout="vertical"
              initialValues={{ email: '', password: '' }}
              onValuesChange={() => {
                if (submitError) {
                  setSubmitError(null);
                }
              }}
              onFinish={handleFinish}
            >
              <Form.Item
                label="Электронная почта"
                name="email"
                rules={[
                  { required: true, message: 'Введите электронную почту' },
                  { type: 'email', message: 'Введите корректный адрес электронной почты' },
                ]}
              >
                <Input prefix={<MailOutlined />} placeholder="name@company.ru" />
              </Form.Item>
              <Form.Item
                label="Пароль"
                name="password"
                rules={[{ required: true, message: 'Введите пароль' }]}
              >
                <Input.Password prefix={<LockOutlined />} placeholder="Введите пароль" />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<LockOutlined />}
                  block
                  loading={isSubmitting}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Входим...' : 'Войти'}
                </Button>
              </Form.Item>
            </Form>
          </Space>
        </Card>
      </Col>
    </Row>
  );
}
