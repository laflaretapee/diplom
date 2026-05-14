import { startTransition, useEffect, useMemo, useState } from 'react';
import { EditOutlined, PlusOutlined, ProfileOutlined, ReloadOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { ColumnsType } from 'antd/es/table';
import axios from 'axios';
import {
  Alert,
  Button,
  Card,
  Col,
  ConfigProvider,
  Empty,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Typography,
  theme as antdTheme,
} from 'antd';

import { apiClient } from '../api/client';
import { useAuthStore } from '../auth/store';
import { useThemeStore } from '../store/themeStore';
import { ensureArray } from '../utils/ensureArray';

type SourceChannel = 'website' | 'mobile_app' | 'telegram' | 'vk' | 'pos';
type DishFilter = 'active' | 'inactive' | 'all';

interface DishRead {
  id: string;
  name: string;
  description: string | null;
  price: number | string;
  is_active: boolean;
  available_channels: SourceChannel[];
}

interface DishCreatePayload {
  name: string;
  description: string;
  price: number;
  available_channels: SourceChannel[];
}

interface DishUpdatePayload {
  name: string;
  description: string;
  price: number;
  is_active: boolean;
  available_channels: SourceChannel[];
}

interface DishIngredientRead {
  id?: string;
  ingredient_id?: string;
  ingredient_name?: string;
  name?: string;
  quantity?: number | string | null;
  amount?: number | string | null;
  unit?: string | null;
}

type MutationNotice = {
  type: 'success' | 'error';
  text: string;
} | null;

type CreateDishFormValues = {
  name: string;
  description?: string;
  price: number;
  available_channels: SourceChannel[];
};

type UpdateDishFormValues = {
  name: string;
  description?: string;
  price: number;
  is_active: boolean;
  available_channels: SourceChannel[];
};

const pageBackground =
  'linear-gradient(180deg, var(--j-surface-muted) 0%, var(--j-surface-strong) 55%, var(--j-surface-muted) 100%)';

const CHANNEL_LABELS: Record<SourceChannel, string> = {
  website: 'Сайт',
  mobile_app: 'Приложение',
  telegram: 'Телеграм',
  vk: 'ВКонтакте',
  pos: 'Касса',
};

const CHANNEL_OPTIONS = (Object.entries(CHANNEL_LABELS) as [SourceChannel, string][]).map(
  ([value, label]) => ({ value, label }),
);
const DEFAULT_CHANNELS: SourceChannel[] = CHANNEL_OPTIONS.map(({ value }) => value);

function authHeader(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function asNumber(value: string | number | null | undefined): number {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : 0;
  }

  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

function formatMoney(value: string | number | null | undefined): string {
  return `${asNumber(value).toLocaleString('ru-RU', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

function parsePriceInput(value: string | number | null | undefined): number {
  const normalized = String(value ?? '')
    .replace(/\s/g, '')
    .replace(/₽/g, '')
    .replace(',', '.')
    .replace(/[^0-9.-]/g, '');

  return normalized ? Number(normalized) : Number.NaN;
}

function formatPriceInput(value: string | number | undefined): string {
  if (value === undefined || value === null || value === '') {
    return '';
  }

  return String(value).replace('.', ',');
}

function formatError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail ?? error.response?.data?.message;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') {
            return item;
          }

          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg?: unknown }).msg ?? '');
          }

          return '';
        })
        .filter(Boolean)
        .join('; ');
    }

    if (error.message) {
      return error.message;
    }
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return 'Не удалось выполнить запрос.';
}

function sortDishes(items: DishRead[]): DishRead[] {
  return [...items].sort((left, right) => {
    if (left.is_active !== right.is_active) {
      return left.is_active ? -1 : 1;
    }

    return left.name.localeCompare(right.name, 'ru');
  });
}

function uniqueDishes(items: DishRead[]): DishRead[] {
  const byId = new Map<string, DishRead>();

  items.forEach((dish) => {
    byId.set(dish.id, dish);
  });

  return sortDishes(Array.from(byId.values()));
}

function ingredientName(item: DishIngredientRead): string {
  return item.ingredient_name?.trim() || item.name?.trim() || item.ingredient_id || item.id || 'Ингредиент';
}

function ingredientAmount(item: DishIngredientRead): string {
  const rawValue = item.quantity ?? item.amount;

  if (rawValue === null || rawValue === undefined || rawValue === '') {
    return '—';
  }

  const numericValue = Number(rawValue);
  const value = Number.isFinite(numericValue)
    ? numericValue.toLocaleString('ru-RU', {
        minimumFractionDigits: numericValue % 1 === 0 ? 0 : 2,
        maximumFractionDigits: 3,
      })
    : String(rawValue);

  return item.unit ? `${value} ${item.unit}` : value;
}

async function fetchDishes(filter: DishFilter, token: string | null): Promise<DishRead[]> {
  const request = (isActive: boolean) =>
    apiClient.get<DishRead[]>('/v1/warehouse/dishes', {
      headers: authHeader(token),
      params: { is_active: isActive },
    });

  if (filter === 'all') {
    const [activeResponse, inactiveResponse] = await Promise.all([request(true), request(false)]);
    return uniqueDishes([
      ...ensureArray<DishRead>(activeResponse.data),
      ...ensureArray<DishRead>(inactiveResponse.data),
    ]);
  }

  const { data } = await request(filter === 'active');
  return sortDishes(ensureArray<DishRead>(data));
}

async function createDish(payload: DishCreatePayload, token: string | null): Promise<DishRead> {
  const { data } = await apiClient.post<DishRead>('/v1/warehouse/dishes', payload, {
    headers: authHeader(token),
  });

  return data;
}

async function updateDish(
  dishId: string,
  payload: DishUpdatePayload,
  token: string | null,
): Promise<DishRead> {
  const { data } = await apiClient.patch<DishRead>(`/v1/warehouse/dishes/${dishId}`, payload, {
    headers: authHeader(token),
  });

  return data;
}

async function fetchDishIngredients(
  dishId: string,
  token: string | null,
): Promise<DishIngredientRead[]> {
  const { data } = await apiClient.get<DishIngredientRead[]>(
    `/v1/warehouse/dishes/${dishId}/ingredients`,
    {
      headers: authHeader(token),
    },
  );

  return ensureArray<DishIngredientRead>(data);
}

export function DishesPage() {
  const token = useAuthStore((state) => state.token);
  const isDark = useThemeStore((state) => state.isDark);
  const queryClient = useQueryClient();
  const [createForm] = Form.useForm<CreateDishFormValues>();
  const [editForm] = Form.useForm<UpdateDishFormValues>();
  const [filter, setFilter] = useState<DishFilter>('active');
  const [selectedDishId, setSelectedDishId] = useState<string>('');
  const [notice, setNotice] = useState<MutationNotice>(null);

  const dishesQuery = useQuery({
    queryKey: ['dishes', token, filter],
    queryFn: () => fetchDishes(filter, token),
    retry: false,
    select: (data) => ensureArray<DishRead>(data),
  });

  const dishes = dishesQuery.data ?? [];
  const selectedDish = dishes.find((dish) => dish.id === selectedDishId) ?? null;

  const ingredientsQuery = useQuery({
    queryKey: ['dish-ingredients', token, selectedDishId],
    queryFn: () => fetchDishIngredients(selectedDishId, token),
    enabled: selectedDishId !== '',
    retry: false,
    select: (data) => ensureArray<DishIngredientRead>(data),
  });

  const createMutation = useMutation({
    mutationFn: (payload: DishCreatePayload) => createDish(payload, token),
    onMutate: () => {
      setNotice(null);
    },
    onSuccess: async (dish) => {
      setNotice({
        type: 'success',
        text: `Блюдо «${dish.name}» создано.`,
      });
      createForm.resetFields();
      startTransition(() => {
        setSelectedDishId(dish.id);
      });
      await queryClient.invalidateQueries({ queryKey: ['dishes'] });
    },
    onError: (error) => {
      setNotice({
        type: 'error',
        text: formatError(error),
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ dishId, payload }: { dishId: string; payload: DishUpdatePayload }) =>
      updateDish(dishId, payload, token),
    onMutate: () => {
      setNotice(null);
    },
    onSuccess: async (dish) => {
      setNotice({
        type: 'success',
        text: `Изменения для блюда «${dish.name}» сохранены.`,
      });
      startTransition(() => {
        setSelectedDishId(dish.id);
      });
      await queryClient.invalidateQueries({ queryKey: ['dishes'] });
    },
    onError: (error) => {
      setNotice({
        type: 'error',
        text: formatError(error),
      });
    },
  });

  useEffect(() => {
    if (dishes.length === 0) {
      setSelectedDishId('');
      editForm.resetFields();
      return;
    }

    const selectedExists = dishes.some((dish) => dish.id === selectedDishId);
    if (!selectedDishId || !selectedExists) {
      setSelectedDishId(dishes[0].id);
    }
  }, [dishes, editForm, selectedDishId]);

  useEffect(() => {
    if (!selectedDish) {
      editForm.resetFields();
      return;
    }

    editForm.setFieldsValue({
      name: selectedDish.name,
      description: selectedDish.description ?? '',
      price: asNumber(selectedDish.price),
      is_active: selectedDish.is_active,
      available_channels: selectedDish.available_channels,
    });
  }, [editForm, selectedDish]);

  const handleRefresh = async () => {
    setNotice(null);
    await Promise.all([
      dishesQuery.refetch(),
      selectedDishId ? ingredientsQuery.refetch() : Promise.resolve(),
    ]);
  };

  const handleCreate = async (values: CreateDishFormValues) => {
    await createMutation.mutateAsync({
      name: values.name.trim(),
      description: values.description?.trim() ?? '',
      price: values.price,
      available_channels: values.available_channels,
    });
  };

  const handleUpdate = async (values: UpdateDishFormValues) => {
    if (!selectedDish) {
      return;
    }

    await updateMutation.mutateAsync({
      dishId: selectedDish.id,
      payload: {
        name: values.name.trim(),
        description: values.description?.trim() ?? '',
        price: values.price,
        is_active: values.is_active,
        available_channels: values.available_channels,
      },
    });
  };

  const stats = useMemo(
    () => ({
      total: dishes.length,
      active: dishes.filter((dish) => dish.is_active).length,
      inactive: dishes.filter((dish) => !dish.is_active).length,
    }),
    [dishes],
  );

  const dishColumns: ColumnsType<DishRead> = [
    {
      title: 'Блюдо',
      dataIndex: 'name',
      key: 'name',
      render: (_value: string, record: DishRead) => (
        <Space direction="vertical" size={2}>
          <Typography.Text strong style={{ color: 'var(--j-text)' }}>
            {record.name}
          </Typography.Text>
          <Typography.Text style={{ color: 'var(--j-text-tertiary)', fontSize: 12 }}>
            {record.description?.trim() || 'Без описания'}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: 'Цена',
      dataIndex: 'price',
      key: 'price',
      width: 140,
      render: (value: string | number) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{formatMoney(value)}</span>
      ),
    },
    {
      title: 'Статус',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 140,
      render: (value: boolean) =>
        value ? <Tag color="green">Активно</Tag> : <Tag color="default">Выключено</Tag>,
    },
    {
      title: 'Каналы',
      dataIndex: 'available_channels',
      key: 'available_channels',
      render: (channels: SourceChannel[]) =>
        channels.length > 0 ? (
          <Space size={[6, 6]} wrap>
            {channels.map((channel) => (
              <Tag
                key={channel}
                style={{
                  marginInlineEnd: 0,
                  background: 'var(--j-warning-bg)',
                  borderColor: 'var(--j-border)',
                  color: '#FFD598',
                }}
              >
                {CHANNEL_LABELS[channel]}
              </Tag>
            ))}
          </Space>
        ) : (
          '—'
        ),
    },
  ];

  const ingredientColumns: ColumnsType<DishIngredientRead> = [
    {
      title: 'Ингредиент',
      key: 'ingredient_name',
      render: (_value: unknown, record: DishIngredientRead) => ingredientName(record),
    },
    {
      title: 'Количество',
      key: 'quantity',
      width: 180,
      render: (_value: unknown, record: DishIngredientRead) => (
        <span style={{ fontFamily: 'JetBrains Mono, monospace' }}>{ingredientAmount(record)}</span>
      ),
    },
  ];

  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorBgBase: 'var(--j-surface-muted)',
          colorBgContainer: 'var(--j-surface-panel)',
          colorBgElevated: 'var(--j-surface-high)',
          colorText: 'var(--j-text)',
          colorTextSecondary: 'var(--j-text-secondary)',
          colorBorder: 'var(--j-border)',
          colorPrimary: '#E8B86D',
          colorPrimaryBg: 'var(--j-warning-bg)',
          colorLink: '#FFD598',
          borderRadius: 10,
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          fontFamilyCode: 'JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, monospace',
        },
        components: {
          Card: {
            colorBgContainer: 'var(--j-surface-panel)',
            headerBg: 'var(--j-surface-panel)',
          },
          Table: {
            headerBg: 'var(--j-surface-high)',
            headerColor: 'var(--j-text)',
            borderColor: 'var(--j-border)',
            rowHoverBg: 'var(--j-surface-muted)',
          },
        },
      }}
    >
      <Space direction="vertical" size={20} style={{ width: '100%' }}>
        <Card
          bordered={false}
          style={{
            background: pageBackground,
            border: '1px solid rgba(79, 69, 56, 0.35)',
            boxShadow: '0 18px 48px var(--j-shadow)',
          }}
        >
          <Row gutter={[16, 16]} align="middle" justify="space-between">
            <Col xs={24} xl={14}>
              <Space direction="vertical" size={6}>
                <Typography.Title level={2} style={{ margin: 0, color: 'var(--j-text)' }}>
                  Блюда и каналы продаж
                </Typography.Title>
                <Typography.Text style={{ color: 'var(--j-text-secondary)', lineHeight: 1.7 }}>
                  Управление ассортиментом для demo: создание блюда, переключение активности,
                  публикация по каналам и просмотр техкарты.
                </Typography.Text>
                <Space size={[8, 8]} wrap>
                  <Tag color="gold">Всего: {stats.total}</Tag>
                  <Tag color="green">Активных: {stats.active}</Tag>
                  <Tag color="default">Неактивных: {stats.inactive}</Tag>
                </Space>
              </Space>
            </Col>
            <Col xs={24} xl={10}>
              <Space wrap style={{ justifyContent: 'flex-end', width: '100%' }}>
                <Radio.Group
                  value={filter}
                  onChange={(event) => {
                    const nextFilter = event.target.value as DishFilter;
                    startTransition(() => {
                      setFilter(nextFilter);
                    });
                  }}
                  optionType="button"
                  buttonStyle="solid"
                  options={[
                    { label: 'Активные', value: 'active' },
                    { label: 'Неактивные', value: 'inactive' },
                    { label: 'Все', value: 'all' },
                  ]}
                />
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    void handleRefresh();
                  }}
                  loading={dishesQuery.isFetching || ingredientsQuery.isFetching}
                >
                  Обновить
                </Button>
              </Space>
            </Col>
          </Row>
          {notice ? (
            <Alert
              style={{ marginTop: 16 }}
              type={notice.type}
              showIcon
              message={notice.text}
            />
          ) : null}
        </Card>

        <Row gutter={[20, 20]} align="stretch">
          <Col xs={24} xl={8}>
            <Card
              title={
                <Space size={8}>
                  <PlusOutlined />
                  <span>Создать блюдо</span>
                </Space>
              }
              bordered={false}
              style={{ height: '100%' }}
            >
              <Form<CreateDishFormValues>
                layout="vertical"
                form={createForm}
                initialValues={{ available_channels: DEFAULT_CHANNELS }}
                onFinish={(values) => {
                  void handleCreate(values);
                }}
              >
                <Form.Item
                  label="Название"
                  name="name"
                  rules={[{ required: true, message: 'Введите название блюда' }]}
                >
                  <Input placeholder="Например, Филадельфия лайт" maxLength={120} />
                </Form.Item>
                <Form.Item label="Описание" name="description">
                  <Input.TextArea
                    placeholder="Коротко опишите блюдо для админки"
                    rows={4}
                    maxLength={500}
                    showCount
                  />
                </Form.Item>
                <Form.Item
                  label="Цена"
                  name="price"
                  rules={[{ required: true, message: 'Укажите цену' }]}
                >
                  <InputNumber
                    min={0.01}
                    step={0.01}
                    precision={2}
                    controls={false}
                    addonAfter="₽"
                    decimalSeparator=","
                    parser={(value) => parsePriceInput(value)}
                    formatter={(value) => formatPriceInput(value)}
                    style={{ width: '100%' }}
                    placeholder="0,00"
                  />
                </Form.Item>
                <Form.Item label="Каналы продаж" name="available_channels">
                  <Select
                    mode="multiple"
                    placeholder="Где блюдо доступно клиенту"
                    options={CHANNEL_OPTIONS}
                  />
                </Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  loading={createMutation.isPending}
                  icon={<PlusOutlined />}
                >
                  Создать блюдо
                </Button>
              </Form>
            </Card>
          </Col>

          <Col xs={24} xl={16}>
            <Card
              title="Список блюд"
              extra={
                selectedDish ? (
                  <Typography.Text style={{ color: 'var(--j-text-tertiary)' }}>
                    Выбрано: {selectedDish.name}
                  </Typography.Text>
                ) : null
              }
              bordered={false}
              style={{ height: '100%' }}
            >
              {dishesQuery.isLoading ? (
                <div style={{ minHeight: 320, display: 'grid', placeItems: 'center' }}>
                  <Spin size="large" tip="Загружаем блюда" />
                </div>
              ) : dishesQuery.isError ? (
                <Alert
                  type="error"
                  showIcon
                  message="Не удалось загрузить список блюд"
                  description={formatError(dishesQuery.error)}
                  action={
                    <Button size="small" onClick={() => void dishesQuery.refetch()}>
                      Повторить
                    </Button>
                  }
                />
              ) : (
                <Table<DishRead>
                  rowKey="id"
                  columns={dishColumns}
                  dataSource={dishes}
                  pagination={{ pageSize: 8, hideOnSinglePage: true }}
                  scroll={{ x: 960 }}
                  locale={{ emptyText: <Empty description="Блюда пока не заведены" /> }}
                  onRow={(record) => ({
                    onClick: () => {
                      startTransition(() => {
                        setSelectedDishId(record.id);
                      });
                    },
                  })}
                  rowClassName={(record) => (record.id === selectedDishId ? 'ant-table-row-selected' : '')}
                />
              )}
            </Card>
          </Col>
        </Row>

        <Row gutter={[20, 20]} align="stretch">
          <Col xs={24} xl={10}>
            <Card
              title={
                <Space size={8}>
                  <EditOutlined />
                  <span>Редактирование блюда</span>
                </Space>
              }
              bordered={false}
              style={{ height: '100%' }}
            >
              {!selectedDish ? (
                <Empty description="Выберите блюдо из списка" />
              ) : (
                <Form<UpdateDishFormValues>
                  layout="vertical"
                  form={editForm}
                  onFinish={(values) => {
                    void handleUpdate(values);
                  }}
                >
                  <Form.Item
                    label="Название"
                    name="name"
                    rules={[{ required: true, message: 'Введите название блюда' }]}
                  >
                    <Input maxLength={120} />
                  </Form.Item>
                  <Form.Item label="Описание" name="description">
                    <Input.TextArea rows={4} maxLength={500} showCount />
                  </Form.Item>
                  <Form.Item
                    label="Цена"
                    name="price"
                    rules={[{ required: true, message: 'Укажите цену' }]}
                  >
                    <InputNumber
                      min={0.01}
                      step={0.01}
                      precision={2}
                      controls={false}
                      addonAfter="₽"
                      decimalSeparator=","
                      parser={(value) => parsePriceInput(value)}
                      formatter={(value) => formatPriceInput(value)}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                  <Form.Item label="Каналы продаж" name="available_channels">
                    <Select mode="multiple" options={CHANNEL_OPTIONS} />
                  </Form.Item>
                  <Form.Item
                    label="Доступность блюда"
                    name="is_active"
                    valuePropName="checked"
                    extra="Неактивное блюдо остаётся в каталоге, но не доступно к продаже."
                  >
                    <Switch checkedChildren="Активно" unCheckedChildren="Выключено" />
                  </Form.Item>
                  <Space wrap>
                    <Button
                      type="primary"
                      htmlType="submit"
                      loading={updateMutation.isPending}
                      icon={<EditOutlined />}
                    >
                      Сохранить изменения
                    </Button>
                    <Button
                      onClick={() => {
                        if (!selectedDish) {
                          return;
                        }

                        editForm.setFieldsValue({
                          name: selectedDish.name,
                          description: selectedDish.description ?? '',
                          price: asNumber(selectedDish.price),
                          is_active: selectedDish.is_active,
                          available_channels: selectedDish.available_channels,
                        });
                      }}
                    >
                      Сбросить форму
                    </Button>
                  </Space>
                </Form>
              )}
            </Card>
          </Col>

          <Col xs={24} xl={14}>
            <Card
              title={
                <Space size={8}>
                  <ProfileOutlined />
                  <span>Техкарта блюда</span>
                </Space>
              }
              extra={
                selectedDish ? (
                  <Typography.Text style={{ color: 'var(--j-text-tertiary)' }}>
                    {selectedDish.name}
                  </Typography.Text>
                ) : null
              }
              bordered={false}
              style={{ height: '100%' }}
            >
              {!selectedDish ? (
                <Empty description="Сначала выберите блюдо" />
              ) : ingredientsQuery.isLoading ? (
                <div style={{ minHeight: 240, display: 'grid', placeItems: 'center' }}>
                  <Spin size="large" tip="Загружаем техкарту" />
                </div>
              ) : ingredientsQuery.isError ? (
                <Alert
                  type="error"
                  showIcon
                  message="Не удалось загрузить техкарту"
                  description={formatError(ingredientsQuery.error)}
                  action={
                    <Button size="small" onClick={() => void ingredientsQuery.refetch()}>
                      Повторить
                    </Button>
                  }
                />
              ) : (
                <Table<DishIngredientRead>
                  rowKey={(record) => record.id ?? record.ingredient_id ?? ingredientName(record)}
                  columns={ingredientColumns}
                  dataSource={ingredientsQuery.data ?? []}
                  pagination={false}
                  scroll={{ x: 640 }}
                  locale={{
                    emptyText: <Empty description="Для блюда ещё не настроен состав" />,
                  }}
                />
              )}
            </Card>
          </Col>
        </Row>
      </Space>
    </ConfigProvider>
  );
}
