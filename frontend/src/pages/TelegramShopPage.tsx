import { ShoppingCartOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Empty, Form, Input, InputNumber, Select, Space, Spin, Typography } from 'antd';
import { useEffect, useState } from 'react';

import { apiClient } from '../api/client';
import { BrandLogo } from '../components/BrandLogo';

type ShopPoint = {
  id: string;
  name: string;
  address: string;
};

type ShopDish = {
  id: string;
  name: string;
  description?: string | null;
  price: string;
};

type CatalogResponse = {
  points: ShopPoint[];
  dishes: ShopDish[];
};

type CartLine = {
  dish: ShopDish;
  quantity: number;
};

type CheckoutForm = {
  point_id: string;
  name: string;
  phone: string;
  delivery_address: string;
  notes?: string;
};

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initDataUnsafe?: {
          user?: {
            id?: number;
            first_name?: string;
            last_name?: string;
            username?: string;
          };
        };
        ready?: () => void;
        expand?: () => void;
        openLink?: (url: string) => void;
      };
    };
  }
}

function money(value: string | number) {
  return `${Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
}

export function TelegramShopPage() {
  const [cart, setCart] = useState<Record<string, CartLine>>({});
  const [form] = Form.useForm<CheckoutForm>();
  const telegramUser = window.Telegram?.WebApp?.initDataUnsafe?.user;

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
  }, []);

  const catalogQuery = useQuery({
    queryKey: ['telegram-shop-catalog'],
    queryFn: async () => {
      const { data } = await apiClient.get<CatalogResponse>('/v1/shop/telegram/catalog');
      return data;
    },
  });

  const checkoutMutation = useMutation({
    mutationFn: async (values: CheckoutForm) => {
      const items = Object.values(cart).map((line) => ({
        dish_id: line.dish.id,
        quantity: line.quantity,
      }));
      const fullName =
        values.name ||
        [telegramUser?.first_name, telegramUser?.last_name].filter(Boolean).join(' ') ||
        telegramUser?.username ||
        'Клиент Telegram';
      const { data } = await apiClient.post<{
        order_id: string;
        payment_url: string;
      }>('/v1/shop/telegram/checkout', {
        point_id: values.point_id,
        customer: {
          name: fullName,
          phone: values.phone,
          delivery_address: values.delivery_address,
          telegram_id: telegramUser?.id ? String(telegramUser.id) : undefined,
        },
        items,
        notes: values.notes,
      });
      return data;
    },
    onSuccess: (data) => {
      window.Telegram?.WebApp?.openLink?.(data.payment_url);
      if (!window.Telegram?.WebApp?.openLink) {
        window.location.assign(data.payment_url);
      }
    },
  });

  const catalog = catalogQuery.data;
  const lines = Object.values(cart);
  const total = lines.reduce((sum, line) => sum + Number(line.dish.price) * line.quantity, 0);

  const setQuantity = (dish: ShopDish, quantity: number) => {
    setCart((current) => {
      const next = { ...current };
      if (quantity <= 0) {
        delete next[dish.id];
      } else {
        next[dish.id] = { dish, quantity };
      }
      return next;
    });
  };

  return (
    <div style={{ minHeight: '100vh', background: '#fcf9f8', padding: 16 }}>
      <Space direction="vertical" size={16} style={{ width: '100%', maxWidth: 760, margin: '0 auto' }}>
        <Card style={{ borderRadius: 12 }}>
          <Space direction="vertical" size={8}>
            <BrandLogo height={42} maxWidth={220} />
            <Typography.Text style={{ color: '#4f4538' }}>
              Меню доставки в Telegram
            </Typography.Text>
          </Space>
        </Card>

        {catalogQuery.isLoading ? (
          <Card><Spin /></Card>
        ) : catalogQuery.isError ? (
          <Alert type="error" message="Не удалось загрузить меню" showIcon />
        ) : catalog?.dishes.length ? (
          <div style={{ display: 'grid', gap: 12 }}>
            {catalog.dishes.map((dish) => {
              const quantity = cart[dish.id]?.quantity ?? 0;
              return (
                <Card key={dish.id} style={{ borderRadius: 12 }}>
                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }}>
                      <div>
                        <Typography.Text strong>{dish.name}</Typography.Text>
                        <Typography.Paragraph style={{ margin: '4px 0 0', color: '#817567' }}>
                          {dish.description || 'Описание скоро появится'}
                        </Typography.Paragraph>
                      </div>
                      <Typography.Text strong style={{ whiteSpace: 'nowrap' }}>{money(dish.price)}</Typography.Text>
                    </Space>
                    <Space>
                      <Button onClick={() => setQuantity(dish, quantity - 1)} disabled={quantity === 0}>-</Button>
                      <InputNumber min={0} max={99} value={quantity} onChange={(value) => setQuantity(dish, Number(value ?? 0))} />
                      <Button type="primary" onClick={() => setQuantity(dish, quantity + 1)}>+</Button>
                    </Space>
                  </Space>
                </Card>
              );
            })}
          </div>
        ) : (
          <Empty description="Меню пока пустое" />
        )}

        <Card title={<Space><ShoppingCartOutlined />Корзина</Space>} style={{ borderRadius: 12 }}>
          {lines.length ? (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {lines.map((line) => (
                <Space key={line.dish.id} style={{ justifyContent: 'space-between', width: '100%' }}>
                  <Typography.Text>{line.dish.name} x {line.quantity}</Typography.Text>
                  <Typography.Text>{money(Number(line.dish.price) * line.quantity)}</Typography.Text>
                </Space>
              ))}
              <Typography.Title level={4} style={{ margin: 0 }}>Итого: {money(total)}</Typography.Title>
              <Form form={form} layout="vertical" onFinish={(values) => checkoutMutation.mutate(values)}>
                <Form.Item name="point_id" label="Точка" rules={[{ required: true, message: 'Выберите точку' }]}>
                  <Select
                    options={(catalog?.points ?? []).map((point) => ({
                      value: point.id,
                      label: `${point.name} · ${point.address}`,
                    }))}
                  />
                </Form.Item>
                <Form.Item name="name" label="Имя">
                  <Input placeholder="Как к вам обращаться" />
                </Form.Item>
                <Form.Item name="phone" label="Телефон" rules={[{ required: true, message: 'Введите телефон' }]}>
                  <Input placeholder="+7..." />
                </Form.Item>
                <Form.Item name="delivery_address" label="Адрес доставки" rules={[{ required: true, message: 'Введите адрес' }]}>
                  <Input.TextArea rows={2} />
                </Form.Item>
                <Form.Item name="notes" label="Комментарий">
                  <Input.TextArea rows={2} />
                </Form.Item>
                <Button type="primary" htmlType="submit" block loading={checkoutMutation.isPending}>
                  Оформить и оплатить
                </Button>
              </Form>
            </Space>
          ) : (
            <Empty description="Добавьте блюда в корзину" />
          )}
        </Card>
      </Space>
    </div>
  );
}
