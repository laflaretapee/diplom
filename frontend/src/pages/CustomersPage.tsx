import { ReloadOutlined, UserOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Card, Drawer, Form, Input, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useState } from 'react';

import { apiClient } from '../api/client';

type Customer = {
  id: string;
  name: string;
  phone?: string | null;
  delivery_address?: string | null;
  telegram_id?: string | null;
  vk_id?: string | null;
  source: 'crm' | 'telegram' | 'vk' | 'website';
  notes?: string | null;
  orders_count: number;
  total_spent: string;
  updated_at: string;
};

type CustomerForm = {
  name: string;
  phone?: string;
  delivery_address?: string;
  telegram_id?: string;
  vk_id?: string;
  notes?: string;
};

const SOURCE_LABELS: Record<Customer['source'], string> = {
  crm: 'CRM',
  telegram: 'Telegram',
  vk: 'VK',
  website: 'Сайт',
};

function money(value: string) {
  return `${Number(value).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽`;
}

export function CustomersPage() {
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Customer | null>(null);
  const [form] = Form.useForm<CustomerForm>();
  const queryClient = useQueryClient();

  const customersQuery = useQuery({
    queryKey: ['customers', query],
    queryFn: async () => {
      const { data } = await apiClient.get<Customer[]>('/v1/customers', {
        params: query ? { query } : undefined,
      });
      return data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (values: CustomerForm) => {
      const { data } = await apiClient.post<Customer>('/v1/customers', {
        ...values,
        source: 'crm',
      });
      return data;
    },
    onSuccess: async () => {
      form.resetFields();
      await queryClient.invalidateQueries({ queryKey: ['customers'] });
    },
  });

  const columns: ColumnsType<Customer> = [
    {
      title: 'Клиент',
      dataIndex: 'name',
      render: (_, customer) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong>{customer.name}</Typography.Text>
          <Typography.Text type="secondary">{customer.phone || 'Телефон не указан'}</Typography.Text>
        </Space>
      ),
    },
    {
      title: 'Источник',
      dataIndex: 'source',
      render: (source: Customer['source']) => <Tag>{SOURCE_LABELS[source]}</Tag>,
    },
    {
      title: 'Telegram',
      dataIndex: 'telegram_id',
      render: (value?: string | null) => value || '—',
    },
    {
      title: 'Заказы',
      dataIndex: 'orders_count',
    },
    {
      title: 'Выручка',
      dataIndex: 'total_spent',
      render: (value: string) => money(value),
    },
  ];

  return (
    <Space direction="vertical" size={18} style={{ width: '100%' }}>
      <Card>
        <Space align="start" style={{ justifyContent: 'space-between', width: '100%' }} wrap>
          <div>
            <Typography.Title level={3} style={{ marginTop: 0 }}>Клиенты</Typography.Title>
            <Typography.Text type="secondary">
              Карточки клиентов из CRM и Telegram Mini App.
            </Typography.Text>
          </div>
          <Button icon={<ReloadOutlined />} onClick={() => void customersQuery.refetch()}>
            Обновить
          </Button>
        </Space>
      </Card>

      <Card>
        <Space direction="vertical" size={14} style={{ width: '100%' }}>
          <Input.Search
            placeholder="Поиск по имени, телефону, Telegram ID или VK ID"
            allowClear
            onSearch={setQuery}
          />
          {customersQuery.isError ? <Alert type="error" message="Не удалось загрузить клиентов" showIcon /> : null}
          <Table
            rowKey="id"
            loading={customersQuery.isLoading || customersQuery.isFetching}
            columns={columns}
            dataSource={customersQuery.data ?? []}
            onRow={(record) => ({
              onClick: () => setSelected(record),
              style: { cursor: 'pointer' },
            })}
            scroll={{ x: true }}
          />
        </Space>
      </Card>

      <Card title={<Space><UserOutlined />Новый клиент</Space>}>
        <Form form={form} layout="vertical" onFinish={(values) => createMutation.mutate(values)}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Form.Item name="name" label="Имя" rules={[{ required: true, message: 'Введите имя' }]}>
              <Input />
            </Form.Item>
            <Form.Item name="phone" label="Телефон">
              <Input />
            </Form.Item>
            <Form.Item name="delivery_address" label="Адрес доставки">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Space.Compact style={{ width: '100%' }}>
              <Form.Item name="telegram_id" label="Telegram ID" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
              <Form.Item name="vk_id" label="VK ID" style={{ width: '50%' }}>
                <Input />
              </Form.Item>
            </Space.Compact>
            <Form.Item name="notes" label="Заметки">
              <Input.TextArea rows={3} />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              Создать клиента
            </Button>
          </Space>
        </Form>
      </Card>

      <Drawer
        title={selected?.name}
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        width={420}
      >
        {selected ? (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Typography.Text><b>Телефон:</b> {selected.phone || '—'}</Typography.Text>
            <Typography.Text><b>Адрес:</b> {selected.delivery_address || '—'}</Typography.Text>
            <Typography.Text><b>Telegram ID:</b> {selected.telegram_id || '—'}</Typography.Text>
            <Typography.Text><b>VK ID:</b> {selected.vk_id || '—'}</Typography.Text>
            <Typography.Text><b>Источник:</b> {SOURCE_LABELS[selected.source]}</Typography.Text>
            <Typography.Text><b>Заказов:</b> {selected.orders_count}</Typography.Text>
            <Typography.Text><b>Оплачено:</b> {money(selected.total_spent)}</Typography.Text>
            <Typography.Paragraph>
              <b>Заметки:</b> {selected.notes || '—'}
            </Typography.Paragraph>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}
